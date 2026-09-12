from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.server.exceptions import UnauthorizedException, ForbiddenException
from src.services.clerk.clerk_service import ClerkService
from src.services.practice.practice_services import PracticeService
from src.services.admin.plan_services import PlanService
from src.services.admin.admin_auth_service import verify_admin_token
from src.services.patient_portal.patient_portal_auth_service import PatientPortalAuthService
from src.models.user import User, UserRole
from src.models.practice import Practice, PracticeStatus
from src.models.patient import Patient
from src.models.subscription import SubscriptionTier

plan_service = PlanService()


async def get_current_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")

    token = authorization.replace("Bearer ", "")
    clerk = ClerkService()
    user = await clerk.verify_token(token)

    if not user:
        raise UnauthorizedException("Invalid or expired token")

    return user


async def get_optional_user(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
):
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization.replace("Bearer ", "")
    clerk = ClerkService()
    user = await clerk.verify_token(token)
    return user


async def get_current_practice_user(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # `get_current_user` only proves the request carries a *valid Clerk
    # session* — it says nothing about which practice that person belongs to,
    # since Clerk's JWT doesn't carry our `practice_id`. Any endpoint that
    # scopes data by practice (conversations, patients, appointments, ...)
    # needs to resolve Clerk's `sub` to a local `User` row for that instead of
    # trusting a client-supplied practice_id.
    result = await db.execute(select(User).where(User.clerk_id == user.get("sub")))
    local_user = result.scalar_one_or_none()

    # Self-heal a reissued Clerk `sub` (a dev-instance reset / reinstall gives
    # every account a NEW id while emails stay stable). When no row matches
    # the sub, re-link by email so the existing practice account keeps working
    # instead of 401-ing until manually re-provisioned.
    #
    # SECURITY: for a self-apply sign-up (doctor/staff), the Clerk account
    # carries unsafe_metadata.practice_id stamped from the practice's signup
    # code (see DoctorApplyPage/StaffApplyPage). The relink MUST be scoped to
    # THAT practice — a bare email-match across ALL practices could silently
    # adopt an unrelated account (even an Owner at another practice) and hand
    # this session the foreign account's role/access, which is exactly the
    # "new signup ends up in someone else's Owner dashboard" bug (found live:
    # a plain /sign-up with no metadata fell into the any-practice fallback
    # below and got relinked to an unrelated existing Owner row). Only when NO
    # self-apply metadata exists (a normal existing account, e.g. an Owner
    # surviving a dev-instance reset) does the any-practice email fallback
    # apply — and even then, ONLY if the email is unambiguous (exactly one
    # User row across the whole table). If it matches more than one row across
    # different practices, we cannot know which account this session should
    # become, so we refuse rather than guess.
    if local_user is None:
        full_user = None
        email = (user.get("email") or "").strip().lower()
        if not email:
            full_user = await ClerkService().get_user(user.get("sub"))
            if full_user:
                addrs = full_user.get("email_addresses") or []
                email = addrs[0]["email_address"].strip().lower() if addrs else ""

        target_practice_id: UUID | None = None
        unsafe_metadata: dict = {}
        if full_user is None and email:
            # Metadata only lives on the Clerk Backend API, never in the
            # session JWT — fetch it so we can scope the relink below.
            full_user = await ClerkService().get_user(user.get("sub"))
        if full_user:
            unsafe_metadata = full_user.get("unsafe_metadata") or {}
        raw_practice_id = (
            unsafe_metadata.get("practice_id")
            if unsafe_metadata.get("invite_type") in ("doctor_self_apply", "staff_self_apply")
            else None
        )
        if raw_practice_id is not None:
            try:
                target_practice_id = UUID(raw_practice_id)
            except (ValueError, TypeError):
                target_practice_id = None

        if email and target_practice_id is not None:
            result = await db.execute(
                select(User).where(func.lower(User.email) == email, User.practice_id == target_practice_id)
            )
            local_user = result.scalar_one_or_none()
            if local_user is not None:
                local_user.clerk_id = user.get("sub")
                await db.flush()
        elif email:
            result = await db.execute(select(User).where(func.lower(User.email) == email))
            matches = list(result.scalars().all())
            if len(matches) == 1:
                local_user = matches[0]
                local_user.clerk_id = user.get("sub")
                await db.flush()
            elif len(matches) > 1:
                raise UnauthorizedException(
                    "Multiple accounts share this email across different practices — "
                    "ask your practice owner to help you sign back in."
                )

    if local_user is None:
        raise UnauthorizedException("No practice account found for this Clerk user")
    if not local_user.is_active:
        raise UnauthorizedException("This account has been deactivated")

    # Self-heal platform-admin status from the bootstrap allowlist — mirrors
    # AgentCostingService's "self-seeding on first read" pattern. Only ever
    # promotes (never demotes here); once at least one admin exists, further
    # promotions happen from the admin panel itself, not this list.
    settings = get_settings()
    admin_emails = {e.strip().lower() for e in settings.platform_admin_emails.split(",") if e.strip()}
    if local_user.email.lower() in admin_emails and not local_user.is_platform_admin:
        local_user.is_platform_admin = True
        await db.flush()

    return local_user


async def resolve_self_apply_practice_id(db: AsyncSession, user: User) -> UUID:
    """Authoritative practice for a doctor/receptionist self-application.

    The apply forms (DoctorApplyPage/StaffApplyPage) validate the practice's
    signup code and stamp the resulting practice_id into Clerk's
    unsafe_metadata at sign-up. A User row can carry a STALE practice_id from
    earlier relink bugs (email adopted an unrelated account, or the row was
    created before the practice-scoped fixes), which files the pending
    application under the wrong practice — so the intended Owner's Doctor/
    Staff Requests page never shows it (found live: application INSERT at
    e43f114a... while the Owner filtered on 4d1123f3...).

    Called at application SUBMIT time (the one moment the applicant is
    re-authorizing their intent): re-reads the Clerk metadata, and if it
    identifies a self-apply signup at a DIFFERENT practice than the row's,
    heals the User row (practice_id + role) and returns the true practice so
    the application lands where the Owner can see and approve it. When no
    self-apply metadata is available the row is left untouched.
    """
    try:
        full_user = await ClerkService().get_user(user.clerk_id)
        unsafe_metadata = (full_user or {}).get("unsafe_metadata") or {}
    except Exception:
        unsafe_metadata = {}

    invite_type = unsafe_metadata.get("invite_type")
    if invite_type not in ("doctor_self_apply", "staff_self_apply"):
        return user.practice_id

    raw_practice_id = unsafe_metadata.get("practice_id")
    try:
        target_practice_id = UUID(raw_practice_id)
    except (ValueError, TypeError):
        return user.practice_id

    desired_role = UserRole.DOCTOR if invite_type == "doctor_self_apply" else UserRole.RECEPTIONIST
    if user.practice_id != target_practice_id or user.role != desired_role:
        user.practice_id = target_practice_id
        user.role = desired_role
        await db.flush()

    return target_practice_id


async def get_current_user_record(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Like get_current_practice_user, but deliberately skips the is_active
    # check — used by the doctor AND receptionist self-application endpoints,
    # where the applicant's User row is intentionally created inactive (see
    # the user.created webhook's doctor_self_apply / staff_self_apply
    # branches) until an Owner approves them. Every other practice-scoped
    # endpoint should keep using get_current_practice_user instead.
    result = await db.execute(select(User).where(User.clerk_id == user.get("sub")))
    local_user = result.scalar_one_or_none()

    # Self-heal for a fresh self-apply sign-up (doctor or receptionist) whose
    # user.created webhook never arrived (Clerk can't POST to 127.0.0.1 — the
    # normal case in local dev). Fetch the full Clerk user to get both the
    # email AND the unsafe_metadata.practice_id the apply form set at sign-up
    # (see DoctorApplyPage.tsx / StaffApplyPage.tsx's
    # <SignUp unsafeMetadata={{practice_id, ...}}>) — the same field the
    # webhook's own self-apply branches trust.
    #
    # A bare email-match here (this function's earlier behavior) is WRONG:
    # if that email already belongs to an unrelated existing account at a
    # DIFFERENT practice (e.g. someone who is already an Owner elsewhere, or
    # a Doctor at another clinic), it silently re-used THAT account's
    # practice_id — so the application got filed under the wrong practice
    # and never showed up in the intended Owner's Doctor Requests list. Real
    # bug, found live. Fixed by scoping the email-match to the SAME target
    # practice, and creating a fresh inactive Doctor row (mirroring the
    # webhook's own doctor_self_apply branch exactly) when no such row
    # exists yet, rather than adopting an unrelated account.
    if local_user is None:
        full_user = await ClerkService().get_user(user.get("sub"))
        email = (user.get("email") or "").strip().lower()
        unsafe_metadata: dict = {}
        if full_user:
            unsafe_metadata = full_user.get("unsafe_metadata") or {}
            if not email:
                addrs = full_user.get("email_addresses") or []
                email = addrs[0]["email_address"].strip().lower() if addrs else ""

        target_practice_id: UUID | None = None
        raw_practice_id = (
            unsafe_metadata.get("practice_id")
            if unsafe_metadata.get("invite_type") in ("doctor_self_apply", "staff_self_apply")
            else None
        )
        if raw_practice_id:
            try:
                target_practice_id = UUID(raw_practice_id)
            except (ValueError, TypeError):
                target_practice_id = None
        self_apply_role = (
            UserRole.DOCTOR if unsafe_metadata.get("invite_type") == "doctor_self_apply" else UserRole.RECEPTIONIST
        )

        if email and target_practice_id is not None:
            # Re-signup for the SAME intended practice (e.g. a dev-instance
            # reset reissuing Clerk ids) — relink rather than duplicate.
            result = await db.execute(
                select(User).where(func.lower(User.email) == email, User.practice_id == target_practice_id)
            )
            local_user = result.scalar_one_or_none()
            if local_user is not None:
                local_user.clerk_id = user.get("sub")
                await db.flush()
            else:
                name = (full_user or {}).get("first_name", "") + " " + (full_user or {}).get("last_name", "") if full_user else ""
                local_user = User(
                    clerk_id=user.get("sub"),
                    practice_id=target_practice_id,
                    email=email,
                    name=name.strip(),
                    role=self_apply_role,
                    is_active=False,
                )
                db.add(local_user)
                await db.flush()
        elif email:
            # Not a self-apply signup (or metadata unavailable) — fall
            # back to the original any-practice email match, same safety
            # net get_current_practice_user uses for a reissued sub on an
            # already-existing account. Same ambiguity guard as there: only
            # relink when the email is unambiguous.
            result = await db.execute(select(User).where(func.lower(User.email) == email))
            matches = list(result.scalars().all())
            if len(matches) == 1:
                local_user = matches[0]
                local_user.clerk_id = user.get("sub")
                await db.flush()
            elif len(matches) > 1:
                raise UnauthorizedException(
                    "Multiple accounts share this email across different practices — "
                    "ask your practice owner to help you sign back in."
                )

    if local_user is None:
        raise UnauthorizedException("No account found for this Clerk user")
    return local_user


async def require_platform_admin(local_user: User = Depends(get_current_practice_user)) -> User:
    if not local_user.is_platform_admin:
        raise ForbiddenException("Platform admin access required.")
    return local_user


def require_role(*roles: UserRole):
    """Dependency factory gating an endpoint to specific practice roles —
    e.g. Depends(require_role(UserRole.OWNER)) for owner-only actions."""

    async def _check(local_user: User = Depends(get_current_practice_user)) -> User:
        if local_user.role not in roles:
            raise ForbiddenException("You don't have permission to perform this action.")
        return local_user

    return _check


portal_auth_service = PatientPortalAuthService()


async def get_current_portal_patient(
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> Patient:
    # The Patient Portal's own auth surface — a self-issued JWT from a
    # portal_id+PIN login (see patient_portal_auth_service.py), completely
    # separate from Clerk. Every /patient-portal/me* endpoint depends on
    # this instead of get_current_practice_user.
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.replace("Bearer ", "")
    patient_id = portal_auth_service.verify_token(token)

    result = await db.execute(select(Patient).where(Patient.id == patient_id))
    patient = result.scalar_one_or_none()
    if patient is None or not patient.portal_enabled:
        raise UnauthorizedException("Invalid or expired session — please log in again")
    return patient


@dataclass
class AdminPrincipal:
    username: str


async def require_admin_token(authorization: str = Header(default="")) -> AdminPrincipal:
    # The platform admin panel's real gate — a standalone username/password +
    # JWT login (POST /api/v1/admin/auth/login, admin_auth_service.py),
    # deliberately independent of Clerk (require_platform_admin above is the
    # earlier Clerk-based mechanism; kept for reference/future multi-admin
    # use, but every /admin/* route now depends on THIS instead).
    if not authorization.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid authorization header")
    token = authorization.replace("Bearer ", "")
    payload = verify_admin_token(token)
    if payload is None:
        raise UnauthorizedException("Invalid or expired admin token")
    return AdminPrincipal(username=payload["sub"])


@dataclass
class PracticeContext:
    user: User
    practice: Practice
    tier: SubscriptionTier


async def get_current_practice_context(
    local_user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
) -> PracticeContext:
    # get_current_practice_user only resolves Clerk -> local User — nothing
    # attaches the practice's plan tier. Real enforcement (require_plan_feature
    # below) needs this, not just the frontend's presentation-only gating in
    # app/dashboard/plan/.
    practice_service = PracticeService()
    practice = await practice_service.get_practice(db, local_user.practice_id)
    if practice is None:
        raise UnauthorizedException("Practice not found for this account")
    # A Super Admin-suspended practice (see admin_services.py) must lose
    # dashboard access immediately, not just stop showing in admin listings —
    # every practice-scoped endpoint routes through here, so this is the one
    # real enforcement point. PENDING_APPROVAL never reaches this function in
    # practice (no User row exists for an org-request until approval creates
    # one), but the check is written to cover both non-ACTIVE states in case
    # that ever changes.
    if practice.status != PracticeStatus.ACTIVE:
        raise ForbiddenException(
            "This practice's access has been suspended. Contact Aiaceone support."
            if practice.status == PracticeStatus.SUSPENDED
            else "This practice is still awaiting approval."
        )
    tier = await practice_service.tier_for(db, practice.id)
    return PracticeContext(user=local_user, practice=practice, tier=tier)


def require_plan_feature(feature: str):
    """Dependency factory — currently only 'analytics' is a plain feature
    flag (mirrors dashboard/plan/planCapabilities.ts's FeatureKey). Agent
    access is gated separately via require_agent_category/require_agent."""

    async def _check(
        ctx: PracticeContext = Depends(get_current_practice_context),
        db: AsyncSession = Depends(get_db),
    ) -> PracticeContext:
        if feature == "analytics" and not await plan_service.has_analytics(db, ctx.tier):
            raise ForbiddenException(f"Analytics requires the Practice plan or higher — you're on {ctx.tier.value}.")
        return ctx

    return _check


def require_agent_category(category_id: str):
    async def _check(
        ctx: PracticeContext = Depends(get_current_practice_context),
        db: AsyncSession = Depends(get_db),
    ) -> PracticeContext:
        if not await plan_service.allows_category(db, ctx.tier, category_id):
            raise ForbiddenException(f"This agent category isn't included in your {ctx.tier.value} plan.")
        return ctx

    return _check


def require_agent(agent_slug: str):
    async def _check(
        ctx: PracticeContext = Depends(get_current_practice_context),
        db: AsyncSession = Depends(get_db),
    ) -> PracticeContext:
        if not await plan_service.allows_agent(db, ctx.tier, agent_slug):
            raise ForbiddenException(f"This agent isn't included in your {ctx.tier.value} plan.")
        return ctx

    return _check
