from __future__ import annotations
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.doctor import Doctor
from src.models.user import User
from src.schemas.doctor import CreateDoctorRequest, UpdateDoctorRequest, UpdateMyDoctorRequest
from src.server.exceptions import NotFoundException
from src.services.clerk.clerk_service import ClerkService

settings = get_settings()


class DoctorsService:
    """Backs the dashboard's Doctors page (frontend/src/app/dashboard/doctors/) —
    every method here is practice-scoped; callers must always pass the
    requesting user's own practice_id (see server/dependencies.py:
    get_current_practice_user), never trust one from the client. Mirrors
    services/patients/patients_services.py's shape."""

    async def create_doctor(self, db: AsyncSession, practice_id: UUID, data: CreateDoctorRequest) -> Doctor:
        doctor = Doctor(
            practice_id=practice_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            specialty=data.specialty,
            license_number=data.license_number,
            bio=data.bio,
            capabilities=data.capabilities,
            qualifications=[q.model_dump() for q in data.qualifications],
            specializations=data.specializations,
            working_hours=data.working_hours,
            commission_percent=data.commission_percent,
        )
        db.add(doctor)
        await db.flush()
        await db.refresh(doctor)
        return doctor

    async def list_doctors(self, db: AsyncSession, practice_id: UUID) -> list[Doctor]:
        query = select(Doctor).where(Doctor.practice_id == practice_id).order_by(desc(Doctor.created_at))
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_doctor(self, db: AsyncSession, practice_id: UUID, doctor_id: UUID) -> Doctor:
        query = select(Doctor).where(Doctor.id == doctor_id, Doctor.practice_id == practice_id)
        result = await db.execute(query)
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("Doctor not found")
        return doctor

    async def get_my_doctor(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> Doctor:
        query = select(Doctor).where(Doctor.practice_id == practice_id, Doctor.user_id == user_id)
        result = await db.execute(query)
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise NotFoundException("No doctor profile linked to this account")
        return doctor

    async def update_my_doctor(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, data: UpdateMyDoctorRequest
    ) -> Doctor:
        """Doctor edits their own profile (contact, education, license,
        weekly schedule — see UpdateMyDoctorRequest). name / photo_url /
        signature_url / commission / is_active can never arrive here because
        the self-service schema whitelists them out; those stay Owner-managed
        via PATCH /doctors/{id}."""
        doctor = await self.get_my_doctor(db, practice_id, user_id)
        fields = data.model_dump(exclude_unset=True)
        for field, value in fields.items():
            if field == "qualifications" and value is not None:
                doctor.qualifications = [q.model_dump() for q in value]
            else:
                setattr(doctor, field, value)
        await db.flush()
        await db.refresh(doctor)
        return doctor

    async def update_doctor(
        self, db: AsyncSession, practice_id: UUID, doctor_id: UUID, data: UpdateDoctorRequest
    ) -> Doctor:
        doctor = await self.get_doctor(db, practice_id, doctor_id)
        fields = data.model_dump(exclude_unset=True)
        for field, value in fields.items():
            setattr(doctor, field, value)

        # Doctor.is_active and the linked User.is_active are two separate
        # flags (a Doctor is a roster entry, a User is a login) — without
        # this, an Owner "deactivating" a doctor here left their dashboard
        # login (get_current_practice_user only checks User.is_active)
        # completely untouched. Keep them in lockstep in both directions so
        # deactivating actually revokes portal access, and reactivating
        # actually restores it.
        if "is_active" in fields and doctor.user_id is not None:
            linked_user = await db.get(User, doctor.user_id)
            if linked_user is not None:
                linked_user.is_active = fields["is_active"]

        await db.flush()
        await db.refresh(doctor)
        return doctor

    async def invite_doctor(self, db: AsyncSession, practice_id: UUID, doctor_id: UUID) -> Doctor:
        doctor = await self.get_doctor(db, practice_id, doctor_id)
        clerk = ClerkService()
        await clerk.invite_user(
            email=doctor.email,
            redirect_url=f"{settings.frontend_url}/doctor/sign-up",
            public_metadata={
                "invite_type": "doctor",
                "doctor_id": str(doctor.id),
                "practice_id": str(doctor.practice_id),
            },
        )
        return doctor
