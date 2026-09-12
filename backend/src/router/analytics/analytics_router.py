from __future__ import annotations
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import (
    get_current_practice_user,
    require_plan_feature,
    PracticeContext,
)
from src.models.user import User
from src.schemas.analytics import (
    OverviewSummaryResponse,
    SessionAnalyticsResponse,
    RevenueTrendResponse,
    FunnelResponse,
    DoctorPerformanceResponse,
    ProcedureAnalyticsResponse,
    AppointmentAnalyticsResponse,
)
from src.controller.analytics.analytics_controllers import AnalyticsController

router = APIRouter(prefix="/analytics", tags=["Analytics"])
controller = AnalyticsController()


# /overview deliberately has NO require_plan_feature guard: it backs the Owner
# home screen (OverviewPage), which every plan tier must be able to load. The
# plan-gated analytics surface is /sessions (the dedicated Analytics page),
# which the dashboard already hides behind the Practice plan.
@router.get("/overview", response_model=OverviewSummaryResponse)
async def get_overview_summary(
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_overview_summary(db, user)


@router.get("/sessions", response_model=SessionAnalyticsResponse)
async def get_session_analytics(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_session_analytics(db, user)


# --- Reporting endpoints (Practice plan) ---


@router.get("/revenue", response_model=RevenueTrendResponse)
async def get_revenue_trend(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day", pattern="^(day|week|month)$"),
):
    return await controller.get_revenue_trend(db, user, from_date, to_date, group_by)


@router.get("/funnel", response_model=FunnelResponse)
async def get_conversion_funnel(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    return await controller.get_conversion_funnel(db, user, from_date, to_date)


@router.get("/doctors", response_model=list[DoctorPerformanceResponse])
async def get_doctor_performance(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    return await controller.get_doctor_performance(db, user, from_date, to_date)


@router.get("/procedures", response_model=list[ProcedureAnalyticsResponse])
async def get_procedure_analytics(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    return await controller.get_procedure_analytics(db, user, from_date, to_date)


@router.get("/appointments", response_model=AppointmentAnalyticsResponse)
async def get_appointment_analytics(
    _: PracticeContext = Depends(require_plan_feature("analytics")),
    user: User = Depends(get_current_practice_user),
    db: AsyncSession = Depends(get_db),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
):
    return await controller.get_appointment_analytics(db, user, from_date, to_date)