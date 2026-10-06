"""Per-practice sample ("demo") data: seeding, idempotency, deletion, isolation.

Sample data exists so a clinic owner who came in through the free org-request
path lands on a populated dashboard instead of an empty one
(services/demo/sample_data_service.py). That makes it the one feature where a
scoping bug is a PHI-shaped bug rather than a cosmetic one, so these tests lean
hard on the two properties that must never regress:

  1. ISOLATION — clinic A's demo rows are invisible to, and undeletable by,
     clinic B. Same class of guarantee as tests/test_tenant_isolation.py.
  2. NON-DESTRUCTIVENESS — clearing demo data must never remove a real row.
     The owner is one mis-click away from this, and a real patient's record
     disappearing because someone pressed "delete sample data" is the worst
     failure this feature can produce.

Everything here is DB-backed and therefore skips when PostgreSQL is
unreachable (see conftest.migrated_test_database_url).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from src.models.appointment import Appointment, AppointmentStatus
from src.models.conversation import Conversation
from src.models.expense import Expense
from src.models.inventory_item import InventoryItem
from src.models.message import Message
from src.models.patient import Patient
from src.services.demo.sample_data_service import SampleDataService
from tests.conftest import make_patient, make_practice, make_user


async def _practice_with_owner(db_session, name="Clinic"):
    """A practice plus an owner User.

    The owner is not optional in practice: Expense.recorded_by is NOT NULL, so
    _seed_expenses needs a real user to point at and returns 0 without one.
    Tests that assert on seeded expenses therefore need this.
    """
    practice = make_practice(name=name)
    db_session.add(practice)
    await db_session.flush()
    owner = make_user(practice, role="owner")
    db_session.add(owner)
    await db_session.flush()
    return practice, owner


async def _flagged_count(db_session, model, practice_id):
    """Count sample rows of `model` for one practice."""
    return (
        await db_session.execute(
            select(func.count())
            .select_from(model)
            .where(model.practice_id == practice_id, model.is_sample.is_(True))
        )
    ).scalar_one()


async def _total_count(db_session, model, practice_id):
    return (
        await db_session.execute(
            select(func.count()).select_from(model).where(model.practice_id == practice_id)
        )
    ).scalar_one()


async def _message_count(db_session, practice_id):
    """Messages have no practice_id, so they are counted via their Conversation."""
    return (
        await db_session.execute(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.practice_id == practice_id)
        )
    ).scalar_one()


# ---------------------------------------------------------------- seeding


@pytest.mark.asyncio
async def test_seed_creates_flagged_rows_only(db_session):
    """Everything the seeder writes must be flagged is_sample=True.

    This is the property that makes "delete all sample data" safe, so it is
    asserted directly rather than inferred from the delete tests.
    """
    practice, _ = await _practice_with_owner(db_session)

    await SampleDataService().seed_sample_data(db_session, practice)
    await db_session.flush()

    for model in (Patient, Appointment, Conversation, InventoryItem, Expense):
        total = await _total_count(db_session, model, practice.id)
        flagged = await _flagged_count(db_session, model, practice.id)
        assert total > 0, f"{model.__tablename__} was seeded with nothing to check"
        assert total == flagged, f"a seeded {model.__tablename__} row is missing is_sample=True"


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    """A double-click (or a retried request) must not double the demo data."""
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    first = await service.seed_sample_data(db_session, practice)
    await db_session.flush()
    patients_after_first = await _flagged_count(db_session, Patient, practice.id)

    second = await service.seed_sample_data(db_session, practice)
    await db_session.flush()
    patients_after_second = await _flagged_count(db_session, Patient, practice.id)

    assert second == first
    assert patients_after_second == patients_after_first


@pytest.mark.asyncio
async def test_seed_creates_no_cross_practice_rows(db_session):
    """Seeding clinic A must not create a single row belonging to clinic B."""
    clinic_a, _ = await _practice_with_owner(db_session, name="Clinic A")
    clinic_b, _ = await _practice_with_owner(db_session, name="Clinic B")

    await SampleDataService().seed_sample_data(db_session, clinic_a)
    await db_session.flush()

    for model in (Patient, Appointment, Conversation, InventoryItem, Expense):
        assert await _flagged_count(db_session, model, clinic_b.id) == 0, (
            f"seeding clinic A leaked a {model.__tablename__} row into clinic B"
        )


@pytest.mark.asyncio
async def test_seed_returns_counts_matching_the_database(db_session):
    """The dict handed to the UI must describe what is actually stored."""
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    result = await service.seed_sample_data(db_session, practice)
    await db_session.flush()

    assert result["patients"] == await _flagged_count(db_session, Patient, practice.id)
    assert result["appointments"] == await _flagged_count(db_session, Appointment, practice.id)
    assert result["conversations"] == await _flagged_count(db_session, Conversation, practice.id)
    assert result["inventory_items"] == await _flagged_count(db_session, InventoryItem, practice.id)
    assert result["expenses"] == await _flagged_count(db_session, Expense, practice.id)
    assert result["messages"] == await _message_count(db_session, practice.id)


@pytest.mark.asyncio
async def test_seeded_expenses_are_excluded_from_finance_overview(db_session):
    """Sample expenses must not reach the money aggregates.

    A fabricated burn rate on a prospect's dashboard would read as a real number
    to them, and on a paying customer's own P&L it would be worse. See
    finance_services.get_overview and multiclinic.md §8.4.
    """
    from src.services.finance.finance_services import FinanceService

    practice, _ = await _practice_with_owner(db_session)
    await SampleDataService().seed_sample_data(db_session, practice)
    await db_session.flush()

    assert await _flagged_count(db_session, Expense, practice.id) > 0, "no sample expenses seeded"

    overview = await FinanceService().get_overview(db_session, practice.id)

    assert overview.total_expenses == 0.0
    assert overview.expense_count == 0


@pytest.mark.asyncio
async def test_sample_expenses_are_still_listable_for_deletion(db_session):
    """The owner must be able to SEE demo expenses in order to delete them one
    by one — excluding them from the list as well as the totals would leave the
    rows reachable only via the bulk delete.
    """
    from src.services.finance.finance_services import FinanceService

    practice, _ = await _practice_with_owner(db_session)
    await SampleDataService().seed_sample_data(db_session, practice)
    await db_session.flush()

    listed = await FinanceService().list_expenses(db_session, practice.id)

    assert len(listed) > 0
    assert all(row.is_sample for row in listed)


# --------------------------------------------------------------- isolation


@pytest.mark.asyncio
async def test_clear_does_not_touch_another_practice(db_session):
    """Clinic B calling "delete sample data" must leave clinic A's rows intact."""
    clinic_a, _ = await _practice_with_owner(db_session, name="Clinic A")
    clinic_b, _ = await _practice_with_owner(db_session, name="Clinic B")
    service = SampleDataService()

    await service.seed_sample_data(db_session, clinic_a)
    await db_session.flush()
    patients_before = await _flagged_count(db_session, Patient, clinic_a.id)
    assert patients_before > 0

    removed = await service.clear_sample_data(db_session, clinic_b.id)
    await db_session.flush()

    assert removed["total"] == 0
    assert await _flagged_count(db_session, Patient, clinic_a.id) == patients_before


@pytest.mark.asyncio
async def test_clear_does_not_delete_another_practices_messages(db_session):
    """Messages are the easiest thing to get wrong here: they carry no
    practice_id, so they can only be scoped through their Conversation. Clinic
    B's clear must not reach clinic A's threads."""
    clinic_a, _ = await _practice_with_owner(db_session, name="Clinic A")
    clinic_b, _ = await _practice_with_owner(db_session, name="Clinic B")
    service = SampleDataService()

    await service.seed_sample_data(db_session, clinic_a)
    await db_session.flush()
    messages_before = await _message_count(db_session, clinic_a.id)
    assert messages_before > 0, "no sample messages were seeded"

    await service.clear_sample_data(db_session, clinic_b.id)
    await db_session.flush()

    assert await _message_count(db_session, clinic_a.id) == messages_before


@pytest.mark.asyncio
async def test_counts_are_scoped_to_one_practice(db_session):
    clinic_a, _ = await _practice_with_owner(db_session, name="Clinic A")
    clinic_b, _ = await _practice_with_owner(db_session, name="Clinic B")
    service = SampleDataService()

    await service.seed_sample_data(db_session, clinic_a)
    await db_session.flush()

    counts_a = await service.sample_data_counts(db_session, clinic_a.id)
    counts_b = await service.sample_data_counts(db_session, clinic_b.id)

    assert counts_a["total"] > 0
    assert counts_b["total"] == 0


# ---------------------------------------------------------------- deletion


@pytest.mark.asyncio
async def test_clear_removes_every_sample_row(db_session):
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()

    removed = await service.clear_sample_data(db_session, practice.id)
    await db_session.flush()

    assert removed["total"] > 0
    for model in (Patient, Appointment, Conversation, InventoryItem, Expense):
        assert await _flagged_count(db_session, model, practice.id) == 0, (
            f"{model.__tablename__} survived the clear"
        )


@pytest.mark.asyncio
async def test_clear_removes_sample_messages_without_fk_violation(db_session):
    """Regression guard for the cascade trap.

    clear_sample_data issues a BULK `delete(Conversation)` statement. A bulk
    DELETE bypasses the ORM entirely, so Conversation.messages'
    cascade="all, delete-orphan" does not fire — and messages.conversation_id is
    a plain FK with no ondelete="CASCADE". Relying on the relationship made
    this call raise ForeignKeyViolation on any practice whose threads had
    messages, i.e. every practice that had actually loaded the demo data.
    Messages are therefore deleted explicitly first; this test fails loudly if
    that explicit delete is ever removed.
    """
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()
    assert await _message_count(db_session, practice.id) > 0, "no sample messages seeded"

    await service.clear_sample_data(db_session, practice.id)
    await db_session.flush()

    assert await _message_count(db_session, practice.id) == 0


@pytest.mark.asyncio
async def test_clear_reports_messages_separately_from_total(db_session):
    """`total` means "rows deletable on their own" and must stay comparable to
    sample_data_counts()["total"], which excludes messages for the same reason."""
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()
    counts = await service.sample_data_counts(db_session, practice.id)

    removed = await service.clear_sample_data(db_session, practice.id)

    assert removed["messages"] > 0
    assert removed["total"] == counts["total"]
    assert removed["total"] == sum(
        removed[k]
        for k in ("appointments", "conversations", "inventory_items", "expenses", "patients")
    )


@pytest.mark.asyncio
async def test_clear_never_removes_real_rows(db_session):
    """The headline safety property.

    A real patient, appointment and expense sit alongside the demo data.
    Clearing sample data must leave all three exactly where they were.
    """
    practice, owner = await _practice_with_owner(db_session)
    service = SampleDataService()

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    real_patient = make_patient(practice, first_name="Real", last_name="Patient")
    db_session.add(real_patient)
    await db_session.flush()

    real_appointment = Appointment(
        practice_id=practice.id,
        patient_id=real_patient.id,
        appointment_type="Real consultation",
        status=AppointmentStatus.COMPLETED,
        start_time=now - timedelta(days=1),
        end_time=now - timedelta(days=1, minutes=-30),
    )
    real_expense = Expense(
        practice_id=practice.id,
        expense_type="expense",
        status="paid",
        category="rent",
        amount=Decimal("1000.00"),
        expense_date=date.today(),
        recorded_by=owner.id,
    )
    db_session.add_all([real_appointment, real_expense])
    await db_session.flush()

    await service.clear_sample_data(db_session, practice.id)
    await db_session.flush()

    surviving_patients = (
        await db_session.execute(
            select(func.count())
            .select_from(Patient)
            .where(Patient.id == real_patient.id, Patient.practice_id == practice.id)
        )
    ).scalar_one()
    assert surviving_patients == 1, "clearing sample data deleted a real patient"

    surviving_appointments = (
        await db_session.execute(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.id == real_appointment.id, Appointment.practice_id == practice.id)
        )
    ).scalar_one()
    assert surviving_appointments == 1, "clearing sample data deleted a real appointment"

    surviving_expenses = (
        await db_session.execute(
            select(func.count())
            .select_from(Expense)
            .where(
                Expense.practice_id == practice.id,
                Expense.is_sample.is_(False),
            )
        )
    ).scalar_one()
    assert surviving_expenses == 1, "clearing sample data deleted a real expense"


@pytest.mark.asyncio
async def test_real_rows_survive_and_still_count_in_finance(db_session):
    """After a clear, the real expense is what the P&L reports.

    This is the pairing that matters: the sample data must be invisible to the
    aggregates while it exists, and the real data must be counted normally once
    it is the only thing left.
    """
    from src.services.finance.finance_services import FinanceService

    practice, owner = await _practice_with_owner(db_session)
    service = SampleDataService()

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()

    db_session.add(
        Expense(
            practice_id=practice.id,
            expense_type="expense",
            status="paid",
            category="rent",
            amount=Decimal("1000.00"),
            expense_date=date.today(),
            recorded_by=owner.id,
        )
    )
    await db_session.flush()

    # Before the clear: only the real expense counts.
    before = await FinanceService().get_overview(db_session, practice.id)
    assert before.total_expenses == 1000.0
    assert before.expense_count == 1

    await service.clear_sample_data(db_session, practice.id)
    await db_session.flush()

    # After: unchanged, because the sample rows were never in the total.
    after = await FinanceService().get_overview(db_session, practice.id)
    assert after.total_expenses == 1000.0
    assert after.expense_count == 1


@pytest.mark.asyncio
async def test_clear_on_an_empty_practice_is_a_noop(db_session):
    """Clear must be safe before anything was seeded, and safe to call twice."""
    practice, _ = await _practice_with_owner(db_session)
    service = SampleDataService()

    first = await service.clear_sample_data(db_session, practice.id)
    assert first["total"] == 0

    await service.seed_sample_data(db_session, practice)
    await db_session.flush()

    second = await service.clear_sample_data(db_session, practice.id)
    assert second["total"] > 0

    third = await service.clear_sample_data(db_session, practice.id)
    await db_session.flush()
    assert third["total"] == 0
