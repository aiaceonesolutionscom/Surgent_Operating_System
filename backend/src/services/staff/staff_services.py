from __future__ import annotations
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.user import User, UserRole
from src.data.receptionist_permissions import VALID_RECEPTIONIST_PERMISSION_KEYS
from src.server.exceptions import NotFoundException, AppException
from src.services.clerk.clerk_service import ClerkService

settings = get_settings()


class StaffService:
    """Backs the dashboard's Receptionist/front-desk staff management —
    invited by the Owner via Clerk (mirrors services/doctors/doctors_services.py's
    invite_doctor), but unlike Doctor there's no roster row created ahead of
    time: permissions live directly on User.permissions (see models/user.py),
    and the real User row only exists once the invitee completes Clerk
    sign-up (see router/v1/webhooks/webhook_router.py's
    invite_type == "receptionist" branch)."""

    async def invite_staff(self, db: AsyncSession, practice_id: UUID, email: str, permissions: list[str]) -> dict:
        granted = [p for p in permissions if p in VALID_RECEPTIONIST_PERMISSION_KEYS]
        clerk = ClerkService()
        # Clerk has no idempotency of its own — a double-click or a retried
        # request would otherwise fire a second invite email for the same
        # not-yet-accepted invitation.
        if await clerk.has_pending_invitation(email):
            raise AppException(f"An invitation is already pending for {email}.")
        await clerk.invite_user(
            email=email,
            redirect_url=f"{settings.frontend_url}/staff/sign-up",
            public_metadata={
                "invite_type": "receptionist",
                "practice_id": str(practice_id),
                "permissions": granted,
            },
        )
        return {"email": email, "permissions": granted}

    async def list_staff(self, db: AsyncSession, practice_id: UUID) -> list[User]:
        query = (
            select(User)
            .where(User.practice_id == practice_id, User.role == UserRole.RECEPTIONIST)
            .order_by(User.created_at.desc())
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def resend_access(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> User:
        """The Owner's "help them log back in" lever for a receptionist whose
        Clerk session is gone (e.g. a wiped local/dev Clerk instance — the
        same class of problem documented throughout dependencies.py) — resends
        the SAME invite this person originally got, to the SAME email, with
        their CURRENT permissions. The webhook's receptionist branch
        (webhook_router.py) now relinks this exact existing row by
        practice_id+email instead of inserting a duplicate, so their history
        (messages, expenses, attendance) is never lost."""
        staff = await self.get_staff(db, practice_id, user_id)
        clerk = ClerkService()
        if await clerk.has_pending_invitation(staff.email):
            raise AppException(f"An invitation is already pending for {staff.email}.")
        await clerk.invite_user(
            email=staff.email,
            redirect_url=f"{settings.frontend_url}/staff/sign-up",
            public_metadata={
                "invite_type": "receptionist",
                "practice_id": str(practice_id),
                "permissions": staff.permissions,
            },
        )
        return staff

    async def get_staff(self, db: AsyncSession, practice_id: UUID, user_id: UUID) -> User:
        query = select(User).where(
            User.id == user_id, User.practice_id == practice_id, User.role == UserRole.RECEPTIONIST
        )
        result = await db.execute(query)
        staff = result.scalar_one_or_none()
        if staff is None:
            raise NotFoundException("Staff member not found")
        return staff

    async def update_my(self, db: AsyncSession, user: User, work_schedule: dict | None, phone: str | None) -> User:
        """The staff member updates their own profile: the recurring weekly
        work schedule and phone number. name/email/role stay Owner-owned."""
        if work_schedule is not None:
            user.work_schedule = work_schedule if isinstance(work_schedule, dict) else {}
        if phone is not None:
            user.phone = phone
        await db.flush()
        await db.refresh(user)
        return user

    async def update_staff(
        self, db: AsyncSession, practice_id: UUID, user_id: UUID, permissions: list[str] | None, is_active: bool | None
    ) -> User:
        staff = await self.get_staff(db, practice_id, user_id)
        if permissions is not None:
            staff.permissions = [p for p in permissions if p in VALID_RECEPTIONIST_PERMISSION_KEYS]
        if is_active is not None:
            staff.is_active = is_active
        await db.flush()
        await db.refresh(staff)
        return staff
