"""Consent immutability: a signed document must stay signed, verbatim.

A signed consent is a legal artifact. Once the patient has signed, the words
they agreed to are frozen - editing the body, re-signing over a changed
document, or signing a voided one would all undermine the consent record. The
PDF is rendered from a snapshot for the same reason.

These tests pin the guard rails in ConsentService so a future refactor cannot
quietly reopen them.
"""

import pytest

from src.models.consent_document import ConsentDocument, ConsentDocumentStatus
from src.server.exceptions import AppException
from tests.conftest import make_patient, make_practice

DOC_TYPE = "surgical"


async def _seed(db_session, status: ConsentDocumentStatus = ConsentDocumentStatus.DRAFT):
    practice = make_practice(name="Consent Clinic")
    db_session.add(practice)
    await db_session.flush()

    patient = make_patient(practice)
    db_session.add(patient)
    await db_session.flush()

    document = ConsentDocument(
        practice_id=practice.id,
        patient_id=patient.id,
        document_type=DOC_TYPE,
        content="Original consent wording the patient agreed to.",
        status=status,
    )
    db_session.add(document)
    await db_session.flush()
    return practice, patient, document


async def test_signing_stamps_the_signature(db_session):
    from src.services.consent.consent_services import ConsentService

    practice, _, document = await _seed(db_session)

    signed = await ConsentService().sign_document(
        db_session, practice.id, document.id, "Alice Patient", None
    )
    assert signed.status == ConsentDocumentStatus.SIGNED
    assert signed.signed_by_name == "Alice Patient"
    assert signed.signed_at is not None


async def test_cannot_sign_twice(db_session):
    """The core immutability rule: a signed document is closed."""
    from src.services.consent.consent_services import ConsentService

    practice, _, document = await _seed(db_session)
    service = ConsentService()

    await service.sign_document(db_session, practice.id, document.id, "Alice Patient", None)

    with pytest.raises(AppException, match="already signed"):
        await service.sign_document(
            db_session, practice.id, document.id, "Someone Else", None
        )

    await db_session.refresh(document)
    assert document.signed_by_name == "Alice Patient", "second signature overwrote the first"


async def test_cannot_sign_a_voided_document(db_session):
    from src.services.consent.consent_services import ConsentService

    practice, _, document = await _seed(db_session, status=ConsentDocumentStatus.VOID)

    with pytest.raises(AppException, match="voided"):
        await ConsentService().sign_document(
            db_session, practice.id, document.id, "Alice Patient", None
        )

    await db_session.refresh(document)
    assert document.status == ConsentDocumentStatus.VOID
    assert document.signed_at is None


async def test_signature_is_tenant_scoped(db_session):
    """Clinic A must not be able to sign clinic B's consent document."""
    from src.services.consent.consent_services import ConsentService
    from src.server.exceptions import NotFoundException

    _, _, document = await _seed(db_session)

    other_clinic = make_practice(name="Other Clinic")
    db_session.add(other_clinic)
    await db_session.flush()

    with pytest.raises(NotFoundException):
        await ConsentService().sign_document(
            db_session, other_clinic.id, document.id, "Mallory", None
        )

    await db_session.refresh(document)
    assert document.status == ConsentDocumentStatus.DRAFT
    assert document.signed_by_name is None


async def test_void_after_signing_moves_status_not_content(db_session):
    """Voiding is the only legal exit from SIGNED, and it must not rewrite text."""
    from src.services.consent.consent_services import ConsentService

    practice, _, document = await _seed(db_session)
    service = ConsentService()
    original_content = document.content

    await service.sign_document(db_session, practice.id, document.id, "Alice Patient", None)
    voided = await service.void_document(db_session, practice.id, document.id)

    assert voided.status == ConsentDocumentStatus.VOID
    assert voided.content == original_content
    assert voided.signed_by_name == "Alice Patient", "voiding must not erase who signed"
    assert voided.signed_at is not None, "voiding must not erase when they signed"


async def test_consent_status_reflects_signed_documents(db_session):
    """Patient.consent_status is a derived bool, so a signed doc must flip it."""
    from src.services.consent.consent_services import ConsentService

    practice, patient, document = await _seed(db_session)
    assert patient.consent_status is False

    await ConsentService().sign_document(
        db_session, practice.id, document.id, "Alice Patient", None
    )
    await db_session.refresh(patient)
    assert patient.consent_status is True
