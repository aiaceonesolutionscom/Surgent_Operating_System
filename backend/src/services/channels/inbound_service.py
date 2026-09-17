from __future__ import annotations
import json
import logging
import re
from datetime import datetime, date as date_cls, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation, ConversationChannel, ConversationStatus
from src.models.message import Message, MessageRole
from src.models.patient import Patient
from src.models.practice import Practice
from src.models.doctor import Doctor
from src.models.appointment import Appointment, AppointmentStatus
from src.models.agent_config import AgentConfig
from src.services.llm.llm_service import LLMService
from src.services.agent_log.agent_log_service import AgentLogService
from src.services.appointments.appointments_services import AppointmentsService
from src.services.channels.whatsapp_green_api import WhatsAppGreenAPI
from src.services.channels.booking_draft_store import BookingDraftStore
from src.services.leads.lead_qualification_service import LeadQualificationService
from src.services.patient_portal.patient_portal_auth_service import PatientPortalAuthService
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

_WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_APPOINTMENT_DURATION_MINUTES = 30

_DATE_RE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_PM_HINT_RE = re.compile(r"\b(evening|pm|p\.m\.|afternoon|tonight)\b", re.IGNORECASE)
_PROCEDURE_KEYWORDS = [
    "consultation", "consult", "botox", "dermal filler", "filler", "rhinoplasty",
    "liposuction", "facelift", "breast augmentation", "breast aug", "tummy tuck",
    "lip filler", "chemical peel",
]


def _extract_booking_hints(text: str, today: date_cls) -> dict:
    """Conservative, deterministic extraction of date/time/reason from a
    patient's raw message. Exists because relying on the LLM to reliably
    call book_appointment with partial info EVERY turn (so progress isn't
    lost) turned out not to hold in practice — the model would often just
    reply conversationally, understanding the fact but never persisting it.
    This only recognizes the exact formats the AI itself asks patients for
    (YYYY-MM-DD, 24-hour HH:MM) plus "today"/"tomorrow" — deliberately NOT
    attempting free-form parsing ("10 September", "next Tuesday"), since a
    real bug already came from over-eager date guessing: "may in the
    evening" got misread as the month May. A patient who replies in the
    exact format requested is captured here regardless of whether the LLM
    also calls the tool that turn; anything looser is left for the LLM's
    own understanding + tool call to catch."""
    hints: dict[str, str] = {}
    lowered = text.lower()

    date_match = _DATE_RE.search(text)
    if date_match:
        hints["date"] = date_match.group(1)
    elif re.search(r"\btomorrow\b", lowered):
        hints["date"] = (today + timedelta(days=1)).isoformat()
    elif re.search(r"\btoday\b", lowered):
        hints["date"] = today.isoformat()

    time_match = _TIME_RE.search(text)
    if time_match:
        hour = int(time_match.group(1))
        minute = time_match.group(2)
        # "5:30" said alongside "evening"/"pm"/etc with no AM/PM marker of
        # its own — treat as post-noon rather than taking it literally as
        # 24-hour 05:30, which is very unlikely to be what a patient means
        # when they've just said "in the evening".
        if hour < 12 and _PM_HINT_RE.search(lowered):
            hour += 12
        hints["time"] = f"{hour:02d}:{minute}"

    for kw in _PROCEDURE_KEYWORDS:
        if kw in lowered:
            hints["appointment_type"] = kw.title()
            break

    return hints


def _format_draft(draft: dict) -> str:
    if not draft:
        return "Nothing confirmed yet."
    parts = []
    if draft.get("date"):
        parts.append(f"date={draft['date']}")
    if draft.get("time"):
        parts.append(f"time={draft['time']}")
    if draft.get("appointment_type"):
        parts.append(f"reason={draft['appointment_type']}")
    return ", ".join(parts) if parts else "Nothing confirmed yet."


def _system_prompt(
    is_new_patient: bool, today: date_cls, draft: dict | None = None, extra_instructions: str | None = None
) -> str:
    patient_context = (
        "This is a NEW patient — you don't have any prior visit on file for them. "
        "Greet them warmly and get their name if the conversation doesn't already make it clear."
        if is_new_patient
        else "This is a RETURNING patient — you already have their record. "
        "Acknowledge that warmly (e.g. \"welcome back\") instead of asking who they are."
    )
    base = (
        "You are a warm, professional AI receptionist for a plastic surgery clinic, replying over WhatsApp. "
        f"{patient_context}\n\n"
        "You help with: booking appointments, questions about procedures (rhinoplasty, breast augmentation, "
        "liposuction, facelift, Botox, dermal fillers, etc.), pricing, clinic hours, and general post-op questions.\n\n"
        "BOOKING DETAILS CONFIRMED SO FAR (trust this, don't re-derive it from scrolling back through the "
        f"conversation): {_format_draft(draft or {})}\n\n"
        "When a patient wants to book:\n"
        "1. If the line above already shows date, time, AND reason all confirmed, call book_appointment right "
        "now (it's fine to call it with no arguments, or restating the confirmed values) — that completes the "
        "booking. Do not ask another question first.\n"
        "2. Otherwise, call book_appointment with whatever of date/time/appointment_type you can extract from "
        "THIS message — even if it's only one field. The system merges it with what's already confirmed above "
        "and tells you exactly what's still missing. Never ask again for something already listed as confirmed.\n"
        "3. Once date, time, and reason are all confirmed, the same call books it for real. You do NOT need to "
        "ask which doctor — the system automatically assigns whichever doctor actually has an opening.\n"
        "4. If it succeeds, confirm the booking warmly, including which doctor they're seeing.\n"
        "5. If no one is free at that requested time, apologize and ask ONLY for a different time — the date "
        "and reason stay confirmed, don't re-ask for those.\n\n"
        "If the patient explicitly asks for a real person, or you genuinely cannot help with something, call "
        "request_human_handoff with a short reason, then let them know a team member will follow up shortly.\n\n"
        f"Today's date is {today.isoformat()}.\n\n"
        "STYLE — this matters: reply like a busy front-desk receptionist texting on WhatsApp, not a chatbot. "
        "1-2 short sentences, plain language, no re-explaining things you already said. Ask exactly ONE question "
        "per reply — never stack multiple questions or restate the full list of what you need. If a patient's "
        "wording is ambiguous (e.g. 'may' as in 'maybe' vs. the month May), ask ONE short clarifying question "
        "instead of guessing or listing both interpretations. "
        "Never diagnose or give clinical medical advice — that's the doctor's job, not yours."
    )
    if extra_instructions and extra_instructions.strip():
        base += (
            "\n\nPRACTICE-SPECIFIC INSTRUCTIONS (set by this practice's owner — always follow these first):\n"
            f"{extra_instructions.strip()}\n"
        )
    return base


def _booking_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": (
                    "Record whatever booking details (date/time/reason) you have from the patient's latest "
                    "message, even a single field — call this every time you learn something new, not just once "
                    "everything is known. The system merges it with details already confirmed in earlier turns; "
                    "once all three are present it books for real with whichever doctor is actually free at that "
                    "time — do not ask the patient to pick a doctor."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Appointment date, YYYY-MM-DD, if mentioned this turn"},
                        "time": {"type": "string", "description": "Appointment time, 24-hour HH:MM, if mentioned this turn"},
                        "appointment_type": {
                            "type": "string",
                            "description": "What the visit is for, e.g. 'Consultation', 'Botox', 'Rhinoplasty consultation', if mentioned this turn",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "request_human_handoff",
                "description": "Flag this conversation for a real staff member to take over.",
                "parameters": {
                    "type": "object",
                    "properties": {"reason": {"type": "string", "description": "Short reason a human is needed"}},
                    "required": ["reason"],
                },
            },
        },
    ]


class InboundService:
    """Handles inbound messages from WhatsApp (and later Facebook/Instagram).
    Orchestrates: find practice → find/create conversation → generate AI reply
    (with real booking/escalation tools) → send reply → persist everything."""

    def __init__(self):
        self.llm = LLMService()
        self.agent_log = AgentLogService()
        self.appointments = AppointmentsService()
        self.booking_drafts = BookingDraftStore()
        self.lead_qualification = LeadQualificationService()
        self.portal_auth = PatientPortalAuthService()

    async def handle_whatsapp_message(
        self,
        db: AsyncSession,
        phone_number: str,
        sender_name: str,
        message_text: str,
        instance_id: str,
        content_type: str = "text",
        extra_data: dict | None = None,
    ) -> dict:
        """Full inbound flow for a WhatsApp message."""

        # 1. Find the practice that owns this Green API instance
        practice = await self._find_practice_by_whatsapp_instance(db, instance_id)
        if not practice:
            return {"error": "No practice found for this WhatsApp instance", "handled": False}

        # 2. Find or create the patient by phone number — every patient's
        # phone number is their durable identity here, so the same person
        # texting again always lands back on the same patient record and
        # conversation, first visit or not.
        patient, is_new_patient = await self._find_or_create_patient(db, practice.id, phone_number, sender_name)

        # 3. Find or create the conversation
        conversation = await self._find_or_create_conversation(
            db, practice.id, patient.id, ConversationChannel.WHATSAPP
        )
        await self._ensure_avatar_cached(practice, conversation, phone_number)

        # 4. Save the incoming patient message
        patient_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.PATIENT,
            content=message_text,
            content_type=content_type,
            extra_data=extra_data or {},
        )
        db.add(patient_msg)

        # A staff member replying manually pauses AI auto-reply (see
        # ConversationsService.send_staff_message) so the two never talk
        # over each other. The patient messaging back in doesn't
        # automatically un-pause it — a human already engaged should be the
        # one to hand it back, not have the AI silently reassert control.
        ai_paused = bool((conversation.extra_data or {}).get("ai_paused"))
        conversation.status = ConversationStatus.NEEDS_ATTENTION if ai_paused else ConversationStatus.ACTIVE
        # Touch the conversation so the inbox sorts/previews by this new
        # inbound message. `updated_at` is server_default/onupdate now() —
        # with an unchanged status (e.g. already NEEDS_ATTENTION) no UPDATE
        # would fire and the session would sit stale at the bottom with the
        # old preview, looking like the message never arrived.
        conversation.updated_at = datetime.now(timezone.utc)
        await db.flush()
        # Commit the incoming message on its own, before ever attempting an
        # AI reply. Previously everything below this point ran in the same
        # uncommitted transaction as the patient's message — an LLM failure
        # (rate limit, network blip, anything) raised past this function
        # with nothing committed, silently discarding the message the
        # patient actually sent, not just the missing reply. A message that
        # was truly received must never be lost because of what happens next.
        await db.commit()

        if ai_paused:
            await self.agent_log.log(
                db,
                practice.id,
                agent_type="ai_receptionist",
                action="whatsapp_message_received_ai_paused",
                details={"patient_phone": phone_number, "incoming_preview": message_text[:200]},
                performed_by="system",
            )
            return {
                "handled": True,
                "practice_id": str(practice.id),
                "patient_id": str(patient.id),
                "conversation_id": str(conversation.id),
                "reply": None,
                "sent": False,
                "ai_paused": True,
            }

        # The Agent Settings "AI Receptionist" toggle writes an AgentConfig
        # row for the "receptionist" slug (see AgentSettingsPage.tsx) — honor
        # it so switching the agent off practice-wide actually stops the
        # WhatsApp auto-replies. Missing row = not disabled (default on), the
        # same behavior as the settings page's DEFAULT_AGENT_SETTING.
        cfg_result = await db.execute(
            select(AgentConfig).where(
                AgentConfig.practice_id == practice.id,
                AgentConfig.agent_type == "receptionist",
            )
        )
        cfg = cfg_result.scalar_one_or_none()
        if cfg is not None and not cfg.enabled:
            conversation.status = ConversationStatus.NEEDS_ATTENTION
            await self.agent_log.log(
                db,
                practice.id,
                agent_type="ai_receptionist",
                action="whatsapp_message_received_ai_disabled",
                details={"patient_phone": phone_number, "incoming_preview": message_text[:200]},
                performed_by="system",
            )
            return {
                "handled": True,
                "practice_id": str(practice.id),
                "patient_id": str(patient.id),
                "conversation_id": str(conversation.id),
                "reply": None,
                "sent": False,
                "ai_disabled": True,
            }

        # 5. Generate AI reply using conversation history + real booking/
        # escalation tools — if this fails for any reason (LLM rate limit,
        # network blip, anything), the patient's message is already safely
        # committed above; degrade to flagging a human instead of losing the
        # message or crashing the whole request.
        try:
            ai_reply, escalated, escalation_reason = await self._generate_reply(
                db, practice, patient, conversation, message_text, is_new_patient
            )
        except Exception:
            logger.exception(
                "AI reply generation failed for patient %s (conversation %s)",
                patient.id, conversation.id,
            )
            conversation.status = ConversationStatus.NEEDS_ATTENTION
            db.add(Message(
                conversation_id=conversation.id,
                role=MessageRole.SYSTEM,
                content="⚠️ The AI Receptionist couldn't respond (a technical issue) — please reply directly.",
                content_type="text",
            ))
            await db.flush()
            await self.agent_log.log(
                db,
                practice.id,
                agent_type="ai_receptionist",
                action="whatsapp_ai_reply_failed",
                details={"patient_phone": phone_number, "incoming_preview": message_text[:200]},
                performed_by="system",
            )
            await db.commit()
            return {
                "handled": True,
                "practice_id": str(practice.id),
                "patient_id": str(patient.id),
                "conversation_id": str(conversation.id),
                "reply": None,
                "sent": False,
                "ai_failed": True,
            }

        # 6. Save the AI reply
        agent_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.AGENT,
            content=ai_reply,
            content_type="text",
        )
        db.add(agent_msg)
        if escalated:
            conversation.status = ConversationStatus.NEEDS_ATTENTION
            # Escalating used to only flip the status badge — extra_data.ai_paused
            # (the flag this SAME function checks at the top, and the one
            # send_staff_message sets when a human actually replies) was never
            # touched here. So the very next inbound message from this patient
            # re-read ai_paused as still False and the AI happily auto-replied
            # again, completely undoing its own "I need a human" request. A
            # request_human_handoff call is now durable, exactly like a human
            # manually taking over — it stays off until a staff member
            # resumes it via the "AI replying" toggle (or replies themselves,
            # which also sets this).
            conversation.extra_data = {**(conversation.extra_data or {}), "ai_paused": True}
            reason_text = f": {escalation_reason}" if escalation_reason else ""
            db.add(Message(
                conversation_id=conversation.id,
                role=MessageRole.SYSTEM,
                content=f"🔔 The AI Receptionist requested a human{reason_text}",
                content_type="text",
            ))
        await db.flush()

        # 6b. Score lead fit/intent once enough of the conversation exists to
        # judge — best-effort, never allowed to affect whether the reply
        # itself gets sent.
        try:
            await self.lead_qualification.maybe_qualify(db, patient, conversation.id)
        except Exception:
            logger.exception("Lead qualification step failed for patient %s", patient.id)

        # 7. Send reply back via WhatsApp
        sent = await self._send_reply(practice, phone_number, ai_reply)

        # 8. Log the action
        await self.agent_log.log(
            db,
            practice.id,
            agent_type="ai_receptionist",
            action="whatsapp_ai_escalated" if escalated else "whatsapp_message_handled",
            details={
                "patient_phone": phone_number,
                "incoming_preview": message_text[:200],
                "reply_preview": ai_reply[:200],
                "sent": sent,
            },
            performed_by="ai_agent",
        )
        await db.commit()

        return {
            "handled": True,
            "practice_id": str(practice.id),
            "patient_id": str(patient.id),
            "conversation_id": str(conversation.id),
            "reply": ai_reply,
            "sent": sent,
            "escalated": escalated,
        }

    async def _ensure_avatar_cached(self, practice: Practice, conversation: Conversation, phone_number: str) -> None:
        """Fetches the WhatsApp contact photo once per conversation and
        caches it on extra_data — avoids an extra Green API round trip on
        every single message just to re-fetch a photo that rarely changes.

        Only caches a result once Green API has *definitively* answered
        (a clean 200, even if the answer is "no photo") — Green API's free
        tier gives getAvatar a low monthly call quota that runs out fast,
        and a failed check (quota exceeded, network blip) must not get
        permanently cached as "no photo," or a real photo would never show
        up once quota resets or the transient error clears."""
        extra = conversation.extra_data or {}
        if "avatar_url" in extra:
            return
        ga = WhatsAppGreenAPI.from_practice_settings(practice.settings or {})
        if ga is None:
            return
        try:
            avatar_url, definitive = await ga.get_avatar(phone_number)
        except Exception:
            return
        if not definitive:
            return
        conversation.extra_data = {**extra, "avatar_url": avatar_url}

    async def _find_practice_by_whatsapp_instance(
        self, db: AsyncSession, instance_id: str
    ) -> Practice | None:
        """Find a practice whose settings contain this Green API instance_id."""
        result = await db.execute(select(Practice))
        for practice in result.scalars().all():
            ga = (practice.settings or {}).get("green_api", {})
            if ga.get("instance_id") == instance_id:
                return practice
        return None

    async def _find_or_create_patient(
        self, db: AsyncSession, practice_id: UUID, phone: str, sender_name: str
    ) -> tuple[Patient, bool]:
        """Find existing patient by phone or create a new one. Returns
        (patient, is_new) — the AI's system prompt uses is_new to greet a
        returning patient differently instead of asking who they are again."""
        phone = normalize_phone(phone)
        result = await db.execute(
            select(Patient).where(
                Patient.practice_id == practice_id,
                Patient.phone == phone,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False

        # Green API always reports digits-only (see green_api_poller.py), but
        # a patient's phone on file may have been typed by staff with a "+",
        # spaces, or a leading "0" instead of the country code — none of
        # which match the exact-string lookup above even though it's the
        # same real number. Real bug found live: one contact ended up with
        # a second Patient row (and from there a second Conversation/thread)
        # purely because of this formatting mismatch. Fall back to a
        # normalized comparison across the practice's other patients before
        # concluding this is really someone new — practice patient counts
        # are small enough that this full pass is cheap (same precedent as
        # PracticeService.resolve_doctor_signup_code's own full scan).
        candidates = await db.execute(
            select(Patient).where(Patient.practice_id == practice_id, Patient.phone.isnot(None))
        )
        for candidate in candidates.scalars().all():
            if candidate.phone and normalize_phone(candidate.phone) == phone:
                return candidate, False

        # Split sender_name into first/last
        parts = (sender_name or "Unknown").strip().split(" ", 1)
        first_name = parts[0] if parts else "Unknown"
        last_name = parts[1] if len(parts) > 1 else ""

        patient = Patient(
            practice_id=practice_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            source="WhatsApp",
            lifecycle_stage="contacted",
        )
        db.add(patient)
        await db.flush()
        return patient, True

    async def _find_or_create_conversation(
        self, db: AsyncSession, practice_id: UUID, patient_id: UUID, channel: ConversationChannel
    ) -> Conversation:
        """Find this patient's existing WhatsApp thread or create a new one.

        Two real bugs fixed here (found live: one contact ending up with
        2-3 separate "chats"):
        1. Matching used to ALSO require agent_type == "ai_receptionist" —
           so a thread that started as (say) an appointment-reminder send
           (MessagingService._find_or_create_conversation, agent_type=
           "appointment_reminder") was invisible to this lookup, and the
           patient's next inbound reply spawned a brand-new, separate
           conversation instead of landing in the one they were already
           replying to. Matching now drops agent_type entirely — one row per
           (patient, channel) is the actual WhatsApp thread, same fix as
           MessagingService's identical function.
        2. A RESOLVED thread used to be treated as unusable — "Mark as
           resolved" is a normal, expected staff action, but the very next
           time that same patient texted in, this created ANOTHER new
           conversation rather than reopening theirs. Resolved threads are
           now reactivated (status -> ACTIVE) and reused instead.
        """
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.practice_id == practice_id,
                Conversation.patient_id == patient_id,
                Conversation.channel == channel,
            )
            .order_by(desc(Conversation.updated_at))
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        if existing:
            if existing.status == ConversationStatus.RESOLVED:
                existing.status = ConversationStatus.ACTIVE
                await db.flush()
            return existing

        conversation = Conversation(
            practice_id=practice_id,
            patient_id=patient_id,
            agent_type="ai_receptionist",
            channel=channel,
        )
        db.add(conversation)
        await db.flush()
        return conversation

    async def _find_available_doctor(
        self, db: AsyncSession, practice_id: UUID, when: datetime
    ) -> Doctor | None:
        """Picks whichever active doctor is actually free at `when` — checks
        their recurring working_hours for that weekday (a doctor with no
        working_hours set at all is treated as generally available, matching
        how the seed data's "Test Doctor" was left unconfigured) and that
        they don't already have a conflicting appointment. Returns the first
        match; doesn't try to load-balance between multiple free doctors."""
        weekday_key = _WEEKDAY_KEYS[when.weekday()]
        result = await db.execute(select(Doctor).where(Doctor.practice_id == practice_id, Doctor.is_active == True))  # noqa: E712
        doctors = list(result.scalars().all())

        window_start = when
        window_end = when + timedelta(minutes=_APPOINTMENT_DURATION_MINUTES)

        for doctor in doctors:
            hours = doctor.working_hours or {}
            if hours:
                # This doctor HAS a recurring schedule defined — a weekday
                # simply missing from it (e.g. Amina's hours only list
                # mon/wed/fri) means "doesn't work that day," not "no
                # schedule configured." Conflating the two used to let a
                # Tuesday booking land on a Monday/Wednesday/Friday-only
                # doctor — a real bug caught by testing every weekday, not
                # just one.
                day_windows = hours.get(weekday_key)
                if not day_windows:
                    continue
                fits = False
                for w in day_windows:
                    try:
                        start_h, start_m = (int(x) for x in w["start"].split(":"))
                        end_h, end_m = (int(x) for x in w["end"].split(":"))
                    except (KeyError, ValueError):
                        continue
                    day_start = when.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                    day_end = when.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
                    if day_start <= window_start and window_end <= day_end:
                        fits = True
                        break
                if not fits:
                    continue
            # else: hours is completely empty — no schedule configured for
            # this doctor at all — treat as generally available rather than
            # blocking every booking for someone who just hasn't set hours yet.

            conflict_result = await db.execute(
                select(Appointment).where(
                    Appointment.doctor_id == doctor.id,
                    Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                    Appointment.start_time < window_end,
                    Appointment.end_time > window_start,
                )
            )
            if conflict_result.scalars().first() is not None:
                continue

            return doctor

        return None

    async def _execute_tool(
        self,
        db: AsyncSession,
        practice: Practice,
        patient: Patient,
        tool_name: str,
        tool_args: dict,
        conversation_id: UUID | None = None,
    ) -> tuple[str, bool]:
        """Runs one tool call for real — actual DB reads/writes, never
        LLM-fabricated results. Returns (result_text_for_the_llm, escalate)."""
        if tool_name == "book_appointment":
            draft = tool_args
            if conversation_id is not None:
                draft = await self.booking_drafts.merge(
                    conversation_id,
                    date=tool_args.get("date"),
                    time=tool_args.get("time"),
                    appointment_type=tool_args.get("appointment_type"),
                )

            missing = [f for f in ("date", "time", "appointment_type") if not draft.get(f)]
            if missing:
                return (
                    f"Saved so far: {_format_draft(draft)}. Still missing: {', '.join(missing)}. "
                    "Ask the patient for ONLY the missing item(s), nothing they've already given.",
                    False,
                )

            try:
                when_local = datetime.strptime(f"{draft['date']} {draft['time']}", "%Y-%m-%d %H:%M")
                # The patient means *their* clinic's local time when they say
                # "tomorrow at 2pm". practice.timezone (default UTC) tells us
                # what that local wall-clock actually is in absolute terms —
                # before, this was stamped as naive UTC, shifting every
                # non-UTC clinic's bookings by their timezone offset.
                try:
                    tz = ZoneInfo(practice.timezone or "UTC")
                except Exception:
                    tz = timezone.utc
                when = when_local.replace(tzinfo=tz).astimezone(timezone.utc)
            except (KeyError, ValueError):
                if conversation_id is not None:
                    await self.booking_drafts.clear_field(conversation_id, "date")
                    await self.booking_drafts.clear_field(conversation_id, "time")
                return "Invalid date/time format — ask the patient to confirm a specific date (YYYY-MM-DD) and time.", False

            if when < datetime.now(timezone.utc):
                if conversation_id is not None:
                    await self.booking_drafts.clear_field(conversation_id, "date")
                    await self.booking_drafts.clear_field(conversation_id, "time")
                return "That date/time is in the past — ask the patient for an upcoming date.", False

            doctor = await self._find_available_doctor(db, practice.id, when)
            if doctor is None:
                # Keep the date and reason confirmed — only the time slot
                # didn't work, so only clear that field. Without this, the
                # next turn's draft would be empty again and the model would
                # re-ask for everything, exactly the loop this was built to
                # avoid.
                if conversation_id is not None:
                    await self.booking_drafts.clear_field(conversation_id, "time")
                return (
                    f"No doctor is available at {draft['date']} {draft['time']}. "
                    "Date and reason stay confirmed — ask ONLY for a different time.",
                    False,
                )

            appointment_type = str(draft.get("appointment_type") or "Consultation")
            appointment = await self.appointments.create_appointment(
                db,
                practice.id,
                patient.id,
                doctor.id,
                appointment_type,
                when,
                when + timedelta(minutes=_APPOINTMENT_DURATION_MINUTES),
                notes="Booked by AI Receptionist via WhatsApp",
                # The AI's own reply below IS the confirmation — an automated
                # generic message right behind it would double-message them.
                notify_patient=False,
            )
            await self.agent_log.log(
                db,
                practice.id,
                agent_type="ai_receptionist",
                action="whatsapp_appointment_booked",
                details={
                    "patient_id": str(patient.id),
                    "doctor_id": str(doctor.id),
                    "doctor_name": doctor.name,
                    "appointment_id": str(appointment.id),
                    "start_time": when.isoformat(),
                },
                performed_by="ai_agent",
            )
            if conversation_id is not None:
                await self.booking_drafts.clear(conversation_id)

            # Flag the conversation so the dashboard's sessions view can
            # distinguish "booking just completed" from a plain Q&A exchange —
            # this is what lets the human receptionist notice a WhatsApp
            # booking happened without wading through the transcript.
            if conversation_id is not None:
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conv = conv_result.scalar_one_or_none()
                if conv is not None:
                    conv.extra_data = {
                        **(conv.extra_data or {}),
                        "ai_booked_appointment_id": str(appointment.id),
                        "ai_booked_at": datetime.now(timezone.utc).isoformat(),
                    }

            # First real booking is the natural moment to get this patient
            # onto the portal — best-effort, must never affect the booking
            # confirmation itself (see PatientPortalAuthService.enable_portal,
            # which already swallows its own invite-send failure the same way).
            if not patient.portal_enabled:
                try:
                    await self.portal_auth.enable_portal(db, practice.id, patient.id)
                except Exception:
                    logger.exception("Auto portal-enable after WhatsApp booking failed for patient %s", patient.id)

            # doctor.name is free text — some rows already include "Dr."
            # (e.g. "Dr. Amina Siddiqui"), others don't (e.g. "Test Doctor").
            # Prepending it unconditionally produced "Dr. Dr. Amina Siddiqui".
            display_name = doctor.name if doctor.name.lower().startswith("dr") else f"Dr. {doctor.name}"
            return (
                f"Booked successfully with {display_name} on {draft['date']} at {draft['time']} "
                f"for {appointment_type}. Confirm these exact details back to the patient.",
                False,
            )

        if tool_name == "request_human_handoff":
            reason = str(tool_args.get("reason") or "Patient requested a human / AI could not help.")
            await self.agent_log.log(
                db,
                practice.id,
                agent_type="ai_receptionist",
                action="whatsapp_human_requested",
                details={"patient_id": str(patient.id), "reason": reason},
                performed_by="ai_agent",
            )
            return "A staff member has been notified and will follow up shortly.", True

        return f"Unknown tool: {tool_name}", False

    async def _generate_reply(
        self,
        db: AsyncSession,
        practice: Practice,
        patient: Patient,
        conversation: Conversation,
        new_message: str,
        is_new_patient: bool,
    ) -> tuple[str, bool]:
        """Generate an AI reply using the conversation history for context,
        with real booking/escalation tools available. Returns (reply_text,
        escalated_to_human, escalation_reason)."""
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at))
            .limit(20)
        )
        recent_messages = list(reversed(result.scalars().all()))

        llm_messages = []
        for msg in recent_messages:
            role = "assistant" if msg.role == MessageRole.AGENT else "user"
            llm_messages.append({"role": role, "content": msg.content})
        llm_messages.append({"role": "user", "content": new_message})

        today = datetime.now(timezone.utc).date()
        try:
            today = datetime.now(ZoneInfo(practice.timezone or "UTC")).date()
        except Exception:
            pass
        hints = _extract_booking_hints(new_message, today)
        if hints:
            draft = await self.booking_drafts.merge(conversation.id, **hints)
        else:
            draft = await self.booking_drafts.get(conversation.id)
        custom = (practice.settings or {}).get("ai_receptionist_system_prompt") or None
        system_prompt = _system_prompt(is_new_patient, today, draft, custom)
        tools = _booking_tools()

        first = await self.llm.chat_with_tools(
            messages=llm_messages, tools=tools, system_prompt=system_prompt, tier="low"
        )
        tool_calls = first.get("tool_calls") or []
        if not tool_calls:
            return first.get("content") or "Thanks for reaching out — how can I help?", False, None

        escalated = False
        escalation_reason: str | None = None
        tool_result_messages: list[dict] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                args = {}
            summary, did_escalate = await self._execute_tool(db, practice, patient, tc.function.name, args, conversation.id)
            if did_escalate:
                escalated = True
                escalation_reason = str(args.get("reason") or "").strip() or None
            tool_result_messages.append({"role": "tool", "tool_call_id": tc.id, "content": summary})

        assistant_message = {
            "role": "assistant",
            "content": first.get("content") or None,
            "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ],
        }

        final = await self.llm.chat(
            messages=[*llm_messages, assistant_message, *tool_result_messages],
            system_prompt=system_prompt,
            tier="low",
        )
        return final, escalated, escalation_reason

    async def _send_reply(self, practice: Practice, phone_number: str, message: str) -> bool:
        """Send reply via WhatsApp Green API. Returns True on success.

        A real successful sendMessage call returns a flat
        `{"idMessage": "..."}` (confirmed against the live API directly —
        there's no "sendMessageResult" wrapper). The previous check looked
        for `result["sendMessageResult"]["sent"]`/`"idMessage" in
        result["sendMessageResult"]`, neither of which a real response ever
        has, so this always evaluated to False even on a genuinely
        successful send — every "sent" flag logged for a WhatsApp reply
        this whole session was wrong, though the message itself did go out
        (this only affects the boolean, not delivery)."""
        ga = WhatsAppGreenAPI.from_practice_settings(practice.settings or {})
        if not ga:
            return False
        try:
            result = await ga.send_text(phone_number, message)
            return "idMessage" in result
        except Exception:
            return False
