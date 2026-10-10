import base64
import hashlib
import hmac
import logging
import time
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
from src.models.subscription import Subscription, SubscriptionStatus
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


_SVIX_TOLERANCE_SECONDS = 300


def _plain(obj):
    """A StripeObject (or anything with to_dict) as plain nested dicts/lists; dicts pass through."""
    return obj.to_dict() if hasattr(obj, "to_dict") else obj


def _verify_clerk_signature(
    payload: bytes, svix_id: str, svix_timestamp: str, svix_signature: str, secret: str
) -> bool:
    """Verify a Clerk (Svix) webhook.

    Svix signs `"{svix-id}.{svix-timestamp}.{raw body}"` with HMAC-SHA256 using
    the BASE64-DECODED secret (the part after `whsec_`), and sends the result as
    one or more space-separated `v1,<base64>` entries in the `svix-signature`
    header. The timestamp is checked too, so a captured request can't be
    replayed later."""
    if not (secret and svix_id and svix_timestamp and svix_signature):
        return False
    try:
        timestamp = int(svix_timestamp)
        if abs(time.time() - timestamp) > _SVIX_TOLERANCE_SECONDS:
            return False
        key = base64.b64decode(secret.removeprefix("whsec_"))
        signed = f"{svix_id}.{svix_timestamp}.".encode("utf-8") + payload
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("utf-8")
        for entry in svix_signature.split(" "):
            version, _, signature = entry.partition(",")
            if version == "v1" and hmac.compare_digest(signature, expected):
                return True
        return False
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
        if not _verify_clerk_signature(raw_body, svix_id, svix_timestamp, svix_signature, settings.clerk_webhook_secret):
            raise AppException("Invalid Clerk webhook signature", status_code=400)
    elif settings.app_env != "development":
        # An unverified user.created event can rebind an existing staff
        # account (including the Owner) to an attacker's Clerk id, so outside
        # local development an unconfigured secret means "refuse", not "trust".
        raise AppException("Clerk webhook secret is not configured", status_code=503)
    else:
        logger.warning("CLERK_WEBHOOK_SECRET is empty - accepting an UNVERIFIED Clerk webhook (development only)")

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
    if not settings.stripe_webhook_secret:
        # construct_event with an empty secret verifies against an empty key,
        # i.e. a forged event signed with "" would pass.
        raise AppException("Stripe webhook secret is not configured", status_code=503)
    try:
        event = stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=stripe_signature,
            secret=settings.stripe_webhook_secret,
        )
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise AppException(f"Invalid Stripe webhook signature: {exc}", status_code=400)

    event_type = event["type"]
    # stripe-python >= 8 hands back StripeObject instances, which are NOT dicts (no .get()), while
    # every handler below reads the payload like a dict. Normalise once, here - before this, every
    # checkout.session.completed raised AttributeError, so no payment ever marked a signup paid.
    data = _plain(event["data"]["object"])

    # --- checkout.session.completed (existing) ---
    if event_type == "checkout.session.completed":
        session = data
        metadata = session.get("metadata") or {}

        if metadata.get("type") == "invoice_payment" and metadata.get("invoice_id"):
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
                pending.completed_at = datetime.now(timezone.utc)
                if not pending.email:
                    # The checkout was started without an email, so Stripe's own form collected it.
                    details = session.get("customer_details") or {}
                    pending.email = (details.get("email") or session.get("customer_email") or "").strip().lower()
                await db.flush()

    # --- customer.subscription.created ---
    elif event_type == "customer.subscription.created":
        sub = data
        sub_id = sub["id"]
        # Find the practice by matching the subscription to a pending signup
        # or by the practice's existing subscription
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
        )
        subscription = result.scalar_one_or_none()
        # At this point a signup has usually not been claimed yet, so there is no
        # Subscription row to find: provisioning links the Stripe subscription
        # itself when the clinic is created (_link_stripe_subscription). This
        # branch only refreshes an already-linked subscription.
        if subscription:
            subscription.stripe_subscription_id = sub_id
            subscription.price = (sub.get("items", {}).get("data", [{}])[0].get("price", {}).get("unit_amount") or 0) / 100
            subscription.cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))
            # If subscription has a trial_end, use it; otherwise keep our calculated end_date
            trial_end = sub.get("trial_end")
            if trial_end:
                subscription.end_date = datetime.fromtimestamp(trial_end, tz=timezone.utc).date()
            # Status will be updated by customer.subscription.updated when trial ends
            logger.info("Linked Stripe subscription %s to practice %s", sub_id, subscription.practice_id)

    # --- customer.subscription.updated ---
    elif event_type == "customer.subscription.updated":
        sub = data
        sub_id = sub["id"]
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
        subscription = result.scalar_one_or_none()
        if subscription:
            status = sub.get("status")
            if status == "active":
                subscription.status = SubscriptionStatus.ACTIVE
            elif status == "trialing":
                subscription.status = SubscriptionStatus.TRIAL
            elif status == "past_due":
                subscription.status = SubscriptionStatus.PAST_DUE
            elif status == "canceled":
                subscription.status = SubscriptionStatus.CANCELLED
            elif status == "unpaid":
                subscription.status = SubscriptionStatus.EXPIRED

            # Update price if changed
            price_data = sub.get("items", {}).get("data", [{}])[0].get("price", {})
            if price_data.get("unit_amount"):
                subscription.price = price_data["unit_amount"] / 100

            # Update trial end if present
            trial_end = sub.get("trial_end")
            if trial_end:
                subscription.end_date = datetime.fromtimestamp(trial_end, tz=timezone.utc).date()

            # Mirror Stripe's cancel_at_period_end so the Super Admin can
            # count "Cancelling" separately from "Active" — the practice
            # keeps access until period end, so status alone can't express
            # "cancelled but still paid up".
            subscription.cancel_at_period_end = bool(sub.get("cancel_at_period_end", False))

            logger.info("Updated subscription %s status=%s", sub_id, subscription.status.value)

    # --- customer.subscription.deleted ---
    elif event_type == "customer.subscription.deleted":
        sub = data
        sub_id = sub["id"]
        result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
        subscription = result.scalar_one_or_none()
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            logger.info("Cancelled subscription %s", sub_id)

    # --- invoice.paid ---
    elif event_type == "invoice.paid":
        invoice = data
        sub_id = invoice.get("subscription")
        if sub_id:
            result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
            subscription = result.scalar_one_or_none()
            if subscription:
                # Record payment for the subscription renewal
                amount_paid = (invoice.get("amount_paid") or 0) / 100
                if amount_paid > 0:
                    subscription.status = SubscriptionStatus.ACTIVE
                    # Could create a payment record here for audit trail
                    logger.info("Invoice paid for subscription %s, amount=%s", sub_id, amount_paid)

    # --- invoice.payment_failed ---
    elif event_type == "invoice.payment_failed":
        invoice = data
        sub_id = invoice.get("subscription")
        if sub_id:
            result = await db.execute(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
            subscription = result.scalar_one_or_none()
            if subscription:
                subscription.status = SubscriptionStatus.PAST_DUE
                logger.warning("Invoice payment failed for subscription %s", sub_id)

    return {"received": True}
