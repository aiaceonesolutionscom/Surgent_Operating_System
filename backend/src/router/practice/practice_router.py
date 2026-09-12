from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.schemas.practice import (
    PracticeMeResponse,
    UpdatePracticeRequest,
    ClaimPlanRequest,
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
from src.controller.practice.practice_controllers import PracticeController
from src.server.dependencies import get_current_practice_context, get_current_user, PracticeContext
from src.server.exceptions import ForbiddenException
from src.models.user import UserRole

router = APIRouter(prefix="/practice", tags=["Practice"])
controller = PracticeController()


@router.get("/me", response_model=PracticeMeResponse)
async def get_me(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_me(db, ctx)


@router.patch("/me", response_model=PracticeMeResponse)
async def update_me(
    body: UpdatePracticeRequest,
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_me(db, ctx, body)


@router.get("/doctor-signup-code", response_model=DoctorSignupCodeResponse)
async def get_doctor_signup_code(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can view the doctor signup link.")
    return await controller.get_doctor_signup_code(db, ctx)


@router.post("/doctor-signup-code/regenerate", response_model=DoctorSignupCodeResponse)
async def regenerate_doctor_signup_code(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can regenerate the doctor signup link.")
    return await controller.regenerate_doctor_signup_code(db, ctx)


@router.get("/validate-doctor-code", response_model=ValidateDoctorCodeResponse)
async def validate_doctor_code(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Deliberately public/unauthenticated — a prospective doctor needs to
    # confirm the link is valid (and see which practice it's for) before
    # they've created any account at all.
    return await controller.validate_doctor_code(db, code)


@router.get("/staff-signup-code", response_model=DoctorSignupCodeResponse)
async def get_staff_signup_code(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can view the staff signup link.")
    return await controller.get_staff_signup_code(db, ctx)


@router.post("/staff-signup-code/regenerate", response_model=DoctorSignupCodeResponse)
async def regenerate_staff_signup_code(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can regenerate the staff signup link.")
    return await controller.regenerate_staff_signup_code(db, ctx)


@router.get("/validate-staff-code", response_model=ValidateDoctorCodeResponse)
async def validate_staff_code(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Public/unauthenticated for the same reason as validate-doctor-code — a
    # prospective receptionist confirms the link before having any account.
    return await controller.validate_staff_code(db, code)


@router.post("/claim", response_model=ClaimPlanResponse)
async def claim_plan(
    body: ClaimPlanRequest,
    # Deliberately get_current_user, not get_current_practice_context — at
    # claim time no local User row exists yet (that's what this endpoint creates).
    clerk_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.claim(db, clerk_user, body.session_id)


@router.get("/settings/green-api", response_model=GreenApiSettingsResponse)
async def get_green_api_settings(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can view WhatsApp connection settings.")
    return await controller.get_green_api_settings(db, ctx)


@router.patch("/settings/green-api", response_model=GreenApiSettingsResponse)
async def update_green_api_settings(
    body: UpdateGreenApiSettingsRequest,
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can connect WhatsApp.")
    return await controller.update_green_api_settings(db, ctx, body)


@router.delete("/settings/green-api", status_code=204)
async def disconnect_green_api(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can disconnect WhatsApp.")
    await controller.disconnect_green_api(db, ctx)


@router.get("/settings/meta", response_model=MetaSettingsResponse)
async def get_meta_settings(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can view Instagram/Facebook connection settings.")
    return await controller.get_meta_settings(db, ctx)


@router.get("/settings/meta/connect-url", response_model=MetaConnectUrlResponse)
async def get_meta_connect_url(
    redirect_uri: str = Query(...),
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can connect Instagram/Facebook.")
    return await controller.get_meta_connect_url(db, ctx, redirect_uri)


@router.post("/settings/meta/callback", response_model=MetaSettingsResponse)
async def complete_meta_connect(
    body: MetaCallbackRequest,
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can connect Instagram/Facebook.")
    return await controller.complete_meta_connect(db, ctx, body)


@router.delete("/settings/meta", status_code=204)
async def disconnect_meta(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    if ctx.user.role != UserRole.OWNER:
        raise ForbiddenException("Only the practice owner can disconnect Instagram/Facebook.")
    await controller.disconnect_meta(db, ctx)


@router.post("/request-org", response_model=OrgRequestResponse)
async def submit_org_request(
    body: SubmitOrgRequestRequest,
    # Same reasoning as /claim — a brand-new self-signup has no local User/
    # Practice row yet; this endpoint is what a Super Admin's later approval
    # turns into one (see org_request_service.py, admin_services.py).
    clerk_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.submit_org_request(db, clerk_user, body)


@router.get("/my-org-request", response_model=OrgRequestResponse)
async def get_my_org_request(
    clerk_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_my_org_request(db, clerk_user)
