from __future__ import annotations
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationStatus
from src.models.appointment import Appointment, AppointmentStatus
from src.models.treatment_plan import TreatmentPlan, TreatmentPlanItem, TreatmentPlanItemStatus, TreatmentPlanStatus
from src.models.patient import Patient
from src.models.consultation_note import ConsultationNote, ConsultationNoteStatus
from src.models.surgery import Surgery, SurgeryStatus
from src.models.procedure import Procedure
from src.models.doctor import Doctor
from src.models.invoice import Invoice, Payment
from src.services.practice.plan_capabilities import AGENT_CATEGORIES, category_for_agent
from src.schemas.analytics import (
    OverviewSummaryResponse,
    SessionAnalyticsResponse,
    ChannelCount,
    CategoryCount,
    RevenueTrendResponse,
    RevenuePointResponse,
    FunnelResponse,
    FunnelStage,
    DoctorPerformanceResponse,
    ProcedureAnalyticsResponse,
    AppointmentAnalyticsResponse,
)


def _start_of_today() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AnalyticsService:
    """Real aggregate queries over Conversation/Appointment — replaces the
    dashboard's MOCK_SESSIONS-derived numbers. Practice-scoped; callers must
    always pass the requesting user's own practice_id."""

    async def get_overview_summary(self, db: AsyncSession, practice_id: UUID) -> OverviewSummaryResponse:
        today = _start_of_today()
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        sessions_today = await db.scalar(
            select(func.count()).select_from(Conversation).where(
                Conversation.practice_id == practice_id, Conversation.created_at >= today
            )
        )
        needs_attention = await db.scalar(
            select(func.count()).select_from(Conversation).where(
                Conversation.practice_id == practice_id, Conversation.status == ConversationStatus.NEEDS_ATTENTION
            )
        )
        bookings_this_week = await db.scalar(
            select(func.count()).select_from(Appointment).where(
                Appointment.practice_id == practice_id, Appointment.created_at >= week_ago
            )
        )

        # Revenue estimate — decision #4 in the roadmap: real, not a
        # fabricated number. Only counts TreatmentPlanItems actually marked
        # COMPLETED, using the real price actually charged when set,
        # falling back to the plan's estimate otherwise.
        revenue_rows = (
            await db.execute(
                select(TreatmentPlanItem.actual_price, TreatmentPlanItem.estimated_price)
                .join(TreatmentPlan, TreatmentPlanItem.treatment_plan_id == TreatmentPlan.id)
                .where(TreatmentPlan.practice_id == practice_id, TreatmentPlanItem.status == TreatmentPlanItemStatus.COMPLETED)
            )
        ).all()
        priced_rows = [(actual if actual is not None else estimated) for actual, estimated in revenue_rows]
        priced_rows = [p for p in priced_rows if p is not None]
        revenue_estimate = float(sum(priced_rows)) if priced_rows else None

        return OverviewSummaryResponse(
            sessions_today=sessions_today or 0,
            needs_attention=needs_attention or 0,
            bookings_this_week=bookings_this_week or 0,
            revenue_estimate=revenue_estimate,
        )

    async def get_session_analytics(self, db: AsyncSession, practice_id: UUID) -> SessionAnalyticsResponse:
        status_counts = dict(
            (
                await db.execute(
                    select(Conversation.status, func.count())
                    .where(Conversation.practice_id == practice_id)
                    .group_by(Conversation.status)
                )
            ).all()
        )

        channel_rows = (
            await db.execute(
                select(Conversation.channel, func.count())
                .where(Conversation.practice_id == practice_id)
                .group_by(Conversation.channel)
            )
        ).all()
        by_channel = [ChannelCount(channel=channel.value, count=count) for channel, count in channel_rows]

        agent_type_rows = (
            await db.execute(
                select(Conversation.agent_type, func.count())
                .where(Conversation.practice_id == practice_id)
                .group_by(Conversation.agent_type)
            )
        ).all()
        category_totals: dict[str, int] = {cat: 0 for cat in AGENT_CATEGORIES}
        for agent_type, count in agent_type_rows:
            category = category_for_agent(agent_type) or "business"
            category_totals[category] = category_totals.get(category, 0) + count
        by_category = [CategoryCount(category=cat, count=count) for cat, count in category_totals.items()]

        total = sum(status_counts.values())

        return SessionAnalyticsResponse(
            total_conversations=total,
            active_count=status_counts.get(ConversationStatus.ACTIVE, 0),
            needs_attention_count=status_counts.get(ConversationStatus.NEEDS_ATTENTION, 0),
            resolved_count=status_counts.get(ConversationStatus.RESOLVED, 0),
            by_channel=by_channel,
            by_category=by_category,
        )

    # --- Reporting endpoints (Practice plan) ------------------------------

    @staticmethod
    def _window(start_date: date | None, end_date: date | None) -> tuple[datetime, datetime]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        return start_dt, end_dt

    async def get_revenue_trend(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        group_by: str = "day",
    ) -> RevenueTrendResponse:
        """Actual cash in — the sum of recorded Payments (not the completed-
        plan-item estimate /overview uses) bucketed by day/week/month."""
        if group_by not in ("day", "week", "month"):
            raise ValueError("group_by must be 'day', 'week' or 'month'")
        start_dt, end_dt = self._window(start_date, end_date)

        bucket_expr = func.date_trunc(group_by, Payment.paid_at).label("bucket")
        rows = (
            await db.execute(
                select(
                    bucket_expr,
                    func.coalesce(func.sum(Payment.amount), 0).label("revenue"),
                    func.count().label("payments_count"),
                )
                .where(
                    Payment.practice_id == practice_id,
                    Payment.paid_at >= start_dt,
                    Payment.paid_at < end_dt,
                )
                .group_by(bucket_expr)
                .order_by(bucket_expr)
            )
        ).all()

        formats = {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}
        buckets = []
        for bucket, revenue, payments_count in rows:
            buckets.append(
                RevenuePointResponse(
                    bucket=bucket.strftime(formats[group_by]),
                    revenue=float(revenue or 0),
                    payments_count=payments_count,
                )
            )
        return RevenueTrendResponse(total_revenue=float(sum(b.revenue for b in buckets)), buckets=buckets)

    async def get_conversion_funnel(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> FunnelResponse:
        start_dt, end_dt = self._window(start_date, end_date)

        leads = await db.scalar(
            select(func.count(func.distinct(Patient.id))).where(
                Patient.practice_id == practice_id, Patient.created_at >= start_dt, Patient.created_at < end_dt
            )
        )

        bookings = await db.scalar(
            select(func.count(func.distinct(Appointment.patient_id))).where(
                Appointment.practice_id == practice_id,
                Appointment.start_time >= start_dt,
                Appointment.start_time < end_dt,
            )
        )

        consultations = await db.scalar(
            select(func.count(func.distinct(ConsultationNote.patient_id))).where(
                ConsultationNote.practice_id == practice_id,
                ConsultationNote.status == ConsultationNoteStatus.FINAL,
                ConsultationNote.created_at >= start_dt,
                ConsultationNote.created_at < end_dt,
            )
        )

        planned = await db.scalar(
            select(func.count(func.distinct(TreatmentPlan.patient_id))).where(
                TreatmentPlan.practice_id == practice_id,
                TreatmentPlan.status.in_(
                    [TreatmentPlanStatus.PROPOSED, TreatmentPlanStatus.ACCEPTED, TreatmentPlanStatus.COMPLETED]
                ),
                TreatmentPlan.created_at >= start_dt,
                TreatmentPlan.created_at < end_dt,
            )
        )

        operated = await db.scalar(
            select(func.count(func.distinct(Surgery.patient_id))).where(
                Surgery.practice_id == practice_id,
                Surgery.status == SurgeryStatus.COMPLETED,
                Surgery.scheduled_date >= start_dt,
                Surgery.scheduled_date < end_dt,
            )
        )

        paid = await db.scalar(
            select(func.count(func.distinct(Invoice.patient_id)))
            .select_from(Payment)
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .where(
                Payment.practice_id == practice_id,
                Payment.paid_at >= start_dt,
                Payment.paid_at < end_dt,
            )
        )

        stages = [
            FunnelStage(stage="lead", count=leads or 0),
            FunnelStage(stage="booked", count=bookings or 0),
            FunnelStage(stage="consulted", count=consultations or 0),
            FunnelStage(stage="treatment_planned", count=planned or 0),
            FunnelStage(stage="operated", count=operated or 0),
            FunnelStage(stage="paid", count=paid or 0),
        ]
        return FunnelResponse(stages=stages)

    async def get_doctor_performance(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DoctorPerformanceResponse]:
        start_dt, end_dt = self._window(start_date, end_date)

        apt_rows = (
            await db.execute(
                select(
                    Appointment.doctor_id,
                    func.count(),
                    func.count().filter(Appointment.status == AppointmentStatus.COMPLETED),
                )
                .where(
                    Appointment.practice_id == practice_id,
                    Appointment.doctor_id.isnot(None),
                    Appointment.start_time >= start_dt,
                    Appointment.start_time < end_dt,
                )
                .group_by(Appointment.doctor_id)
            )
        ).all()

        rev_rows = (
            await db.execute(
                select(
                    TreatmentPlan.doctor_id,
                    func.coalesce(func.sum(func.coalesce(TreatmentPlanItem.actual_price, TreatmentPlanItem.estimated_price)), 0),
                )
                .join(TreatmentPlanItem, TreatmentPlanItem.treatment_plan_id == TreatmentPlan.id)
                .where(
                    TreatmentPlan.practice_id == practice_id,
                    TreatmentPlan.doctor_id.isnot(None),
                    TreatmentPlanItem.status == TreatmentPlanItemStatus.COMPLETED,
                    TreatmentPlanItem.performed_at >= start_dt,
                    TreatmentPlanItem.performed_at < end_dt,
                )
                .group_by(TreatmentPlan.doctor_id)
            )
        ).all()

        names_result = await db.execute(
            select(Doctor.id, Doctor.name).where(Doctor.practice_id == practice_id)
        )
        name_by_id = {doctor_id: name for doctor_id, name in names_result.all()}
        revenue_by_id = {doctor_id: float(revenue) for doctor_id, revenue in rev_rows}

        results = []
        seen: set[UUID] = set()
        for doctor_id, appointment_count, completed_count in apt_rows:
            if doctor_id is None:
                continue
            seen.add(doctor_id)
            results.append(
                DoctorPerformanceResponse(
                    doctor_id=doctor_id,
                    name=name_by_id.get(doctor_id, "Unknown"),
                    appointment_count=appointment_count,
                    completed_appointments=completed_count,
                    revenue=revenue_by_id.get(doctor_id, 0.0),
                )
            )
        # Doctors with revenue but zero appointments in the window still count.
        for doctor_id, revenue in revenue_by_id.items():
            if doctor_id not in seen:
                results.append(
                    DoctorPerformanceResponse(
                        doctor_id=doctor_id,
                        name=name_by_id.get(doctor_id, "Unknown"),
                        appointment_count=0,
                        completed_appointments=0,
                        revenue=revenue,
                    )
                )
        results.sort(key=lambda r: (r.appointment_count, r.revenue), reverse=True)
        return results

    async def get_procedure_analytics(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ProcedureAnalyticsResponse]:
        start_dt, end_dt = self._window(start_date, end_date)

        completed_case = (TreatmentPlanItem.status == TreatmentPlanItemStatus.COMPLETED, 1)
        rows = (
            await db.execute(
                select(
                    Procedure.id,
                    Procedure.name,
                    func.count(TreatmentPlanItem.id).label("proposals"),
                    func.coalesce(func.sum(func.case(completed_case, else_=0)), 0).label("completed"),
                    func.coalesce(
                        func.sum(
                            func.case(
                                (
                                    TreatmentPlanItem.status == TreatmentPlanItemStatus.COMPLETED,
                                    func.coalesce(TreatmentPlanItem.actual_price, TreatmentPlanItem.estimated_price),
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ).label("revenue"),
                )
                .select_from(TreatmentPlanItem)
                .join(TreatmentPlan, TreatmentPlanItem.treatment_plan_id == TreatmentPlan.id)
                .join(Procedure, TreatmentPlanItem.procedure_id == Procedure.id)
                .where(
                    TreatmentPlan.practice_id == practice_id,
                    TreatmentPlanItem.created_at >= start_dt,
                    TreatmentPlanItem.created_at < end_dt,
                )
                .group_by(Procedure.id, Procedure.name)
                .order_by(func.count(TreatmentPlanItem.id).desc())
            )
        ).all()

        return [
            ProcedureAnalyticsResponse(
                procedure_id=procedure_id,
                name=name,
                proposals=int(proposals),
                completed=int(completed),
                revenue=float(revenue or 0),
            )
            for procedure_id, name, proposals, completed, revenue in rows
        ]

    async def get_appointment_analytics(
        self,
        db: AsyncSession,
        practice_id: UUID,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AppointmentAnalyticsResponse:
        start_dt, end_dt = self._window(start_date, end_date)

        rows = (
            await db.execute(
                select(Appointment.status, func.count())
                .where(
                    Appointment.practice_id == practice_id,
                    Appointment.start_time >= start_dt,
                    Appointment.start_time < end_dt,
                )
                .group_by(Appointment.status)
            )
        ).all()
        status_counts = {status.value: count for status, count in rows}
        total = sum(status_counts.values())
        no_show = status_counts.get(AppointmentStatus.NO_SHOW.value, 0)
        no_show_rate = round(no_show / total, 3) if total else 0.0
        return AppointmentAnalyticsResponse(
            total_appointments=total,
            status_counts=status_counts,
            no_show_count=no_show,
            no_show_rate=no_show_rate,
        )
