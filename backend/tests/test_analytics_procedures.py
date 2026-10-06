"""AnalyticsService procedure analytics — the CASE-expression regression.

`get_procedure_analytics` used `func.case(..., else_=0)`. `func.case` builds a
*generic SQL function* call, which does not accept SQLAlchemy's `else_` keyword
argument, so the query raised

    TypeError: Function.__init__() got an unexpected keyword argument 'else_'

at query-CONSTRUCTION time — before any SQL was sent. Every request to
GET /api/v1/analytics/procedures therefore died as a 500 "Internal server
error", and no test noticed because nothing called this method.

The fix is `sqlalchemy.case`. These tests exist so the wrong spelling cannot
come back unnoticed, and so the revenue maths it computes are actually pinned
down rather than assumed.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.models.procedure import Procedure
from src.models.treatment_plan import (
    TreatmentPlan,
    TreatmentPlanItem,
    TreatmentPlanItemStatus,
)
from src.services.analytics.analytics_services import AnalyticsService
from tests.conftest import make_doctor, make_patient, make_practice


async def _seed_procedure_data(db_session):
    """One practice, one doctor, one patient, two procedures and a treatment
    plan covering both — enough for every branch of the aggregation."""
    practice = make_practice(name="Analytics Clinic")
    db_session.add(practice)
    await db_session.flush()

    doctor = make_doctor(practice)
    patient = make_patient(practice)
    db_session.add_all([doctor, patient])
    await db_session.flush()

    filler = Procedure(practice_id=practice.id, name="Hyaluronic Filler")
    laser = Procedure(practice_id=practice.id, name="Laser Resurfacing")
    db_session.add_all([filler, laser])
    await db_session.flush()

    plan = TreatmentPlan(
        practice_id=practice.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        title="Combined plan",
    )
    db_session.add(plan)
    await db_session.flush()

    # Filler: two items, both COMPLETED — one priced by actual_price, one
    # falling back to estimated_price (the COALESCE branch).
    db_session.add_all([
        TreatmentPlanItem(
            treatment_plan_id=plan.id,
            procedure_id=filler.id,
            status=TreatmentPlanItemStatus.COMPLETED,
            estimated_price=Decimal("5000.00"),
            actual_price=Decimal("5500.00"),
        ),
        TreatmentPlanItem(
            treatment_plan_id=plan.id,
            procedure_id=filler.id,
            status=TreatmentPlanItemStatus.COMPLETED,
            estimated_price=Decimal("2500.00"),
            actual_price=None,
        ),
        # Laser: one COMPLETED, one still PLANNED. The PLANNED item must count
        # as a proposal but contribute nothing to revenue or the completed count.
        TreatmentPlanItem(
            treatment_plan_id=plan.id,
            procedure_id=laser.id,
            status=TreatmentPlanItemStatus.COMPLETED,
            estimated_price=Decimal("20000.00"),
            actual_price=Decimal("18000.00"),
        ),
        TreatmentPlanItem(
            treatment_plan_id=plan.id,
            procedure_id=laser.id,
            status=TreatmentPlanItemStatus.PLANNED,
            estimated_price=Decimal("20000.00"),
            actual_price=None,
        ),
    ])
    await db_session.flush()
    return practice


def _window():
    end = date.today()
    return end - timedelta(days=365), end


@pytest.mark.asyncio
async def test_procedure_analytics_builds_and_aggregates(db_session):
    """The regression itself: this used to raise TypeError before running."""
    practice = await _seed_procedure_data(db_session)
    start, end = _window()

    rows = await AnalyticsService().get_procedure_analytics(db_session, practice.id, start, end)

    by_name = {row.name: row for row in rows}
    assert set(by_name) == {"Hyaluronic Filler", "Laser Resurfacing"}

    # 5500 actual + 2500 estimated (no actual → falls back) = 8000
    assert by_name["Hyaluronic Filler"].completed == 2
    assert by_name["Hyaluronic Filler"].proposals == 2
    assert by_name["Hyaluronic Filler"].revenue == 8000.0

    # One of the two laser items is still PLANNED, so it is a proposal but not
    # revenue. This is the whole point of the CASE expressions: counting every
    # row as revenue would have told the clinic it earned 58000 when it earned
    # 26000.
    assert by_name["Laser Resurfacing"].proposals == 2
    assert by_name["Laser Resurfacing"].completed == 1
    assert by_name["Laser Resurfacing"].revenue == 18000.0


@pytest.mark.asyncio
async def test_procedure_analytics_is_empty_not_broken_for_a_new_clinic(db_session):
    """A freshly-provisioned org has no procedures; that must be an empty list,
    not a 500. This is the state every free org-request approval starts in."""
    practice = make_practice(name="Brand New Clinic")
    db_session.add(practice)
    await db_session.flush()
    start, end = _window()

    rows = await AnalyticsService().get_procedure_analytics(db_session, practice.id, start, end)

    assert rows == []


@pytest.mark.asyncio
async def test_procedure_analytics_excludes_other_practices(db_session):
    """Clinic B must never see clinic A's procedure revenue."""
    clinic_a = await _seed_procedure_data(db_session)

    clinic_b = make_practice(name="Other Clinic")
    db_session.add(clinic_b)
    await db_session.flush()
    start, end = _window()

    rows = await AnalyticsService().get_procedure_analytics(db_session, clinic_b.id, start, end)

    assert rows == []
    assert clinic_a.id != clinic_b.id
