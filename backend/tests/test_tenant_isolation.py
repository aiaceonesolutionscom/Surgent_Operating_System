"""Tenant isolation: one practice must never read or write another's data.

These are the highest-consequence tests in the suite. A missing
`practice_id` filter anywhere in a query is a cross-clinic PHI leak, and it
is the kind of bug that cannot show up in a demo (one practice) but is a
liability the moment a second clinic signs up.

The service layer is where scoping is enforced, so the tests drive the
service directly with an explicit `practice_id` - that is the boundary a
missing filter would break.
"""

import uuid
from decimal import Decimal

import pytest

from tests.conftest import make_patient, make_practice


async def _seed_two_practices(db_session):
    """Clinic A and Clinic B, each with one patient."""
    clinic_a = make_practice(name="Clinic A")
    clinic_b = make_practice(name="Clinic B")
    db_session.add_all([clinic_a, clinic_b])
    await db_session.flush()

    patient_a = make_patient(clinic_a, first_name="Alice", last_name="Aonly")
    patient_b = make_patient(clinic_b, first_name="Bob", last_name="Bonly")
    db_session.add_all([patient_a, patient_b])
    await db_session.flush()
    return clinic_a, clinic_b, patient_a, patient_b


async def test_get_patient_returns_own(db_session):
    from src.services.patients.patients_services import PatientsService

    clinic_a, _, patient_a, _ = await _seed_two_practices(db_session)

    found = await PatientsService().get_patient(db_session, clinic_a.id, patient_a.id)
    assert found.id == patient_a.id
    assert found.first_name == "Alice"


async def test_get_patient_rejects_other_practice(db_session):
    """Guessing a valid UUID from clinic B must not return clinic B's patient."""
    from src.server.exceptions import NotFoundException
    from src.services.patients.patients_services import PatientsService

    clinic_a, _, _, patient_b = await _seed_two_practices(db_session)

    with pytest.raises(NotFoundException):
        await PatientsService().get_patient(db_session, clinic_a.id, patient_b.id)


async def test_list_patients_only_returns_own(db_session):
    from src.services.patients.patients_services import PatientsService

    clinic_a, clinic_b, patient_a, patient_b = await _seed_two_practices(db_session)
    service = PatientsService()

    listed_a = await service.list_patients(db_session, clinic_a.id)
    listed_b = await service.list_patients(db_session, clinic_b.id)

    assert {p.id for p in listed_a} == {patient_a.id}
    assert {p.id for p in listed_b} == {patient_b.id}


async def test_funnel_summary_only_counts_own(db_session):
    """The funnel aggregates counts; a missing filter leaks totals, not rows."""
    from src.services.patients.patients_services import PatientsService

    clinic_a, clinic_b, _, _ = await _seed_two_practices(db_session)
    # Give clinic A a second lead so its funnel has more than one patient.
    db_session.add(make_patient(clinic_a, first_name="Alice2", last_name="Second"))
    await db_session.flush()

    service = PatientsService()
    funnel_a = await service.funnel_summary(db_session, clinic_a.id)
    funnel_b = await service.funnel_summary(db_session, clinic_b.id)

    assert sum(s.count for s in funnel_a) == 2
    assert sum(s.count for s in funnel_b) == 1
    # The shape is stable: every stage present, in funnel order, even at 0.
    assert len(funnel_a) == len(funnel_b)
    assert funnel_a[0].stage == "inquiry"


async def test_update_cannot_reach_across_practices(db_session):
    from src.schemas.patient import UpdatePatientRequest
    from src.server.exceptions import NotFoundException
    from src.services.patients.patients_services import PatientsService

    clinic_a, _, _, patient_b = await _seed_two_practices(db_session)

    with pytest.raises(NotFoundException):
        await PatientsService().update_patient(
            db_session, clinic_a.id, patient_b.id,
            UpdatePatientRequest(first_name="Hijacked"),
        )
    await db_session.refresh(patient_b)
    assert patient_b.first_name == "Bob"


async def test_delete_cannot_reach_across_practices(db_session):
    from src.server.exceptions import NotFoundException
    from src.services.patients.patients_services import PatientsService

    clinic_a, _, _, patient_b = await _seed_two_practices(db_session)

    with pytest.raises(NotFoundException):
        await PatientsService().delete_patient(db_session, clinic_a.id, patient_b.id)
    await db_session.refresh(patient_b)
    assert patient_b.id is not None


async def test_update_stage_cannot_reach_across_practices(db_session):
    from src.server.exceptions import NotFoundException
    from src.services.patients.patients_services import PatientsService

    clinic_a, _, _, patient_b = await _seed_two_practices(db_session)
    original_stage = patient_b.lifecycle_stage

    with pytest.raises(NotFoundException):
        await PatientsService().update_stage(
            db_session, clinic_a.id, patient_b.id, "patient", None
        )
    await db_session.refresh(patient_b)
    assert patient_b.lifecycle_stage == original_stage


async def test_inventory_list_only_own_items(db_session):
    """Inventory is the other PHI-adjacent surface: quantities and unit cost."""
    from src.models.inventory_item import InventoryItem
    from src.services.inventory.inventory_services import InventoryService

    clinic_a = make_practice(name="Clinic A")
    clinic_b = make_practice(name="Clinic B")
    db_session.add_all([clinic_a, clinic_b])
    await db_session.flush()

    item_a = InventoryItem(
        practice_id=clinic_a.id, sku="A-1", name="A implant",
        unit_cost=Decimal("100.00"),
    )
    item_b = InventoryItem(
        practice_id=clinic_b.id, sku="B-1", name="B implant",
        unit_cost=Decimal("500.00"),
    )
    db_session.add_all([item_a, item_b])
    await db_session.flush()

    service = InventoryService()
    listed_a = await service.list_items(db_session, clinic_a.id)
    assert [i.sku for i in listed_a] == ["A-1"]


async def test_inventory_get_rejects_other_practice(db_session):
    from src.models.inventory_item import InventoryItem
    from src.server.exceptions import NotFoundException
    from src.services.inventory.inventory_services import InventoryService

    clinic_a = make_practice(name="Clinic A")
    clinic_b = make_practice(name="Clinic B")
    db_session.add_all([clinic_a, clinic_b])
    await db_session.flush()

    item_b = InventoryItem(practice_id=clinic_b.id, sku="B-1", name="B implant")
    db_session.add(item_b)
    await db_session.flush()

    with pytest.raises(NotFoundException):
        await InventoryService().get_item(db_session, clinic_a.id, item_b.id)


async def test_assign_doctor_cannot_cross_practices(db_session):
    """A doctor from clinic B must not be assignable to a clinic A patient."""
    from src.models.doctor import Doctor
    from src.server.exceptions import NotFoundException
    from src.services.patients.patients_services import PatientsService

    clinic_a = make_practice(name="Clinic A")
    clinic_b = make_practice(name="Clinic B")
    db_session.add_all([clinic_a, clinic_b])
    await db_session.flush()

    patient_a = make_patient(clinic_a)
    doctor_b = Doctor(
        practice_id=clinic_b.id, name="Dr Foreign",
        email=f"{uuid.uuid4().hex[:8]}@test.local",
    )
    db_session.add_all([patient_a, doctor_b])
    await db_session.flush()

    with pytest.raises(NotFoundException):
        await PatientsService().assign_doctor(db_session, clinic_a.id, patient_a.id, doctor_b.id)
    await db_session.refresh(patient_a)
    assert patient_a.assigned_doctor_id is None
