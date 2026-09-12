from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_signup import PendingSignup, OrgRequestStatus
from src.server.exceptions import NotFoundException, AppException

# The free "new organization" self-signup path (plain /sign-up, no plan
# chosen) — completely separate from CheckoutService/ProvisioningService's
# paid Pricing->Stripe->claim flow, but reuses the SAME PendingSignup table
# (see its module docstring) since the lifecycle fields it needs
# (email/practice_id/claimed_at/claimed_by_clerk_id) are identical; only
# request_status/org_name/clerk_id are unique to this path.
#
# A row here is created at one of two possible moments:
#   1. The Clerk `user.created` webhook (webhook_router.py's else-branch),
#      the moment a brand-new account first appears — but this can't fire in
#      local dev (Clerk can't POST to 127.0.0.1), so:
#   2. `submit()` below self-heals: if no row exists yet for this clerk_id,
#      it creates one on the spot, exactly the same self-heal pattern already
#      established in dependencies.py/doctor_applications for the same
#      "webhook never arrived" reason.


class OrgRequestService:
    async def get_or_create_for_webhook(self, db: AsyncSession, clerk_id: str, email: str) -> PendingSignup:
        result = await db.execute(select(PendingSignup).where(PendingSignup.clerk_id == clerk_id))
        pending = result.scalar_one_or_none()
        if pending is not None:
            return pending

        pending = PendingSignup(
            email=email,
            clerk_id=clerk_id,
            stripe_session_id=None,
            request_status=OrgRequestStatus.PENDING,
        )
        db.add(pending)
        await db.flush()
        return pending

    async def submit(self, db: AsyncSession, clerk_id: str, email: str, org_name: str) -> PendingSignup:
        pending = await self.get_or_create_for_webhook(db, clerk_id, email)
        if pending.request_status == OrgRequestStatus.REJECTED:
            # A rejected applicant editing and resubmitting goes back to the
            # review queue, mirroring DoctorApplicationsService's identical
            # re-apply behavior.
            pending.request_status = OrgRequestStatus.PENDING
            pending.rejected_reason = None
            pending.reviewed_at = None
        if pending.request_status != OrgRequestStatus.PENDING:
            raise AppException(f"This request is already {pending.request_status.value}.")
        pending.org_name = org_name
        await db.flush()
        await db.refresh(pending)
        return pending

    async def get_my_request(self, db: AsyncSession, clerk_id: str) -> PendingSignup:
        result = await db.execute(select(PendingSignup).where(PendingSignup.clerk_id == clerk_id))
        pending = result.scalar_one_or_none()
        if pending is None:
            raise NotFoundException("No organization request found for this account.")
        return pending
