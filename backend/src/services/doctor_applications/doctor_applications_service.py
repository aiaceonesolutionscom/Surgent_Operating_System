from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_doctor_request import PendingDoctorRequest, DoctorRequestStatus
from src.models.doctor import Doctor
from src.models.user import User, UserRole
from src.data.doctor_permissions import VALID_DOCTOR_PERMISSION_KEYS
from src.schemas.doctor_application import SubmitDoctorApplicationRequest
from src.server.exceptions import NotFoundException, AppException
from src.services.storage.storage_service import StorageService
from src.services.agent_log.agent_log_service import AgentLogService


class DoctorApplicationsService:
    """A doctor's self-registration path — Clerk sign-up (via a practice's
    shareable signup code) creates an *inactive* User row (see the
    user.created webhook's `doctor_self_apply` branch); this service handles
    everything from there: submitting the application, and the Owner's
    review/approve/reject decision that ultimately creates the real Doctor
    row and reactivates the User."""

    def __init__(self):
        self.storage = StorageService()
        self.agent_log = AgentLogService()

    async def upload_file(self, practice_id: UUID, file_bytes: bytes, filename: str) -> dict:
        # Cloudinary defaults to resource_type="image", which rejects PDFs and
        # other non-image documents. Pick "raw" for everything that isn't a
        # common image extension so license certs and diplomas upload cleanly.
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "tif", "svg", "heic", "heif", "avif", "ico"}
        resource_type = "image" if ext in image_exts else "raw"
        return await self.storage.upload(
            file_bytes, filename, folder=f"doctor_applications/{practice_id}", resource_type=resource_type
        )

    async def submit_application(
        self, db: AsyncSession, clerk_id: str, practice_id: UUID, data: SubmitDoctorApplicationRequest
    ) -> PendingDoctorRequest:
        result = await db.execute(select(PendingDoctorRequest).where(PendingDoctorRequest.clerk_id == clerk_id))
        application = result.scalar_one_or_none()

        if application is None:
            application = PendingDoctorRequest(clerk_id=clerk_id, practice_id=practice_id)
            db.add(application)

        application.name = data.name
        application.email = data.email
        application.phone = data.phone
        application.specialty = data.specialty
        application.license_number = data.license_number
        application.bio = data.bio
        application.photo_url = data.photo_url
        application.documents = [d.model_dump() for d in data.documents]
        # A rejected applicant editing and resubmitting goes back to the
        # review queue rather than staying permanently rejected.
        if application.status == DoctorRequestStatus.REJECTED:
            application.status = DoctorRequestStatus.PENDING
            application.rejected_reason = None
            application.reviewed_at = None

        await db.flush()
        await db.refresh(application)
        return application

    async def get_my_application(self, db: AsyncSession, clerk_id: str) -> PendingDoctorRequest:
        result = await db.execute(select(PendingDoctorRequest).where(PendingDoctorRequest.clerk_id == clerk_id))
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundException("No application found for this account")
        return application

    async def list_applications(
        self, db: AsyncSession, practice_id: UUID, status: DoctorRequestStatus | None = None
    ) -> list[PendingDoctorRequest]:
        query = select(PendingDoctorRequest).where(PendingDoctorRequest.practice_id == practice_id)
        if status is not None:
            query = query.where(PendingDoctorRequest.status == status)
        query = query.order_by(PendingDoctorRequest.submitted_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_application(self, db: AsyncSession, practice_id: UUID, request_id: UUID) -> PendingDoctorRequest:
        result = await db.execute(
            select(PendingDoctorRequest).where(
                PendingDoctorRequest.id == request_id, PendingDoctorRequest.practice_id == practice_id
            )
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundException("Application not found")
        return application

    async def approve_application(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, permissions: list[str], approved_by: UUID
    ) -> Doctor:
        application = await self.get_application(db, practice_id, request_id)
        if application.status != DoctorRequestStatus.PENDING:
            raise AppException(f"Application is already {application.status.value}")

        result = await db.execute(select(User).where(User.clerk_id == application.clerk_id))
        applicant_user = result.scalar_one_or_none()
        if applicant_user is None:
            raise NotFoundException("No account found for this applicant")

        # Doctor.user_id is unique — a second application from an account
        # that's already linked to a Doctor row (e.g. someone re-applying
        # with an account that was already approved) would otherwise hit a
        # raw IntegrityError here instead of a clear rejection.
        existing_doctor = await db.execute(select(Doctor).where(Doctor.user_id == applicant_user.id))
        if existing_doctor.scalar_one_or_none() is not None:
            raise AppException("This account is already registered as a doctor at this practice.")

        granted = [p for p in permissions if p in VALID_DOCTOR_PERMISSION_KEYS]

        doctor = Doctor(
            practice_id=practice_id,
            user_id=applicant_user.id,
            name=application.name,
            email=application.email,
            phone=application.phone,
            specialty=application.specialty,
            license_number=application.license_number,
            bio=application.bio,
            photo_url=application.photo_url,
            permissions=granted,
        )
        db.add(doctor)
        await db.flush()

        # Heal the applicant's account to THIS practice and role on approval —
        # a row that slipped through with a stale practice_id (older relink
        # bug) could otherwise keep resolving to the wrong practice's context
        # forever, so the approved doctor lands in the wrong dashboard.
        applicant_user.is_active = True
        applicant_user.practice_id = practice_id
        applicant_user.role = UserRole.DOCTOR
        application.status = DoctorRequestStatus.APPROVED
        application.doctor_id = doctor.id
        application.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(doctor)

        await self.agent_log.log(
            db,
            practice_id,
            agent_type="doctor_applications",
            action="doctor_application_approved",
            details={"application_id": str(application.id), "doctor_id": str(doctor.id), "permissions": granted},
            performed_by=str(approved_by),
        )
        return doctor

    async def reject_application(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, reason: str | None
    ) -> PendingDoctorRequest:
        application = await self.get_application(db, practice_id, request_id)
        if application.status != DoctorRequestStatus.PENDING:
            raise AppException(f"Application is already {application.status.value}")

        application.status = DoctorRequestStatus.REJECTED
        application.rejected_reason = reason
        application.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(application)
        return application

    async def delete_application(self, db: AsyncSession, practice_id: UUID, request_id: UUID) -> None:
        # Deleting the request record never touches a Doctor row already
        # created from an approved one — application.doctor_id is a plain
        # reference, not a cascade — so this is safe to allow for any
        # status (pending clutter, a mistaken/misfiled request, or just
        # tidying up old decisions).
        application = await self.get_application(db, practice_id, request_id)
        await db.delete(application)
        await db.flush()
