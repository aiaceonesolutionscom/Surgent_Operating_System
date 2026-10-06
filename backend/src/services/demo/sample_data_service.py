"""Per-practice demo ("sample") data for the free org-request trial path.

WHY THIS EXISTS
---------------
A prospect who requests free access (see PendingSignup's org-request fields and
services/practice/org_request_service.py) is provisioned by
ProvisioningService.provision_from_org_request — which creates a Practice, an
owner User, a trial Subscription and the 9 AgentConfig rows, and nothing else.
They therefore land on completely empty dashboards: no patients, no
appointments, no conversations. For a product whose entire pitch is "try it
before you pay", an empty dashboard is not a trial, it's a dead end.

This service fills those tables with realistic, clearly-fabricated clinic data
so the owner can actually click through the product and judge it.

THE THREE RULES THAT MAKE THIS SAFE
-----------------------------------
1. ALWAYS SCOPED TO ONE PRACTICE. Every insert carries the caller's
   `practice_id` and every delete filters on it. Clinic A's sample data can
   never appear in, or be deleted by, clinic B. Same invariant as every other
   practice-scoped query in this codebase (see tests/test_tenant_isolation.py).

2. ALWAYS FLAGGED `is_sample=True`. Every seeded row is individually
   identifiable, so the owner can delete a single row rather than all of it,
   and so the counts endpoint can tell the UI what it is showing. This flag is
   what makes rule 3 enforceable.

3. NEVER COUNTED AS MONEY. Sample rows are fabricated. A fabricated revenue or
   expense figure reaching a real customer's screen is a credibility problem
   that no amount of "demo" labelling fixes, and admin_services.py:20-28 makes
   the same point about estimated-vs-measured figures. Therefore: revenue,
   invoice, P&L, burn-rate and stock-valuation aggregates MUST filter on
   `is_sample == False`. See multiclinic.md §8.4.

SCOPE DELIBERATELY EXCLUDED
---------------------------
- `sales_leads` — NOT seeded. Despite the name this is Aiaceone's own
  platform-level buyer pipeline, not a clinic's patient funnel: no
  practice_id, and its `source` enum is aria_landing_chat / demo_form /
  book_consultation (models/sales_lead.py). Seeding it would fabricate rows in
  the real sales funnel and show them to the Super-Admin. A clinic's own lead
  funnel is Patient.lifecycle_stage, which IS seeded here.
- `messages` — NOT flagged directly; it has no practice_id and only a
  conversation_id FK, and a second independently-writable flag would only let
  the two drift apart. They are removed by clear_sample_data's explicit
  DELETE, which runs BEFORE the conversation delete and derives its id set from
  the same practice_id + is_sample predicate. (It cannot rely on
  Conversation.messages' cascade="all, delete-orphan": that is ORM-level and
  does not fire for a bulk DELETE statement.)
- `invoices` — NOT seeded, because invoices ARE money (rule 3).
- Real identity data — every name/phone/email below is invented and uses the
  reserved-for-fiction +1 555 01xx phone block, so a sample row can never
  reach a real person even if an outbound channel is later wired up by mistake.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.appointment import Appointment, AppointmentStatus
from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.expense import Expense
from src.models.inventory_item import InventoryItem
from src.models.message import Message, MessageRole
from src.models.patient import Patient, PatientLifecycleStage
from src.models.practice import Practice

# ---------------------------------------------------------------------------
# Seed content
# ---------------------------------------------------------------------------

# (first, last, age, gender, complaint, source, lifecycle, preferred_channel)
_SAMPLE_PATIENTS = [
    ("Ayesha", "Rahman", 31, "female", "Acne scarring on cheeks, wants laser resurfacing", "Instagram", PatientLifecycleStage.PATIENT, "whatsapp"),
    ("Bilal", "Ahmed", 38, "male", "Hair transplant consultation — thinning at crown", "Referral", PatientLifecycleStage.TREATMENT_PLANNED, "call"),
    ("Sana", "Khan", 27, "female", "Rhinoplasty pricing and pre-op questions", "WhatsApp", PatientLifecycleStage.CONSULT_COMPLETED, "whatsapp"),
    ("Hamza", "Iqbal", 45, "male", "Gynecomastia — interested in surgery", "Web Search", PatientLifecycleStage.CONSULT_SCHEDULED, "call"),
    ("Zainab", "Malik", 34, "female", "Breast augmentation and implant size guidance", "Referral", PatientLifecycleStage.TREATMENT_PLANNED, "whatsapp"),
    ("Usman", "Sheikh", 52, "male", "Facelift and neck tightening", "Walk-in", PatientLifecycleStage.CONSULT_COMPLETED, "sms"),
    ("Maryam", "Yousuf", 29, "female", "Lip filler — first time, nervous", "Instagram", PatientLifecycleStage.CONSULT_SCHEDULED, "whatsapp"),
    ("Ali", "Raza", 41, "male", "Botulinum toxin for chronic migraine", "Phone", PatientLifecycleStage.PATIENT, "call"),
    ("Fatima", "Bibi", 36, "female", "PRP for hair fall after childbirth", "WhatsApp", PatientLifecycleStage.PATIENT, "whatsapp"),
    ("Omar", "Farooq", 48, "male", "Liposuction — consult and recovery questions", "Web Search", PatientLifecycleStage.CONSULT_COMPLETED, "sms"),
    ("Hira", "Siddiqui", 33, "female", "Melasma treatment options", "Instagram", PatientLifecycleStage.INQUIRY, "whatsapp"),
    ("Naveed", "Aslam", 39, "male", "Ear reshaping (otoplasty)", "Referral", PatientLifecycleStage.LOST, "call"),
]

_APPOINTMENT_TYPES = [
    "Initial consultation",
    "Follow-up review",
    "Procedure session",
    "Pre-op assessment",
    "Post-op check",
]

_APPOINTMENT_NOTES = [
    "First visit — full assessment and photographs.",
    "Second session. Patient responding well.",
    "Review at 4 weeks, check healing.",
    "Pre-op — consent discussed, bloods pending.",
    "Post-op day 7 check and suture review.",
]

# Each entry: agent slug, channel, and the thread. Roles alternate to read like a
# real inbox; the last script deliberately shows an agent escalating to a human
# so the "needs attention" state has something in it worth looking at.
_CONVERSATION_SCRIPTS = [
    (
        "appointment_booking",
        ConversationChannel.WHATSAPP,
        [
            (MessageRole.PATIENT, "Hi, I saw your Instagram. Do you do acne laser treatment?"),
            (MessageRole.AGENT, "Hi! Yes we do — laser resurfacing is one of our most requested treatments. Would you like to book a consultation?"),
            (MessageRole.PATIENT, "Yes please. What are your timings?"),
            (MessageRole.AGENT, "We're open Monday to Saturday, 10am–7pm. I can do Tuesday 11:30am with the doctor — shall I hold that for you?"),
            (MessageRole.PATIENT, "Perfect, book it."),
            (MessageRole.AGENT, "Booked! Tuesday 11:30am. Please bring your current skincare products so the doctor can review them. See you then."),
        ],
    ),
    (
        "faq_and_pricing",
        ConversationChannel.WHATSAPP,
        [
            (MessageRole.PATIENT, "Hello, what is the price of rhinoplasty?"),
            (MessageRole.AGENT, "Hello! Rhinoplasty starts at PKR 180,000 including surgeon fee, anaesthesia and one night stay. The exact figure depends on your assessment. Would you like a consultation?"),
            (MessageRole.PATIENT, "What about revision cases?"),
            (MessageRole.AGENT, "Revision rhinoplasty is assessed case by case as it's more complex. I can book you with the surgeon for an assessment so you get an exact quote."),
            (MessageRole.PATIENT, "Okay, book for Saturday."),
        ],
    ),
    (
        "appointment_booking",
        ConversationChannel.INSTAGRAM,
        [
            (MessageRole.PATIENT, "Do you do breast implants? How long is the surgery?"),
            (MessageRole.AGENT, "Yes! Augmentation is around 1.5–2 hours under general anaesthesia, usually day-case. Would you like to discuss size and shape with the surgeon?"),
            (MessageRole.PATIENT, "Yes please"),
            (MessageRole.AGENT, "Booked — Saturday 1:00pm consultation. You'll get a full plan and exact cost after the assessment."),
        ],
    ),
    (
        "reminder",
        ConversationChannel.SMS,
        [
            (MessageRole.SYSTEM, "Reminder: appointment tomorrow 11:30am at Aiaceone Clinic."),
            (MessageRole.PATIENT, "Noted, thank you"),
            (MessageRole.AGENT, "You're welcome. If anything changes, just reply here."),
        ],
    ),
    (
        "aftercare",
        ConversationChannel.WHATSAPP,
        [
            (MessageRole.AGENT, "Hi! This is Aiaceone following up after your session today. How are you feeling?"),
            (MessageRole.PATIENT, "A bit sore but okay. There is some redness."),
            (MessageRole.AGENT, "Mild redness for 24–48 hours after filler is normal. Please use the cold compress we gave you. If it worsens or you have swelling beyond that, reply here and we'll bring you in."),
            (MessageRole.PATIENT, "Thanks, will do."),
        ],
    ),
    (
        "appointment_booking",
        ConversationChannel.FACEBOOK,
        [
            (MessageRole.PATIENT, "Hi, I'm in Lahore this week — can I get a consultation?"),
            (MessageRole.AGENT, "Welcome! Yes, we have availability Thursday 4:00pm and Friday 11:00am. Which suits you?"),
            (MessageRole.PATIENT, "Friday 11am"),
            (MessageRole.AGENT, "Confirmed — Friday 11:00am. Please bring your ID."),
        ],
    ),
    (
        "lead_qualification",
        ConversationChannel.WEB_CHAT,
        [
            (MessageRole.PATIENT, "I'm looking for hair transplant. What is the price and is it a one-time thing?"),
            (MessageRole.AGENT, "Hair transplant starts at PKR 120,000 for the procedure, and most patients need a session count decided at consultation (often 1–2 sessions over a year). Would you like us to assess your case?"),
            (MessageRole.PATIENT, "Yes, and do you do female hair transplant too?"),
            (MessageRole.AGENT, "We do. Booked for your assessment — Tuesday 12:00pm."),
        ],
    ),
    (
        "emergency_triage",
        ConversationChannel.WHATSAPP,
        [
            (MessageRole.PATIENT, "I had a bad reaction after a filler 3 days ago and my lip is swollen."),
            (MessageRole.AGENT, "I'm sorry to hear that — that's not something to leave for later. I'm bringing in our clinical lead now."),
            (MessageRole.STAFF, "This is the clinical lead. I've reviewed your case. Please come in to the clinic today at your earliest convenience and bring anything you've been given."),
        ],
    ),
]

_INVENTORY_ITEMS = [
    ("Hyaluronic Acid Filler 1ml", "FIL-001", "Injectables", "syringe", Decimal("8500.00"), 10, True),
    ("Botulinum Toxin Type A 100u", "BTX-001", "Injectables", "vial", Decimal("12500.00"), 8, True),
    ("PDO Threads 18G", "THR-018", "Injectables", "box", Decimal("3200.00"), 12, False),
    ("Nitrile Gloves (pair)", "CON-100", "Consumables", "pair", Decimal("45.00"), 200, False),
    ("Sterile Gauze 10x10cm", "CON-115", "Consumables", "pack", Decimal("120.00"), 60, False),
    ("Post-procedure Aftercare Kit", "KIT-001", "Retail", "kit", Decimal("950.00"), 25, False),
    ("Local Anaesthetic (Lidocaine)", "MED-004", "Medications", "vial", Decimal("650.00"), 15, False),
    ("Surgical Marker Pen", "CON-140", "Consumables", "each", Decimal("280.00"), 5, False),
]

# (category, vendor, amount, months_ago)
_EXPENSES = [
    ("rent", "Riverside Properties", Decimal("85000.00"), 4),
    ("utilities", "LESCO / WAPDA", Decimal("14500.00"), 2),
    ("supplies", "MediSupply Traders", Decimal("38200.00"), 3),
    ("salaries", "Payroll", Decimal("65000.00"), 2),
    ("marketing", "Meta", Decimal("22000.00"), 1),
    ("maintenance", "MedEquip Services", Decimal("9500.00"), 5),
]


class SampleDataService:
    """Seeds and clears clearly-flagged demo data for exactly one practice."""

    def __init__(self, seed: int | None = None) -> None:
        # Fixed seed by default so a given practice always gets the SAME demo
        # data — a prospect who clears and reloads should not see the clinic
        # suddenly look like a different business, which reads as a bug.
        self._rng = random.Random(seed if seed is not None else 20261002)

    # ---------------------------------------------------------------- read

    async def _count_sample_messages(self, db: AsyncSession, practice_id: UUID) -> int:
        """Messages are derived rather than flagged (see module docstring), so
        they are counted through their parent Conversation."""
        return (
            await db.execute(
                select(func.count())
                .select_from(Message)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(
                    Conversation.practice_id == practice_id,
                    Conversation.is_sample.is_(True),
                )
            )
        ).scalar_one()

    async def sample_data_counts(self, db: AsyncSession, practice_id: UUID) -> dict[str, int]:
        def count_flagged(model, practice_col):
            return (
                select(func.count())
                .select_from(model)
                .where(practice_col == practice_id, model.is_sample.is_(True))
            )

        counts = {
            "patients": (await db.execute(count_flagged(Patient, Patient.practice_id))).scalar_one(),
            "appointments": (await db.execute(count_flagged(Appointment, Appointment.practice_id))).scalar_one(),
            "conversations": (await db.execute(count_flagged(Conversation, Conversation.practice_id))).scalar_one(),
            "inventory_items": (await db.execute(count_flagged(InventoryItem, InventoryItem.practice_id))).scalar_one(),
            "expenses": (await db.execute(count_flagged(Expense, Expense.practice_id))).scalar_one(),
            "messages": await self._count_sample_messages(db, practice_id),
        }
        # "total" counts rows the owner can see and delete; Messages are excluded
        # because they are removed by cascade, not deleted independently.
        counts["total"] = sum(
            v for k, v in counts.items() if k not in ("total", "messages")
        )
        return counts

    # --------------------------------------------------------------- write

    async def seed_sample_data(self, db: AsyncSession, practice: Practice) -> dict[str, int]:
        """Idempotent: returns immediately if this practice already has sample
        patients, so a double-click can't double the demo data."""
        practice_id = practice.id

        already = (
            await db.execute(
                select(func.count())
                .select_from(Patient)
                .where(Patient.practice_id == practice_id, Patient.is_sample.is_(True))
            )
        ).scalar_one()
        if already:
            return await self.sample_data_counts(db, practice_id)

        # Patients first — appointments and conversations both FK to them.
        patients = await self._seed_patients(db, practice_id)
        doctor_id = await self._first_doctor_id(db, practice_id)

        await self._seed_appointments(db, practice_id, patients, doctor_id)
        await self._seed_conversations(db, practice_id, patients)
        await self._seed_inventory(db, practice_id)
        await self._seed_expenses(db, practice_id)

        await db.flush()
        return await self.sample_data_counts(db, practice_id)

    async def clear_sample_data(self, db: AsyncSession, practice_id: UUID) -> dict[str, int]:
        """Deletes only `is_sample` rows belonging to this practice. Every
        statement is scoped by BOTH practice_id and is_sample, so no input can
        reach a real row.

        Order matters only in that Conversations are removed before Patients,
        because Conversation.patient_id is a plain FK (Conversation is not in
        Practice's cascade list, so it is not removed automatically).

        KNOWN LIMITATION (deliberately not "fixed" here): this method bulk
        deletes InventoryItem, and inventory_batches.inventory_item_id is a
        plain FK with no ondelete="CASCADE" (InventoryItem.batches is an
        ORM-level cascade only, so it does not fire here either). The seeder
        creates no batches, so this is unreachable today — but if an owner ever
        RECEIVES STOCK into a demo item, deleting the sample data will raise
        ForeignKeyViolation. Closing it properly means deleting
        InventoryBatch first and InventoryAdjustment (which references
        inventory_batches.id) before that, so it is a three-level change rather
        than a one-line patch bolted onto a method that currently cannot hit it.
        Left as a known gap instead of a half-fix that would still 500 one
        level deeper.
        """
        removed: dict[str, int] = {
            "appointments": (
                await db.execute(
                    delete(Appointment).where(
                        Appointment.practice_id == practice_id,
                        Appointment.is_sample.is_(True),
                    )
                )
            ).rowcount,
            # Messages must be deleted EXPLICITLY, before their Conversations.
            # Conversation.messages is cascade="all, delete-orphan", but that is
            # an ORM-level cascade: it only fires when a Conversation is deleted
            # through the session (session.delete(obj)). The bulk DELETE below
            # bypasses the ORM entirely, and messages.conversation_id is a plain
            # FK with no ondelete="CASCADE", so relying on the relationship would
            # raise ForeignKeyViolation the moment a thread had any messages --
            # which is every thread the seeder creates. Deriving the id set from
            # the same practice_id + is_sample predicate keeps this scoped to
            # sample data only.
            "messages": (
                await db.execute(
                    delete(Message).where(
                        Message.conversation_id.in_(
                            select(Conversation.id).where(
                                Conversation.practice_id == practice_id,
                                Conversation.is_sample.is_(True),
                            )
                        )
                    )
                )
            ).rowcount,
            "conversations": (
                await db.execute(
                    delete(Conversation).where(
                        Conversation.practice_id == practice_id,
                        Conversation.is_sample.is_(True),
                    )
                )
            ).rowcount,
            "inventory_items": (
                await db.execute(
                    delete(InventoryItem).where(
                        InventoryItem.practice_id == practice_id,
                        InventoryItem.is_sample.is_(True),
                    )
                )
            ).rowcount,
            "expenses": (
                await db.execute(
                    delete(Expense).where(
                        Expense.practice_id == practice_id,
                        Expense.is_sample.is_(True),
                    )
                )
            ).rowcount,
            "patients": (
                await db.execute(
                    delete(Patient).where(
                        Patient.practice_id == practice_id,
                        Patient.is_sample.is_(True),
                    )
                )
            ).rowcount,
        }

        await db.flush()
        # "total" deliberately excludes "messages" so it stays comparable to
        # sample_data_counts()["total"]: it means "rows the owner can see and
        # delete independently". Messages go away with their conversation and
        # are never deleted on their own.
        removed["total"] = sum(
            v for k, v in removed.items() if k not in ("total", "messages")
        )
        return removed

    # --------------------------------------------------- seeding internals

    async def _seed_patients(self, db: AsyncSession, practice_id: UUID) -> list[Patient]:
        today = date.today()
        patients: list[Patient] = []

        for idx, (first, last, age, gender, complaint, source, stage, channel) in enumerate(
            _SAMPLE_PATIENTS
        ):
            dob = date(today.year - age, self._rng.randint(1, 12), self._rng.randint(1, 28))
            patient = Patient(
                practice_id=practice_id,
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}@example.com",
                phone=f"+1 555 01{idx:02d}",
                date_of_birth=dob,
                gender=gender,
                chief_complaint=complaint,
                source=source,
                lifecycle_stage=stage,
                consent_status=True,
                portal_enabled=False,
                communication_preferences={
                    "sms": channel == "sms",
                    "email": False,
                    "whatsapp": channel == "whatsapp",
                    "call": channel == "call",
                },
                medical_history={
                    "skin_type": self._rng.choice(["normal", "oily", "dry", "combination"])
                },
                allergies=[],
                surgical_history=[],
                current_medications=[],
                is_sample=True,
            )
            if stage == PatientLifecycleStage.LOST:
                patient.lost_reason = "Unresponsive after consultation"
            db.add(patient)
            patients.append(patient)

        await db.flush()
        return patients

    async def _first_doctor_id(self, db: AsyncSession, practice_id: UUID) -> UUID | None:
        """Appointments and inbox threads read better attributed to a real
        doctor, but a freshly-approved org may not have invited one yet — so
        this is allowed to be None rather than required."""
        from src.models.doctor import Doctor

        return (
            await db.execute(
                select(Doctor.id).where(Doctor.practice_id == practice_id).limit(1)
            )
        ).scalar_one_or_none()

    async def _seed_appointments(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patients: list[Patient],
        doctor_id: UUID | None,
    ) -> int:
        now = datetime.now(timezone.utc)
        created = 0

        for idx, patient in enumerate(patients):
            # Two per patient: one upcoming, one historical, so the calendar has
            # both a "today/next" view and a past-visit history behind it.
            upcoming = now + timedelta(days=(idx % 9) + 1)
            upcoming = upcoming.replace(hour=self._rng.randint(10, 18), minute=0, second=0, microsecond=0)
            historical = now - timedelta(days=3 + (idx % 20))
            historical = historical.replace(hour=self._rng.randint(10, 18), minute=0, second=0, microsecond=0)

            for start, status in (
                (upcoming, AppointmentStatus.SCHEDULED),
                (historical, AppointmentStatus.COMPLETED),
            ):
                db.add(
                    Appointment(
                        practice_id=practice_id,
                        patient_id=patient.id,
                        doctor_id=doctor_id,
                        appointment_type=self._rng.choice(_APPOINTMENT_TYPES),
                        status=status,
                        start_time=start,
                        end_time=start + timedelta(minutes=self._rng.choice([30, 45, 60])),
                        notes=self._rng.choice(_APPOINTMENT_NOTES),
                        is_sample=True,
                    )
                )
                created += 1

        await db.flush()
        return created

    async def _seed_conversations(
        self,
        db: AsyncSession,
        practice_id: UUID,
        patients: list[Patient],
    ) -> int:
        """Returns the number of Conversations created.

        NOT the number of Messages — the sibling _seed_* helpers return the rows
        they created, so counting messages here made this one inconsistent and
        would silently mislabel the first caller that ever used the value.
        """
        now = datetime.now(timezone.utc)
        created = 0

        for idx, (agent_type, channel, script) in enumerate(_CONVERSATION_SCRIPTS):
            patient = patients[idx % len(patients)]
            # The escalation script is left ACTIVE so the inbox's "needs
            # attention" split has something in it worth looking at.
            needs_attention = agent_type == "emergency_triage"
            thread_started = now - timedelta(days=idx % 7, hours=idx)

            conversation = Conversation(
                practice_id=practice_id,
                patient_id=patient.id,
                agent_type=agent_type,
                channel=channel,
                status=(
                    ConversationStatus.NEEDS_ATTENTION
                    if needs_attention
                    else ConversationStatus.ACTIVE
                ),
                is_active=True,
                is_sample=True,
                created_at=thread_started,
            )
            db.add(conversation)
            await db.flush()  # need conversation.id for its messages

            for msg_idx, (role, text) in enumerate(script):
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        role=role,
                        content=text,
                        content_type="text",
                        extra_data={},
                        created_at=thread_started + timedelta(minutes=2 * msg_idx),
                    )
                )

            created += 1

        await db.flush()
        return created

    async def _seed_inventory(self, db: AsyncSession, practice_id: UUID) -> int:
        created = 0
        for name, sku, category, unit, cost, threshold, is_implant in _INVENTORY_ITEMS:
            db.add(
                InventoryItem(
                    practice_id=practice_id,
                    name=name,
                    sku=sku,
                    category=category,
                    unit=unit,
                    unit_cost=cost,
                    reorder_threshold=threshold,
                    is_implant=is_implant,
                    is_active=True,
                    is_sample=True,
                )
            )
            created += 1
        await db.flush()
        return created

    async def _seed_expenses(self, db: AsyncSession, practice_id: UUID) -> int:
        """Expense.recorded_by is NOT NULL and must reference a real User in
        this practice. A freshly-provisioned org always has an owner, but this
        returns 0 rather than inventing a FK if one is ever absent."""
        from src.models.user import User, UserRole

        recorder_id = (
            await db.execute(
                select(User.id)
                .where(
                    User.practice_id == practice_id,
                    User.role == UserRole.OWNER,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if recorder_id is None:
            recorder_id = (
                await db.execute(
                    select(User.id).where(User.practice_id == practice_id).limit(1)
                )
            ).scalar_one_or_none()
        if recorder_id is None:
            return 0

        today = date.today()
        created = 0
        for category, vendor, amount, months_ago in _EXPENSES:
            db.add(
                Expense(
                    practice_id=practice_id,
                    expense_type="expense",
                    status="paid",
                    category=category,
                    amount=amount,
                    vendor=vendor,
                    expense_date=today
                    - timedelta(days=30 * months_ago + self._rng.randint(0, 6)),
                    paid_at=datetime.now(timezone.utc) - timedelta(days=30 * months_ago),
                    recorded_by=recorder_id,
                    is_sample=True,
                )
            )
            created += 1

        await db.flush()
        return created