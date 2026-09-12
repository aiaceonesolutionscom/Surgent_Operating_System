import hashlib
import hmac
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Request, Header, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from src.config import get_settings
from src.database import get_db
from src.server.exceptions import AppException
from src.models.pending_signup import PendingSignup
from src.models.user import User, UserRole
from src.models.doctor import Doctor
from src.models.invoice import Invoice, PaymentMethod
from src.services.billing.invoice_services import InvoiceService
from src.services.billing.invoice_receipt_service import InvoiceReceiptService
from src.services.billing.wallet_services import WalletService
from src.services.practice.org_request_service import OrgRequestService

settings = get_settings()
logger = logging.getLogger("aesthetixai.webhooks")

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
invoice_service = InvoiceService()
invoice_receipts = InvoiceReceiptService()
wallet_service = WalletService()
org_request_service = OrgRequestService()


def _verify_clerk_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """Verify Clerk webhook signature using HMAC-SHA256 (svix format)."""
    if not secret or not signature_header:
        return False
    try:
        parts = {}
        for item in signature_header.split(","):
            key, value = item.split("=", 1)
            parts[key] = value
        expected_sig = parts.get("v1", "")
        signed_payload = f"{parts.get('t', '')}.{payload.decode('utf-8')}"
        computed = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        import base64
        computed_b64 = base64.b64encode(computed).decode("utf-8")
        return hmac.compare_digest(computed_b64, expected_sig)
    except Exception as e:
        logger.warning("Clerk signature verification failed: %s", e)
        return False


@router.post("/clerk")
async def clerk_webhook(
    request: Request,
    svix_id: str = Header(default="", alias="svix-id"),
    svix_timestamp: str = Header(default="", alias="svix-timestamp"),
    svix_signature: str = Header(default="", alias="svix-signature"),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    if settings.clerk_webhook_secret:
        signature_header = f"t={svix_timestamp},v1={svix_signature}"
        if not _verify_clerk_signature(raw_body, signature_header, settings.clerk_webhook_secret):
            raise AppException("Invalid Clerk webhook signature", status_code=400)

    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})
    clerk_user_id = data.get("id")

    if event_type == "user.created" and clerk_user_id:
        existing = await db.execute(select(User).where(User.clerk_id == clerk_user_id))
        if existing.scalar_one_or_none() is None:
            email_addresses = data.get("email_addresses", [])
            primary_email = next(
                (e["email_address"] for e in email_addresses if e.get("id") == data.get("primary_email_address_id")),
                email_addresses[0]["email_address"] if email_addresses else "",
            )
            name = data.get("first_name", "") + " " + data.get("last_name", "")
            phone = data.get("phone_numbers", [{}])[0].get("phone_number", "") if data.get("phone_numbers") else None
            public_metadata = data.get("public_metadata", {})
            unsafe_metadata = data.get("unsafe_metadata", {})
            invite_type = public_metadata.get("invite_type")
            self_apply_type = unsafe_metadata.get("invite_type")

            if self_apply_type == "doctor_self_apply" and unsafe_metadata.get("practice_id"):
                # Self-registration via a practice's shareable signup code
                # (see practice_router.py's GET /practice/validate-doctor-code
                # and frontend's DoctorApplyPage) — unsafe_metadata (set
                # client-side at Clerk sign-up) carries the resolved
                # practice_id, since there's no invite to stamp public_metadata
                # with ahead of time. Created inactive: this account can only
                # submit an application (see get_current_user_record in
                # dependencies.py) until an Owner reviews and approves it,
                # which is what flips is_active and creates the real Doctor row.
                new_user = User(
                    clerk_id=clerk_user_id,
                    practice_id=UUID(unsafe_metadata["practice_id"]),
                    email=primary_email,
                    name=name,
                    phone=phone,
                    role=UserRole.DOCTOR,
                    is_active=False,
                )
                db.add(new_user)
                await db.flush()
                logger.info("Created inactive self-applied Doctor User for clerk_id=%s", clerk_user_id)
            elif self_apply_type == "staff_self_apply" and unsafe_metadata.get("practice_id"):
                # Self-registration via a practice's shareable staff signup code
                # (see practice_router.py's GET /practice/validate-staff-code and
                # frontend's StaffApplyPage) — the receptionist mirror of the
                # doctor_self_apply branch above, so front-desk staff onboard
                # through the SAME link-followed-by-Owner-approval mechanism as
                # doctors. Created inactive: the account can only submit a staff
                # application (see get_current_user_record in dependencies.py)
                # until an Owner reviews and approves it, which is what flips
                # is_active and grants User.permissions.
                new_user = User(
                    clerk_id=clerk_user_id,
                    practice_id=UUID(unsafe_metadata["practice_id"]),
                    email=primary_email,
                    name=name,
                    phone=phone,
                    role=UserRole.RECEPTIONIST,
                    is_active=False,
                )
                db.add(new_user)
                await db.flush()
                logger.info("Created inactive self-applied Receptionist User for clerk_id=%s", clerk_user_id)
            elif invite_type == "doctor" and public_metadata.get("practice_id"):
                # Invited via POST /api/v1/doctors/{id}/invite (ClerkService.invite_user) —
                # public_metadata carries the practice/doctor to link, since Clerk's JWT
                # has no signal about which practice a brand-new sign-up belongs to.
                new_user = User(
                    clerk_id=clerk_user_id,
                    practice_id=UUID(public_metadata["practice_id"]),
                    email=primary_email,
                    name=name,
                    phone=phone,
                    role=UserRole.DOCTOR,
                )
                db.add(new_user)
                await db.flush()

                doctor_id = public_metadata.get("doctor_id")
                if doctor_id:
                    doctor_result = await db.execute(select(Doctor).where(Doctor.id == UUID(doctor_id)))
                    doctor = doctor_result.scalar_one_or_none()
                    if doctor:
                        doctor.user_id = new_user.id
                        await db.flush()
                logger.info("Created Doctor User for clerk_id=%s, linked doctor_id=%s", clerk_user_id, doctor_id)
            elif invite_type == "receptionist" and public_metadata.get("practice_id"):
                # Invited via POST /api/v1/staff (ClerkService.invite_user) —
                # unlike Doctor, there's no pre-existing roster row to link:
                # permissions travel in public_metadata at invite time and
                # land directly on User.permissions (see models/user.py).
                # Owner can still edit them afterward via PATCH /staff/{id}.
                #
                # A "resend access" re-invite (StaffService.resend_access, for
                # someone who already has a User row but lost their Clerk
                # session) reuses this exact same invite path — if a matching
                # row already exists for this practice+email, relink it
                # instead of inserting a duplicate, or every resend would
                # silently create a second receptionist row at this practice.
                granted = public_metadata.get("permissions", [])
                target_practice_id = UUID(public_metadata["practice_id"])
                existing = await db.execute(
                    select(User).where(User.practice_id == target_practice_id, func.lower(User.email) == primary_email.lower())
                )
                new_user = existing.scalar_one_or_none()
                if new_user is not None:
                    new_user.clerk_id = clerk_user_id
                    new_user.is_active = True
                else:
                    new_user = User(
                        clerk_id=clerk_user_id,
                        practice_id=target_practice_id,
                        email=primary_email,
                        name=name,
                        phone=phone,
                        role=UserRole.RECEPTIONIST,
                        permissions=granted if isinstance(granted, list) else [],
                    )
                    db.add(new_user)
                await db.flush()
                logger.info("Created Receptionist User for clerk_id=%s", clerk_user_id)
            else:
                # A genuinely new self-signup — no invite, no self-apply code,
                # no plan chosen yet (that's the paid Pricing->checkout->claim
                # path, handled entirely separately by CheckoutService /
                # ProvisioningService). There is no Practice to attach a User
                # row to at this point, and User.practice_id is NOT NULL — an
                # unconditional User(role=STAFF, ...) here (the old behavior)
                # would raise IntegrityError on flush and 500 the whole
                # webhook. Instead, file this as a pending "new organization"
                # request for a Super Admin to review (see
                # org_request_service.py) — no User/Practice is created until
                # that approval happens.
                await org_request_service.get_or_create_for_webhook(db, clerk_user_id, primary_email)
                logger.info("Created org-request PendingSignup for clerk_id=%s", clerk_user_id)

    elif event_type == "user.updated" and clerk_user_id:
        result = await db.execute(select(User).where(User.clerk_id == clerk_user_id))
        user = result.scalar_one_or_none()
        if user:
            email_addresses = data.get("email_addresses", [])
            primary_email = next(
                (e["email_address"] for e in email_addresses if e.get("id") == data.get("primary_email_address_id")),
                email_addresses[0]["email_address"] if email_addresses else user.email,
            )
            user.email = primary_email
            user.name = (data.get("first_name", "") + " " + data.get("last_name", "")).strip() or user.name
            await db.flush()
            logger.info("Updated User for clerk_id=%s", clerk_user_id)

    elif event_type == "user.deleted" and clerk_user_id:
        result = await db.execute(select(User).where(User.clerk_id == clerk_user_id))
        user = result.scalar_one_or_none()
        if user:
            user.is_active = False
            await db.flush()
            logger.info("Deactivated User for clerk_id=%s", clerk_user_id)

    return {"received": True}


@router.post("/twilio/voice")
async def twilio_voice_webhook(request: Request):
    form = await request.form()
    return {"status": "received"}


@router.post("/twilio/sms")
async def twilio_sms_webhook(request: Request):
    form = await request.form()
    return {"status": "received"}


@router.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    payload = await request.json()
    return {"status": "received"}


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default="", alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    # Previously accepted any POST body as a genuine Stripe event with zero
    # verification — anyone could forge a "payment succeeded" call. Real
    # signature verification closes that.
    raw_body = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise AppException(f"Invalid Stripe webhook signature: {exc}", status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        metadata = session.get("metadata") or {}

        if metadata.get("type") == "invoice_payment" and metadata.get("invoice_id"):
            # Patient-facing one-off invoice payment — a completely separate
            # flow from the PendingSignup/subscription path below, sharing
            # only this endpoint (see PaymentService.create_invoice_checkout_session).
            # No user/practice context exists in a webhook call, so the
            # invoice's own practice_id (not a client-supplied one) is what
            # scopes this write.
            invoice_id = UUID(metadata["invoice_id"])
            result = await db.execute(select(Invoice).where(Invoice.id == invoice_id))
            invoice_row = result.scalar_one_or_none()
            if invoice_row is not None:
                amount_total = (session.get("amount_total") or 0) / 100
                existing_payments = await invoice_service.list_payments_for_invoice(
                    db, invoice_row.practice_id, invoice_id
                )
                already_recorded = any(p.stripe_checkout_session_id == session["id"] for p in existing_payments)
                if not already_recorded and amount_total > 0:
                    paid_invoice = await invoice_service.record_payment(
                        db, invoice_row.practice_id, invoice_id, amount_total, PaymentMethod.STRIPE,
                        stripe_checkout_session_id=session["id"],
                        stripe_payment_intent_id=session.get("payment_intent"),
                    )
                    logger.info("Recorded Stripe payment for invoice_id=%s", invoice_id)
                    await invoice_receipts.send_receipt_best_effort(db, invoice_row.practice_id, paid_invoice, amount_total)
        elif metadata.get("type") == "wallet_topup" and metadata.get("practice_id"):
            practice_id = UUID(metadata["practice_id"])
            amount_total = (session.get("amount_total") or 0) / 100
            if amount_total > 0:
                await wallet_service.record_topup(
                    db, practice_id, amount_total, (session.get("currency") or "usd").upper(),
                    session["id"], session.get("payment_intent"),
                )
                logger.info("Recorded wallet top-up for practice_id=%s", practice_id)
        else:
            result = await db.execute(
                select(PendingSignup).where(PendingSignup.stripe_session_id == session["id"])
            )
            pending = result.scalar_one_or_none()
            if pending is not None:
                # Marks the checkout as paid. Provisioning the real Practice/
                # User/Subscription from this record is a deliberate follow-up —
                # see the NOTE in models/pending_signup.py for why a Subscription
                # row can't be written directly here yet.
                pending.completed_at = datetime.now(timezone.utc)
                await db.flush()

    return {"received": True}
