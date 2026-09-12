from __future__ import annotations
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

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
from src.services.analytics.analytics_services import AnalyticsService


class AnalyticsController:
    def __init__(self):
        self.service = AnalyticsService()

    async def get_overview_summary(self, db: AsyncSession, user: User) -> OverviewSummaryResponse:
        return await self.service.get_overview_summary(db, user.practice_id)

    async def get_session_analytics(self, db: AsyncSession, user: User) -> SessionAnalyticsResponse:
        return await self.service.get_session_analytics(db, user.practice_id)

    async def get_revenue_trend(
        self,
        db: AsyncSession,
        user: User,
        start_date: date | None,
        end_date: date | None,
        group_by: str,
    ) -> RevenueTrendResponse:
        return await self.service.get_revenue_trend(db, user.practice_id, start_date, end_date, group_by)

    async def get_conversion_funnel(
        self,
        db: AsyncSession,
        user: User,
        start_date: date | None,
        end_date: date | None,
    ) -> FunnelResponse:
        return await self.service.get_conversion_funnel(db, user.practice_id, start_date, end_date)

    async def get_doctor_performance(
        self,
        db: AsyncSession,
        user: User,
        start_date: date | None,
        end_date: date | None,
    ) -> list[DoctorPerformanceResponse]:
        return await self.service.get_doctor_performance(db, user.practice_id, start_date, end_date)

    async def get_procedure_analytics(
        self,
        db: AsyncSession,
        user: User,
        start_date: date | None,
        end_date: date | None,
    ) -> list[ProcedureAnalyticsResponse]:
        return await self.service.get_procedure_analytics(db, user.practice_id, start_date, end_date)

    async def get_appointment_analytics(
        self,
        db: AsyncSession,
        user: User,
        start_date: date | None,
        end_date: date | None,
    ) -> AppointmentAnalyticsResponse:
        return await self.service.get_appointment_analytics(db, user.practice_id, start_date, end_date)