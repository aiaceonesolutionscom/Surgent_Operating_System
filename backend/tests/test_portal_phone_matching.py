"""Patient-portal login identifies a patient by phone number.

The lookup used to compare `digits[-10:]` with `endswith`, so a login attempt
with no digits ("abc") produced an empty suffix that matched EVERY portal
patient on the platform - and PIN guessing could then run against all of them
at once. Junk or too-short input must find nobody.
"""

import pytest
from pydantic import ValidationError

from src.schemas.patient_portal import PinLoginRequest, RequestOtpRequest, VerifyOtpRequest
from src.services.patient_portal.patient_portal_auth_service import PatientPortalAuthService, phone_key
from tests.conftest import make_patient, make_practice


async def _portal_patients(db_session):
    practice = make_practice(name="Portal Clinic")
    db_session.add(practice)
    await db_session.flush()
    alice = make_patient(practice, first_name="Alice", phone="+92 300 1234567", portal_enabled=True)
    bob = make_patient(practice, first_name="Bob", phone="0321-7654321", portal_enabled=True)
    carol = make_patient(practice, first_name="Carol", phone="0300 1234567", portal_enabled=False)
    db_session.add_all([alice, bob, carol])
    await db_session.flush()
    return alice, bob


@pytest.mark.parametrize("junk", ["abc", "", "   ", "+-()", "12", "1234567"])
async def test_junk_or_short_input_matches_nobody(db_session, junk):
    await _portal_patients(db_session)
    assert await PatientPortalAuthService()._find_patients_by_phone(db_session, junk) == []


@pytest.mark.parametrize("typed", ["+923001234567", "0300 123 4567", "(0300) 1234567", "300-1234567"])
async def test_any_formatting_of_the_same_number_finds_the_patient(db_session, typed):
    alice, _ = await _portal_patients(db_session)
    found = await PatientPortalAuthService()._find_patients_by_phone(db_session, typed)
    assert [p.id for p in found] == [alice.id]


async def test_patients_without_portal_access_are_never_returned(db_session):
    await _portal_patients(db_session)  # Carol shares Alice's number but has no portal access
    found = await PatientPortalAuthService()._find_patients_by_phone(db_session, "03001234567")
    assert {p.first_name for p in found} == {"Alice"}


def test_formatting_variants_share_one_rate_limit_key():
    assert phone_key("+92 300 1234567") == phone_key("0300-1234567") == phone_key("3001234567")


@pytest.mark.parametrize("model,extra", [(RequestOtpRequest, {}), (VerifyOtpRequest, {"code": "123456"}), (PinLoginRequest, {"pin": "123456"})])
def test_request_schemas_reject_a_phone_without_digits(model, extra):
    with pytest.raises(ValidationError):
        model(phone="abc", **extra)
    model(phone="+92 300 1234567", **extra)
