from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_staff_request import PendingStaffRequest, StaffRequestStatus
from src.models.user import User, UserRole
from src.data.receptionist_permissions import VALID_RECEPTIONIST_PERMISSION_KEYS
from src.schemas.staff_application import SubmitStaffApplicationRequest
from src.server.exceptions import NotFoundException, AppException
from src.services.agent_log.agent_log_service import AgentLogService


class StaffApplicationsService:
    """A receptionist's self-registration path — the exact mirror of
    DoctorApplicationsService: Clerk sign-up (via a practice's shareable
    signup code) creates an *inactive* RECEPTIONIST User row (see the
    user.created webhook's `staff_self_apply` branch); this service handles
    submitting the application and the Owner's review/approve/reject decision
    that reactivates the User and grants their permissions. Waiting for
    approval works identically to a doctor's, so both roles share ONE
    onboarding mechanism (link + pending review), replacing the old
    Clerk-email-invite path for receptionists."""

    def __init__(self):
        self.agent_log = AgentLogService()

    async def submit_application(
        self, db: AsyncSession, clerk_id: str, practice_id: UUID, data: SubmitStaffApplicationRequest
    ) -> PendingStaffRequest:
        result = await db.execute(select(PendingStaffRequest).where(PendingStaffRequest.clerk_id == clerk_id))
        application = result.scalar_one_or_none()

        if application is None:
            application = PendingStaffRequest(clerk_id=clerk_id, practice_id=practice_id)
            db.add(application)

        application.name = data.name
        application.email = data.email
        application.phone = data.phone
        # A rejected applicant editing and resubmitting goes back to the
        # review queue rather than staying permanently rejected.
        if application.status == StaffRequestStatus.REJECTED:
            application.status = StaffRequestStatus.PENDING
            application.rejected_reason = None
            application.reviewed_at = None

        await db.flush()
        await db.refresh(application)
        return application

    async def get_my_application(self, db: AsyncSession, clerk_id: str) -> PendingStaffRequest:
        result = await db.execute(select(PendingStaffRequest).where(PendingStaffRequest.clerk_id == clerk_id))
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundException("No application found for this account")
        return application

    async def list_applications(
        self, db: AsyncSession, practice_id: UUID, status: StaffRequestStatus | None = None
    ) -> list[PendingStaffRequest]:
        query = select(PendingStaffRequest).where(PendingStaffRequest.practice_id == practice_id)
        if status is not None:
            query = query.where(PendingStaffRequest.status == status)
        query = query.order_by(PendingStaffRequest.submitted_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_application(self, db: AsyncSession, practice_id: UUID, request_id: UUID) -> PendingStaffRequest:
        result = await db.execute(
            select(PendingStaffRequest).where(
                PendingStaffRequest.id == request_id, PendingStaffRequest.practice_id == practice_id
            )
        )
        application = result.scalar_one_or_none()
        if application is None:
            raise NotFoundException("Application not found")
        return application

    async def approve_application(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, permissions: list[str], approved_by: UUID
    ) -> User:
        application = await self.get_application(db, practice_id, request_id)
        if application.status != StaffRequestStatus.PENDING:
            raise AppException(f"Application is already {application.status.value}")

        result = await db.execute(select(User).where(User.clerk_id == application.clerk_id))
        applicant_user = result.scalar_one_or_none()
        if applicant_user is None:
            raise NotFoundException("No account found for this applicant")

        granted = [p for p in permissions if p in VALID_RECEPTIONIST_PERMISSION_KEYS]

        # Same heal as the doctor approval — a stale practice_id/role on the
        # applicant's User row is corrected now so the approved receptionist
        # resolves the right practice context, not a foreign one.
        applicant_user.is_active = True
        applicant_user.practice_id = practice_id
        applicant_user.role = UserRole.RECEPTIONIST
        applicant_user.permissions = granted
        application.status = StaffRequestStatus.APPROVED
        application.user_id = applicant_user.id
        application.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(applicant_user)

        await self.agent_log.log(
            db,
            practice_id,
            agent_type="staff_applications",
            action="staff_application_approved",
            details={"application_id": str(application.id), "user_id": str(applicant_user.id), "permissions": granted},
            performed_by=str(approved_by),
        )
        return applicant_user

    async def reject_application(
        self, db: AsyncSession, practice_id: UUID, request_id: UUID, reason: str | None
    ) -> PendingStaffRequest:
        application = await self.get_application(db, practice_id, request_id)
        if application.status != StaffRequestStatus.PENDING:
            raise AppException(f"Application is already {application.status.value}")

        application.status = StaffRequestStatus.REJECTED
        application.rejected_reason = reason
        application.reviewed_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(application)
        return application

    async def delete_application(self, db: AsyncSession, practice_id: UUID, request_id: UUID) -> None:
        # Deleting the request record never touches a User row already
        # activated from an approved one (application.user_id is a plain
        # reference, not a cascade) — safe for any status.
        application = await self.get_application(db, practice_id, request_id)
        await db.delete(application)
        await db.flush()