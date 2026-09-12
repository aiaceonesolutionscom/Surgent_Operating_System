from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.pending_signup import PendingSignup
from src.models.doctor import Doctor
from src.models.user import UserRole
from src.schemas.practice import (
    PracticeMeResponse,
    UpdatePracticeRequest,
    ClaimPlanResponse,
    DoctorSignupCodeResponse,
    ValidateDoctorCodeResponse,
    SubmitOrgRequestRequest,
    OrgRequestResponse,
    UpdateGreenApiSettingsRequest,
    GreenApiSettingsResponse,
    MetaSettingsResponse,
    MetaConnectUrlResponse,
    MetaCallbackRequest,
)
from src.services.practice.practice_services import PracticeService
from src.services.checkout.provisioning_service import ProvisioningService
from src.services.practice.org_request_service import OrgRequestService
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI
from src.services.channels.meta_service import MetaService
from src.services.clerk.clerk_service import ClerkService
from src.config import get_settings
from src.server.dependencies import PracticeContext
from src.server.exceptions import NotFoundException, ForbiddenException

settings = get_settings()


class PracticeController:
    def __init__(self):
        self.service = PracticeService()
        self.provisioning = ProvisioningService()
        self.org_requests = OrgRequestService()

    async def submit_org_request(self, db: AsyncSession, clerk_user: dict, body: SubmitOrgRequestRequest) -> OrgRequestResponse:
        clerk_id = clerk_user.get("sub")
        email = (clerk_user.get("email") or "").strip().lower()
        if not email:
            clerk = ClerkService()
            full_user = await clerk.get_user(clerk_id)
            if full_user:
                addrs = full_user.get("email_addresses") or []
                email = addrs[0]["email_address"].strip().lower() if addrs else ""
        pending = await self.org_requests.submit(db, clerk_id, email, body.org_name)
        return OrgRequestResponse.from_model(pending)

    async def get_green_api_settings(self, db: AsyncSession, ctx: PracticeContext) -> GreenApiSettingsResponse:
        config = self.service.get_green_api_config(ctx.practice)
        if config is None:
            return GreenApiSettingsResponse(connected=False)
        client = WhatsAppGreenAPI(config["instance_id"], config["api_token"])
        try:
            state = await client.get_state()
            return GreenApiSettingsResponse(
                connected=state.get("stateInstance") == "authorized",
                instance_id=config["instance_id"],
                state=state.get("stateInstance"),
            )
        except Exception:
            return GreenApiSettingsResponse(connected=False, instance_id=config["instance_id"], error="Couldn't reach Green API right now.")

    async def update_green_api_settings(self, db: AsyncSession, ctx: PracticeContext, body: UpdateGreenApiSettingsRequest) -> GreenApiSettingsResponse:
        client = WhatsAppGreenAPI(body.instance_id, body.api_token)
        try:
            state = await client.get_state()
        except Exception:
            raise ForbiddenException("Couldn't reach Green API with these credentials — check the instance ID and token.")
        if "stateInstance" not in state:
            raise ForbiddenException("Green API rejected these credentials — check the instance ID and token.")

        await self.service.set_green_api_config(db, ctx.practice, body.instance_id, body.api_token)
        if state.get("stateInstance") == "authorized":
            # Incoming messages never reach the poller's queue until this is
            # on (see ensure_incoming_webhook_enabled's docstring) — do it
            # once at connect time instead of relying on someone remembering.
            try:
                await client.ensure_incoming_webhook_enabled()
            except Exception:
                pass
        return GreenApiSettingsResponse(connected=state.get("stateInstance") == "authorized", instance_id=body.instance_id, state=state.get("stateInstance"))

    async def disconnect_green_api(self, db: AsyncSession, ctx: PracticeContext) -> None:
        await self.service.disconnect_green_api(db, ctx.practice)

    async def get_meta_settings(self, db: AsyncSession, ctx: PracticeContext) -> MetaSettingsResponse:
        meta_svc = MetaService()
        config = self.service.get_meta_config(ctx.practice)
        return MetaSettingsResponse(
            configured=meta_svc.is_configured(),
            connected=config is not None,
            page_id=config.get("page_id") if config else None,
            page_name=config.get("page_name") if config else None,
            ig_business_id=config.get("ig_business_id") if config else None,
        )

    async def get_meta_connect_url(self, db: AsyncSession, ctx: PracticeContext, redirect_uri: str) -> MetaConnectUrlResponse:
        meta_svc = MetaService()
        if not meta_svc.is_configured():
            raise ForbiddenException("Instagram/Facebook connection isn't available on this platform yet.")
        state = meta_svc.generate_state()
        return MetaConnectUrlResponse(url=meta_svc.get_oauth_url(redirect_uri, state), state=state)

    async def complete_meta_connect(self, db: AsyncSession, ctx: PracticeContext, body: MetaCallbackRequest) -> MetaSettingsResponse:
        meta_svc = MetaService()
        if not meta_svc.is_configured():
            raise ForbiddenException("Instagram/Facebook connection isn't available on this platform yet.")
        try:
            user_token = await meta_svc.exchange_code_for_user_token(body.code, body.redirect_uri)
            pages = await meta_svc.list_pages(user_token)
        except Exception:
            raise ForbiddenException("Couldn't complete the connection with Meta — please try again.")
        if not pages:
            raise ForbiddenException("No Facebook Page found for this account — connect a Page to Instagram first.")

        # V1: the practice's first/primary Page connects automatically — a
        # picker for Owners managing multiple Pages is a real but separate
        # follow-up once this is validated against a real Facebook App.
        page = pages[0]
        ig_business = (page.get("instagram_business_account") or {}).get("id")
        await self.service.set_meta_config(db, ctx.practice, page["id"], page.get("name", ""), page["access_token"], ig_business)
        try:
            await meta_svc.subscribe_page_webhook(page["id"], page["access_token"])
        except Exception:
            pass
        return await self.get_meta_settings(db, ctx)

    async def disconnect_meta(self, db: AsyncSession, ctx: PracticeContext) -> None:
        await self.service.disconnect_meta(db, ctx.practice)

    async def get_my_org_request(self, db: AsyncSession, clerk_user: dict) -> OrgRequestResponse:
        clerk_id = clerk_user.get("sub")
        try:
            pending = await self.org_requests.get_my_request(db, clerk_id)
        except NotFoundException:
            # Same "webhook can't reach localhost in dev" gap as every other
            # self-apply flow in this codebase — self-heal by checking Clerk's
            # own metadata for the org_request marker (see SignUpPage.tsx's
            # unsafeMetadata) instead of leaving this account stuck with no
            # request and no way to get one, since /org/apply itself only
            # renders the "waiting" state once a row exists.
            full_user = await ClerkService().get_user(clerk_id)
            unsafe_metadata = (full_user or {}).get("unsafe_metadata") or {}
            if unsafe_metadata.get("invite_type") != "org_request":
                raise
            email = (clerk_user.get("email") or "").strip().lower()
            if not email:
                addrs = (full_user or {}).get("email_addresses") or []
                email = addrs[0]["email_address"].strip().lower() if addrs else ""
            pending = await self.org_requests.get_or_create_for_webhook(db, clerk_id, email)
        return OrgRequestResponse.from_model(pending)

    async def get_me(self, db: AsyncSession, ctx: PracticeContext) -> PracticeMeResponse:
        sub = await self.service.active_subscription_for(db, ctx.practice.id)

        permissions: list[str] = []
        if ctx.user.role == UserRole.DOCTOR:
            result = await db.execute(select(Doctor).where(Doctor.user_id == ctx.user.id))
            doctor = result.scalar_one_or_none()
            if doctor is not None:
                permissions = doctor.permissions
        elif ctx.user.role == UserRole.RECEPTIONIST:
            # Lives directly on User (models/user.py), not a separate roster
            # row — see data/receptionist_permissions.py.
            permissions = ctx.user.permissions

        return PracticeMeResponse(
            id=ctx.practice.id,
            name=ctx.practice.name,
            email=ctx.practice.email,
            phone=ctx.practice.phone,
            address=ctx.practice.address,
            timezone=ctx.practice.timezone,
            plan_tier=ctx.tier.value,
            subscription_status=sub.status.value if sub else "trial",
            role=ctx.user.role.value,
            permissions=permissions,
        )

    async def get_doctor_signup_code(self, db: AsyncSession, ctx: PracticeContext) -> DoctorSignupCodeResponse:
        code = await self.service.get_or_create_doctor_signup_code(db, ctx.practice)
        return DoctorSignupCodeResponse(code=code, signup_url=f"{settings.frontend_url}/doctor/apply?code={code}")

    async def regenerate_doctor_signup_code(self, db: AsyncSession, ctx: PracticeContext) -> DoctorSignupCodeResponse:
        code = await self.service.regenerate_doctor_signup_code(db, ctx.practice)
        return DoctorSignupCodeResponse(code=code, signup_url=f"{settings.frontend_url}/doctor/apply?code={code}")

    async def validate_doctor_code(self, db: AsyncSession, code: str) -> ValidateDoctorCodeResponse:
        practice = await self.service.resolve_doctor_signup_code(db, code)
        if practice is None:
            return ValidateDoctorCodeResponse(valid=False)
        return ValidateDoctorCodeResponse(valid=True, practice_id=practice.id, practice_name=practice.name)

    # Receptionists self-register through the SAME share-link mechanism as
    # doctors (see pending_staff_requests / staff-applications), so the Owner
    # gets a parallel staff signup link. Kept as a sibling, not a collapse,
    # because practice.settings holds each code under its own key.
    async def get_staff_signup_code(self, db: AsyncSession, ctx: PracticeContext) -> DoctorSignupCodeResponse:
        code = await self.service.get_or_create_staff_signup_code(db, ctx.practice)
        return DoctorSignupCodeResponse(code=code, signup_url=f"{settings.frontend_url}/staff/apply?code={code}")

    async def regenerate_staff_signup_code(self, db: AsyncSession, ctx: PracticeContext) -> DoctorSignupCodeResponse:
        code = await self.service.regenerate_staff_signup_code(db, ctx.practice)
        return DoctorSignupCodeResponse(code=code, signup_url=f"{settings.frontend_url}/staff/apply?code={code}")

    async def validate_staff_code(self, db: AsyncSession, code: str) -> ValidateDoctorCodeResponse:
        practice = await self.service.resolve_staff_signup_code(db, code)
        if practice is None:
            return ValidateDoctorCodeResponse(valid=False)
        return ValidateDoctorCodeResponse(valid=True, practice_id=practice.id, practice_name=practice.name)

    async def update_me(self, db: AsyncSession, ctx: PracticeContext, body: UpdatePracticeRequest) -> PracticeMeResponse:
        await self.service.update_practice(
            db, ctx.practice, name=body.name, phone=body.phone, address=body.address, timezone=body.timezone
        )
        return await self.get_me(db, ctx)

    async def claim(self, db: AsyncSession, clerk_user: dict, session_id: str) -> ClaimPlanResponse:
        result = await db.execute(select(PendingSignup).where(PendingSignup.stripe_session_id == session_id))
        pending = result.scalar_one_or_none()
        if pending is None:
            raise NotFoundException("No checkout session found for that id.")

        clerk_id = clerk_user.get("sub")
        clerk_email = clerk_user.get("email")
        clerk_name = clerk_user.get("name")

        # Clerk's default session JWT often omits email unless a custom JWT
        # template adds it — fall back to the Backend API for the real address.
        if not clerk_email:
            clerk = ClerkService()
            full_user = await clerk.get_user(clerk_id)
            if full_user:
                addrs = full_user.get("email_addresses") or []
                clerk_email = addrs[0]["email_address"] if addrs else None

        # v1 claim security: the Clerk account claiming this session must
        # match the email that paid — see app/onboarding/README.md for why
        # this is simpler than a signed single-use token, and its limits.
        if clerk_email and clerk_email.lower() != pending.email.lower():
            raise ForbiddenException("This plan was purchased with a different email address.")

        practice = await self.provisioning.provision_from_pending_signup(db, pending, clerk_id, clerk_email, clerk_name)
        return ClaimPlanResponse(practice_id=practice.id, plan_tier=pending.plan_tier)
