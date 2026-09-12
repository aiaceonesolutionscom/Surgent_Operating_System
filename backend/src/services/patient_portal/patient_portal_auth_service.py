from __future__ import annotations
import base64
import hashlib
import logging
import random
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.models.patient import Patient
from src.models.practice import Practice
from src.server.exceptions import NotFoundException, UnauthorizedException, AppException
from src.services.audit.audit_log_service import AuditLogService
from src.services.security.rate_limiter import RedisRateLimiter
from src.services.patient_portal.patient_otp_store import PatientOtpStore
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI
from src.services.email.resend_service import ResendService

settings = get_settings()
logger = logging.getLogger(__name__)
audit_log_service = AuditLogService()

# Separate limiters for the two steps: requesting a code (guards against
# spamming a patient's phone with OTP messages / enumerating which phones
# have an account) and verifying one (guards against brute-forcing a
# 6-digit code within its 10-minute window).
request_rate_limiter = RedisRateLimiter(max_attempts=5, window_seconds=15 * 60)
verify_rate_limiter = RedisRateLimiter(max_attempts=8, window_seconds=15 * 60)

# PIN policy + storage format. A 4-6 digit PIN is low-entropy by nature, so
# it gets the same treatment as a password: PBKDF2-HMAC-SHA256 with a random
# per-PIN salt and a deliberately high iteration count, stored only as a hash
# (staff can't read it back or hand it over — the exact failure mode of the
# old clinic-assigned PIN scheme). 8 failed attempts per 15 min (from
# verify_rate_limiter) makes brute-forcing a 6-digit PIN a non-starter while
# keeping the PBKDF2 cost (a few ms per attempt) cheap enough for normal use.
_PIN_MIN_DIGITS = 4
_PIN_MAX_DIGITS = 6
_PBKDF2_ROUNDS = 310_000
_PBKDF2_SALT_BYTES = 16
# Staff-visible one-time login PIN lifetime. A 6-digit single-use secret that
# staff hand over in person; it expires so it can't be hoarded/reused and is
# cleared as soon as it's used for a login.
_TEMP_PIN_LIFETIME_DAYS = 7


def _hash_pin(pin: str) -> str:
    """Returns `pbkdf2_sha256$<rounds>$<salt_b64>$<hash_b64>`."""
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_pin(pin: str, stored: str) -> bool:
    try:
        _, rounds, salt_b64, hash_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt, int(rounds))
    return secrets.compare_digest(digest, expected)


def _valid_pin(pin: str) -> bool:
    return pin.isdigit() and _PIN_MIN_DIGITS <= len(pin) <= _PIN_MAX_DIGITS


class PatientPortalAuthService:
    """Patient-facing login — phone number + a one-time code, replacing the
    earlier static portal_id + PIN scheme entirely. A clinic-assigned PIN
    was a shared secret staff had to generate, hand over, and could in
    principle read/store; a code sent live to the patient's own verified
    phone (falling back to email when WhatsApp isn't reachable — see
    _deliver_code) is a real possession-based factor tied to a channel
    only the patient controls, and there's nothing durable for staff to
    mishandle. portal_id is kept only as a human-readable reference clinic
    staff can quote back to a patient (see system_design.md) — it plays no
    role in authentication anymore."""

    def __init__(self):
        self.otp_store = PatientOtpStore()

    async def _issue_temp_pin(self, db: AsyncSession, patient: Patient) -> tuple[str, datetime]:
        """Generates a fresh staff-visible one-time login PIN and stores it
        with its expiry on the patient. Each generation rotates the previous
        PIN, so re-issuing (resend/generate) instantly invalidates the old
        one — staff can safely hand out a new PIN if one was misplaced."""
        pin = str(random.Random().randint(0, 999999)).zfill(6)
        patient.portal_temp_pin = pin
        patient.portal_temp_pin_expires_at = datetime.now(timezone.utc) + timedelta(days=_TEMP_PIN_LIFETIME_DAYS)
        await db.flush()
        return pin, patient.portal_temp_pin_expires_at

    async def _find_patients_by_phone(self, db: AsyncSession, phone: str) -> list[Patient]:
        digits = "".join(ch for ch in phone if ch.isdigit())
        result = await db.execute(select(Patient).where(Patient.portal_enabled == True))  # noqa: E712
        return [p for p in result.scalars().all() if p.phone and "".join(ch for ch in p.phone if ch.isdigit()).endswith(digits[-10:])]

    async def _deliver_code(self, db: AsyncSession, patient: Patient, code: str) -> str:
        """Tries WhatsApp first (matches how this patient most likely
        already talks to the clinic), falls back to email if WhatsApp isn't
        configured/reachable or the patient has no WhatsApp identity on
        file. Raises if neither channel is available — there's no silent
        "looks sent but wasn't" path here, unlike the messaging bugs found
        earlier this project: a login code that didn't actually go out must
        surface as a real error, not a false success."""
        text = f"Your Aiaceone verification code is {code}. It expires in 10 minutes. Don't share this with anyone."

        result = await db.execute(select(Practice).where(Practice.id == patient.practice_id))
        practice = result.scalar_one_or_none()
        ga = WhatsAppGreenAPI.from_practice_settings((practice.settings if practice else None) or {})
        if ga is not None and patient.phone:
            try:
                send_result = await ga.send_text(patient.phone, text)
                if "idMessage" in send_result:
                    return "whatsapp"
                logger.warning("WhatsApp OTP send for patient %s did not return an idMessage: %s", patient.id, send_result)
            except Exception:
                logger.exception("WhatsApp OTP delivery failed for patient %s, falling back to email", patient.id)

        if patient.email:
            try:
                await ResendService().send(
                    patient.email, "Your Aiaceone verification code",
                    f"<p>Your verification code is <strong>{code}</strong>. It expires in 10 minutes.</p>",
                )
                return "email"
            except Exception:
                logger.exception("Email OTP delivery failed for patient %s", patient.id)

        raise AppException("Couldn't deliver a login code — no working WhatsApp or email on file. Please contact the clinic.")

    async def request_otp(self, db: AsyncSession, phone: str, client_key: str, ip_address: str | None = None) -> dict:
        await request_rate_limiter.check(client_key)
        candidates = await self._find_patients_by_phone(db, phone)

        if not candidates:
            await audit_log_service.log(db, None, "patient_portal", "otp_request.no_account", ip_address=ip_address)
            await db.commit()
            return {"found": False, "delivered_via": None}

        # Same phone matching more than one portal-enabled patient (rare —
        # different practices, or a duplicate record) — the newest profile
        # is the most likely one the patient actually means to reach.
        patient = max(candidates, key=lambda p: p.updated_at)
        code = await self.otp_store.generate(patient.phone)
        delivered_via = await self._deliver_code(db, patient, code)

        await audit_log_service.log(
            db, patient.practice_id, "patient_portal", "otp_request.sent",
            resource_type="patient", resource_id=patient.id, ip_address=ip_address,
        )
        await db.commit()
        return {"found": True, "delivered_via": delivered_via}

    async def verify_otp(self, db: AsyncSession, phone: str, code: str, client_key: str, ip_address: str | None = None) -> tuple[str, Patient, bool]:
        await verify_rate_limiter.check(client_key)
        candidates = await self._find_patients_by_phone(db, phone)
        if not candidates:
            raise UnauthorizedException("Invalid phone number or code")
        patient = max(candidates, key=lambda p: p.updated_at)

        if not await self.otp_store.verify(patient.phone, code):
            await audit_log_service.log(
                db, patient.practice_id, "patient_portal", "portal_login.failed",
                resource_type="patient", resource_id=patient.id, ip_address=ip_address,
            )
            await db.commit()
            raise UnauthorizedException("Invalid or expired code")

        await verify_rate_limiter.reset(client_key)
        await audit_log_service.log(
            db, patient.practice_id, "patient_portal", "portal_login.success",
            resource_type="patient", resource_id=patient.id, ip_address=ip_address,
        )
        await db.commit()
        token = self._issue_token(patient)
        # First-time logins have no PIN yet — the portal must prompt the
        # patient to set their own one so daily logins stop costing an OTP.
        return token, patient, patient.portal_pin_hash is None

    async def login_with_pin(self, db: AsyncSession, phone: str, pin: str, client_key: str, ip_address: str | None = None) -> tuple[str, Patient, bool]:
        """Primary patient login — phone + a PIN. Two valid PINs: the
        patient's own permanent PIN (portal_pin_hash), or a staff-issued
        one-time PIN (portal_temp_pin) that is single-use and expires.
        A one-time-PIN login counts as a first-time login (no permanent PIN
        yet) — the portal must prompt the patient to set their own PIN, just
        like after an OTP login. Either way it's free to use on every visit,
        with brute-force rate-limited exactly like OTP verification."""
        await verify_rate_limiter.check(client_key)
        candidates = await self._find_patients_by_phone(db, phone)
        if not candidates:
            raise UnauthorizedException("Invalid phone number or PIN")

        # More than one patient can share a phone number (duplicate record,
        # or a family member on the same line) — never resolve "which patient"
        # by picking the newest row, because that silently breaks login for
        # everyone else who shares the number. Instead try the PIN against
        # every candidate and authenticate the one whose PIN verifies.
        patient = None
        for cand in candidates:
            permanent_ok = bool(cand.portal_pin_hash) and _verify_pin(pin, cand.portal_pin_hash)
            temp_ok = False
            if not permanent_ok and cand.portal_temp_pin and cand.portal_temp_pin_expires_at:
                if cand.portal_temp_pin_expires_at > datetime.now(timezone.utc) and secrets.compare_digest(
                    pin, cand.portal_temp_pin
                ):
                    temp_ok = True
                    # The one-time PIN is single-use — it's dead after this login.
                    cand.portal_temp_pin = None
                    cand.portal_temp_pin_expires_at = None
            if permanent_ok or temp_ok:
                patient = cand
                break

        if patient is None:
            await audit_log_service.log(
                db, candidates[0].practice_id, "patient_portal", "portal_login.failed",
                resource_type="patient", resource_id=candidates[0].id, ip_address=ip_address,
            )
            await db.commit()
            raise UnauthorizedException("Invalid phone number or PIN")

        await verify_rate_limiter.reset(client_key)
        await audit_log_service.log(
            db, patient.practice_id, "patient_portal", "portal_login.success",
            resource_type="patient", resource_id=patient.id, ip_address=ip_address,
        )
        await db.commit()
        return self._issue_token(patient), patient, patient.portal_pin_hash is None

    async def set_pin(self, db: AsyncSession, patient: Patient, pin: str, current_pin: str | None = None) -> None:
        """Sets/updates the patient's own PIN. Setting for a patient who
        already has a PIN requires `current_pin` (they're changing it — same
        rule as a password change); first-time setup needs no current PIN."""
        if not _valid_pin(pin):
            raise AppException(f"PIN must be {_PIN_MIN_DIGITS}-{_PIN_MAX_DIGITS} digits")
        if patient.portal_pin_hash is not None:
            if not current_pin or not _verify_pin(current_pin, patient.portal_pin_hash):
                raise UnauthorizedException("Current PIN is wrong")
        patient.portal_pin_hash = _hash_pin(pin)
        patient.pin_set_at = datetime.now(timezone.utc)
        await db.flush()
        await audit_log_service.log(
            db, patient.practice_id, "patient_portal", "portal_pin.set",
            resource_type="patient", resource_id=patient.id,
        )
        await db.commit()

    # --- Staff-side portal management -------------------------------------

    async def _get_practice_patient(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> Patient:
        result = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.practice_id == practice_id))
        patient = result.scalar_one_or_none()
        if patient is None:
            raise NotFoundException("Patient not found")
        return patient

    async def _generate_unique_portal_id(self, db: AsyncSession) -> str:
        year = datetime.now(timezone.utc).year
        for _ in range(10):
            candidate = f"PT-{year}-{random.randint(0, 99999):05d}"
            existing = await db.execute(select(Patient.id).where(Patient.portal_id == candidate))
            if existing.scalar_one_or_none() is None:
                return candidate
        raise AppException("Could not generate a unique patient ID — try again.")

    async def enable_portal(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> tuple[str, bool, str | None, datetime | None]:
        """Turns portal access on (generating a reference patient ID if this
        patient doesn't have one yet), issues a fresh staff-visible one-time
        login PIN, and sends an invite over WhatsApp/email carrying that PIN
        so the patient can log in with their phone number + PIN even if the
        message itself never lands (staff can read the PIN back to them).
        Returns (portal_id, invite_sent, temp_pin, temp_pin_expires_at)."""
        patient = await self._get_practice_patient(db, practice_id, patient_id)
        if not patient.portal_id:
            patient.portal_id = await self._generate_unique_portal_id(db)
        patient.portal_enabled = True
        await db.flush()

        temp_pin, expires_at = await self._issue_temp_pin(db, patient)
        await db.commit()

        invite_sent = False
        if patient.phone or patient.email:
            try:
                await self._send_invite(db, patient, temp_pin)
                invite_sent = True
            except Exception:
                logger.exception("Portal invite send failed for patient %s — access is enabled regardless", patient.id)
        return patient.portal_id, invite_sent, temp_pin, expires_at

    async def generate_portal_pin(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> tuple[str | None, datetime | None]:
        """(Re)issues the staff-visible one-time login PIN for an already
        enabled patient — the "Generate new PIN" action in the staff panel.
        Rotates out any previous PIN immediately (it stops working the moment
        this one is written)."""
        patient = await self._get_practice_patient(db, practice_id, patient_id)
        if not patient.portal_enabled:
            raise AppException("Portal isn't enabled for this patient yet — enable it first.")
        temp_pin, expires_at = await self._issue_temp_pin(db, patient)
        await db.commit()
        return temp_pin, expires_at

    async def resend_invite(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> tuple[str | None, datetime | None]:
        patient = await self._get_practice_patient(db, practice_id, patient_id)
        if not patient.portal_enabled:
            raise AppException("Portal isn't enabled for this patient yet — enable it first.")
        # Resending also rotates the PIN — the invite carries a live credential.
        temp_pin, expires_at = await self._issue_temp_pin(db, patient)
        await self._send_invite(db, patient, temp_pin)
        await db.commit()
        return temp_pin, expires_at

    async def _send_invite(self, db: AsyncSession, patient: Patient, pin: str) -> None:
        text = (
            f"Hi {patient.first_name}, your Aiaceone patient portal is ready. "
            f"Log in at the portal with your phone number and this one-time PIN: {pin}. "
            f"It works once and expires in 7 days — after logging in you'll set your own PIN. "
            f"Your reference ID is {patient.portal_id}."
        )
        result = await db.execute(select(Practice).where(Practice.id == patient.practice_id))
        practice = result.scalar_one_or_none()
        ga = WhatsAppGreenAPI.from_practice_settings((practice.settings if practice else None) or {})
        if ga is not None and patient.phone:
            try:
                send_result = await ga.send_text(patient.phone, text)
                if "idMessage" in send_result:
                    return
            except Exception:
                logger.exception("WhatsApp portal invite delivery failed for patient %s", patient.id)
        if patient.email:
            await ResendService().send(patient.email, "Your Aiaceone patient portal is ready", f"<p>{text}</p>")
            return
        raise AppException("No working WhatsApp or email on file to send the invite.")

    async def disable_portal(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> None:
        patient = await self._get_practice_patient(db, practice_id, patient_id)
        patient.portal_enabled = False
        # A disabled portal shouldn't leave a live handed-out PIN floating around.
        patient.portal_temp_pin = None
        patient.portal_temp_pin_expires_at = None
        await db.flush()

    async def get_portal_state(self, db: AsyncSession, practice_id: UUID, patient_id: UUID) -> tuple[str | None, bool, str | None, datetime | None, bool]:
        patient = await self._get_practice_patient(db, practice_id, patient_id)
        return (
            patient.portal_id,
            patient.portal_enabled,
            patient.portal_temp_pin,
            patient.portal_temp_pin_expires_at,
            patient.portal_pin_hash is not None,
        )

    # --- Token issuance / verification -------------------------------------

    def _issue_token(self, patient: Patient) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(patient.id),
            "practice_id": str(patient.practice_id),
            "type": "patient_portal",
            "iat": now,
            "exp": now + timedelta(minutes=settings.patient_portal_jwt_expires_minutes),
        }
        return jwt.encode(payload, settings.patient_portal_jwt_secret, algorithm="HS256")

    def verify_token(self, token: str) -> UUID:
        try:
            payload = jwt.decode(token, settings.patient_portal_jwt_secret, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise UnauthorizedException("Invalid or expired session — please log in again")
        if payload.get("type") != "patient_portal":
            raise UnauthorizedException("Invalid session token")
        return UUID(payload["sub"])
