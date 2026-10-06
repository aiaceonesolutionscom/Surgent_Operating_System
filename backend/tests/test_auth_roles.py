"""Role authorization: what each of the four roles may see and change.

The role model is Owner / Doctor / Receptionist / Staff, and the rules worth
protecting are not "who can log in" but the two data-scoping rules:

  * **Doctor hard-restriction** - a Doctor may only reach patients assigned
    to them, enforced in `verify_doctor_access`, which every patient-scoped
    controller method is supposed to route through.
  * **Receptionist field redaction** - clinical fields are stripped on read
    and refused on write, while the rest of the roster stays visible.

Both are backend-authoritative: the frontend only reflects them, so if a
guard regresses here the data is already leaked.
"""

import pytest

from src.models.user import UserRole
from tests.conftest import make_doctor, make_patient, make_practice, make_user

CLINICAL_FIELDS = (
    "allergies", "surgical_history", "current_medications",
    "smoking_status", "previous_cosmetic_procedures", "intake_summary",
)


async def _seed(db_session):
    practice = make_practice(name="Roles Clinic")
    db_session.add(practice)
    await db_session.flush()

    doctor_user = make_user(practice, role=UserRole.DOCTOR)
    receptionist = make_user(practice, role=UserRole.RECEPTIONIST)
    owner = make_user(practice, role=UserRole.OWNER)
    db_session.add_all([doctor_user, receptionist, owner])
    await db_session.flush()

    doctor = make_doctor(practice, user=doctor_user)
    db_session.add(doctor)
    await db_session.flush()

    mine = make_patient(practice, first_name="Mine", assigned_doctor_id=doctor.id)
    someone_elses = make_patient(practice, first_name="Theirs")
    db_session.add_all([mine, someone_elses])
    await db_session.flush()

    return {
        "practice": practice, "doctor_user": doctor_user, "doctor": doctor,
        "receptionist": receptionist, "owner": owner,
        "mine": mine, "theirs": someone_elses,
    }


# --- Doctor hard-restriction -------------------------------------------------

async def test_doctor_sees_only_assigned_patients(db_session):
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    listed = await PatientsController().list_patients(db_session, ctx["doctor_user"])

    assert [p.id for p in listed] == [ctx["mine"].id]


async def test_doctor_cannot_open_unassigned_patient(db_session):
    from src.controller.patients.patients_controllers import PatientsController
    from src.server.exceptions import ForbiddenException

    ctx = await _seed(db_session)

    with pytest.raises(ForbiddenException):
        await PatientsController().get_patient(
            db_session, ctx["doctor_user"], ctx["theirs"].id
        )


async def test_doctor_can_open_assigned_patient(db_session):
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    response = await PatientsController().get_patient(
        db_session, ctx["doctor_user"], ctx["mine"].id
    )
    assert response.id == ctx["mine"].id


async def test_owner_reaches_every_practice_patient(db_session):
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    listed = await PatientsController().list_patients(db_session, ctx["owner"])

    assert {p.id for p in listed} == {ctx["mine"].id, ctx["theirs"].id}


# --- Receptionist redaction --------------------------------------------------

async def test_receptionist_sees_clinical_fields_redacted(db_session):
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    ctx["mine"].allergies = [{"substance": "penicillin", "reaction": "rash"}]
    ctx["mine"].smoking_status = "former"
    ctx["mine"].intake_summary = "Sensitive intake notes"
    await db_session.flush()

    response = await PatientsController().get_patient(
        db_session, ctx["receptionist"], ctx["mine"].id
    )

    assert response.allergies == []
    assert response.smoking_status is None
    assert response.intake_summary is None
    # Non-clinical fields still come through, or the receptionist could not work.
    assert response.first_name == "Mine"


async def test_owner_sees_unredacted_clinical_fields(db_session):
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    ctx["mine"].allergies = [{"substance": "penicillin", "reaction": "rash"}]
    await db_session.flush()

    response = await PatientsController().get_patient(
        db_session, ctx["owner"], ctx["mine"].id
    )
    assert response.allergies == [{"substance": "penicillin", "reaction": "rash"}]


async def test_receptionist_cannot_write_clinical_fields(db_session):
    from src.controller.patients.patients_controllers import PatientsController
    from src.schemas.patient import UpdatePatientRequest
    from src.server.exceptions import ForbiddenException

    ctx = await _seed(db_session)
    original = [{"substance": "penicillin", "reaction": "rash"}]
    ctx["mine"].allergies = list(original)
    await db_session.flush()

    with pytest.raises(ForbiddenException):
        await PatientsController().update_patient(
            db_session, ctx["receptionist"], ctx["mine"].id,
            UpdatePatientRequest(allergies=[{"substance": "latex", "reaction": "burn"}]),
        )

    await db_session.refresh(ctx["mine"])
    assert ctx["mine"].allergies == original, "a rejected write must not land"


async def test_receptionist_can_write_non_clinical_fields(db_session):
    from src.controller.patients.patients_controllers import PatientsController
    from src.schemas.patient import UpdatePatientRequest

    ctx = await _seed(db_session)

    response = await PatientsController().update_patient(
        db_session, ctx["receptionist"], ctx["mine"].id,
        UpdatePatientRequest(first_name="Renamed"),
    )
    assert response.first_name == "Renamed"


async def test_every_clinical_field_is_redacted_for_receptionist(db_session):
    """Guards the redaction list itself: a field added to the model but not to
    the redaction map would leak silently."""
    from src.controller.patients.patients_controllers import PatientsController

    ctx = await _seed(db_session)
    sensitive = {"value": "leaky"}
    for field in CLINICAL_FIELDS:
        setattr(
            ctx["mine"], field,
            "leaky" if field in ("smoking_status", "intake_summary") else [sensitive],
        )
    await db_session.flush()

    response = await PatientsController().get_patient(
        db_session, ctx["receptionist"], ctx["mine"].id
    )

    for field in CLINICAL_FIELDS:
        value = getattr(response, field, None)
        assert value in (None, []), f"{field} leaked to a receptionist: {value!r}"
