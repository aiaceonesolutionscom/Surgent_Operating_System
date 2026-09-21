"""When the clinic is allowed to message a patient — SOP s11.

    "Send between 09:00 and 21:00 in the patient's local time, never the
     clinic's. A reminder at 3am loses the patient and, in some markets,
     breaches messaging rules."
    "Automated reminders must be scheduled against the stored patient time zone,
     not the server's."

Until now every outbound message in this codebase was stamped against the
server clock, so a Pakistani practice on UTC sent appointment reminders at 3am
local time. This module answers two questions for `MessagingService`:

1. **Which time zone is the patient actually in?** There is no
   `patients.timezone` column yet, so it is resolved from the most reliable
   source available, in order: the zone the patient themselves stated (stored
   by `LocaleService` on their conversation), a zone on their record, the time
   zone of the market their conversation routed to, then the practice's own.
2. **Is this the right moment to send?** Not every message is the same kind —
   see `MessageTiming`. A receipt for a payment the patient just made is not
   the same as a nurture message three weeks into silence.

It also owns the other half of the same problem: rendering a time *for* the
patient. `format_for_patient` states a moment in their zone first and the
clinic's second, which is what the SOP's own confirmation scripts do —
"Tuesday 4:30pm your time in [city] — that's [time] here" — and what stops an
appointment reminder from arriving with a UTC clock face on it.

Nothing here sends anything; `MessagingService` calls it before every send, and
a refusal is deferred to the next poll run rather than dropped.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.models.patient import Patient
from src.models.practice import Practice
from src.services.ai_receptionist.locale_service import LOCALE_MEMORY_KEY
from src.services.ai_receptionist.markets import (
    MARKETS,
    Market,
    default_market_code,
    is_working_day,
    normalize_market_code,
)

logger = logging.getLogger(__name__)


class MessageTiming(str, enum.Enum):
    """Not every outbound message earns the same restraint."""

    # The patient or a staff member just acted (booking confirmation, receipt,
    # a human replying now). Sending immediately is the expected behaviour and
    # is what the person on the other end is waiting for.
    ON_DEMAND = "on_demand"
    # Scheduled and patient-relevant, but not something they asked for *right
    # now*: appointment reminders, post-op check-ins. Wake-up hours only.
    REMINDER = "reminder"
    # The clinic chasing a lead: nurture cadence, offers, win-back. Wake-up
    # hours AND the market's working week — nobody wants marketing on their
    # Saturday in Riyadh.
    PROACTIVE = "proactive"


@dataclass(frozen=True)
class PatientTimingContext:
    """Where the patient is, what market that implies, and how we know."""

    timezone: str
    market: Market | None
    source: str


@dataclass(frozen=True)
class TimingDecision:
    allowed: bool
    timing: MessageTiming
    timezone: str
    local_time_label: str
    reason: str
    next_allowed_label: str | None = None
    source: str = ""

    def as_log_details(self) -> dict:
        return {
            "timing": self.timing.value,
            "patient_timezone": self.timezone,
            "patient_local_time": self.local_time_label,
            "timezone_source": self.source,
            "reason": self.reason,
            "next_allowed": self.next_allowed_label,
        }


def format_for_patient(
    moment: datetime, patient_timezone: str, clinic_timezone: str | None = None
) -> str:
    """Render an appointment time the way the SOP's scripts say it aloud: the
    patient's own clock first, the clinic's second, and only when the two
    actually differ.

    `moment` is treated as UTC when it carries no zone — every appointment in
    this codebase is stored that way (see InboundService._execute_tool, which
    converts the patient's stated wall-clock from the practice's zone into UTC).
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        local = moment.astimezone(ZoneInfo(patient_timezone))
    except Exception:
        local = moment.astimezone(timezone.utc)
    when = local.strftime("%A, %B %d at %I:%M %p").replace(" 0", " ")

    if clinic_timezone:
        try:
            clinic = moment.astimezone(ZoneInfo(clinic_timezone))
        except Exception:
            return when
        if clinic.utcoffset() != local.utcoffset():
            when += f" your time ({clinic.strftime('%I:%M %p').lstrip('0')} at the clinic)"
    return when


def _valid_zone(name: object) -> str | None:
    if not name:
        return None
    try:
        ZoneInfo(str(name))
    except Exception:
        return None
    return str(name)


async def resolve_patient_timing_context(
    db: AsyncSession, practice: Practice, patient: Patient
) -> PatientTimingContext:
    """The patient's own zone where we know it, otherwise their market's."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.practice_id == practice.id,
            Conversation.patient_id == patient.id,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(1)
    )
    conversation = result.scalar_one_or_none()
    memory = (conversation.extra_data or {}).get(LOCALE_MEMORY_KEY) if conversation else None
    memory = memory if isinstance(memory, dict) else {}

    # 1. The zone the patient stated during their own conversation — the only
    #    source here that is a fact about them rather than an inference.
    stated_zone = _valid_zone(memory.get("timezone"))
    market = MARKETS.get(normalize_market_code(memory.get("market")) or "")
    if stated_zone:
        return PatientTimingContext(timezone=stated_zone, market=market, source="patient_stated")

    # 2. A zone on the patient's own record. `communication_preferences` is the
    #    existing JSONB blob for "how and when to reach this patient", so a
    #    staff member (or the portal) can pin a zone there without a migration.
    #    A dedicated `patients.timezone` column is the right long-term home.
    preferences = patient.communication_preferences or {}
    record_zone = _valid_zone(preferences.get("timezone") if isinstance(preferences, dict) else None)
    if record_zone:
        return PatientTimingContext(timezone=record_zone, market=market, source="patient_record")

    # 3. The market their conversation routed to (SOP s3.4's own time zone).
    if market is not None:
        return PatientTimingContext(timezone=market.timezone, market=market, source=f"market:{market.code}")

    # 4. The clinic's home market, which is the best guess a single-market
    #    practice can make for a patient who has never said where they are.
    home = MARKETS.get(default_market_code(practice.settings or {}, practice.timezone) or "")
    if home is not None:
        return PatientTimingContext(timezone=home.timezone, market=home, source=f"clinic_market:{home.code}")

    return PatientTimingContext(timezone=practice.timezone or "UTC", market=None, source="clinic")


def evaluate_timing(
    context: PatientTimingContext, timing: MessageTiming, now: datetime | None = None
) -> TimingDecision:
    """Whether `timing`'s kind of message may go out at this moment."""
    try:
        tz = ZoneInfo(context.timezone)
    except Exception:
        tz = timezone.utc
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    quiet_start, quiet_end = (context.market.quiet_hours if context.market else (9, 21))
    label = local_now.strftime("%A %d %B, %H:%M") + f" ({context.timezone})"

    if timing is MessageTiming.ON_DEMAND:
        return TimingDecision(
            allowed=True,
            timing=timing,
            timezone=context.timezone,
            local_time_label=label,
            reason="Patient or staff initiated — sending now.",
            source=context.source,
        )

    outside_hours = not (quiet_start <= local_now.hour < quiet_end)
    off_day = timing is MessageTiming.PROACTIVE and not is_working_day(context.market, local_now.weekday())

    if not outside_hours and not off_day:
        return TimingDecision(
            allowed=True,
            timing=timing,
            timezone=context.timezone,
            local_time_label=label,
            reason=f"Inside the patient's {quiet_start:02d}:00-{quiet_end:02d}:00 window.",
            source=context.source,
        )

    reasons = []
    if outside_hours:
        reasons.append(f"it is {local_now.strftime('%H:%M')} for the patient, outside {quiet_start:02d}:00-{quiet_end:02d}:00")
    if off_day:
        reasons.append(
            "it is outside this market's working week"
            + (f" ({context.market.working_week})" if context.market else "")
        )
    return TimingDecision(
        allowed=False,
        timing=timing,
        timezone=context.timezone,
        local_time_label=label,
        reason="Held back because " + " and ".join(reasons) + " in their local time.",
        next_allowed_label=_next_allowed_label(context, quiet_start, timing, now=now),
        source=context.source,
    )


def _next_allowed_label(
    context: PatientTimingContext, quiet_start: int, timing: MessageTiming, now: datetime | None = None
) -> str:
    """The next moment this message *would* go out — shown to staff so a held
    message doesn't look lost, and written to the agent log."""
    try:
        tz = ZoneInfo(context.timezone)
    except Exception:
        tz = timezone.utc
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    candidate = local_now
    if local_now.hour >= (context.market.quiet_hours[1] if context.market else 21):
        candidate = (local_now + timedelta(days=1)).replace(
            hour=quiet_start, minute=0, second=0, microsecond=0
        )
    else:
        candidate = local_now.replace(hour=quiet_start, minute=0, second=0, microsecond=0)
    # A proactive message also waits for a working day (at most a two-day walk,
    # which covers both Gulf weekends).
    for _ in range(3):
        if timing is not MessageTiming.PROACTIVE or is_working_day(context.market, candidate.weekday()):
            break
        candidate = candidate + timedelta(days=1)
    return candidate.strftime("%A %d %B, %H:%M") + f" ({context.timezone})"


async def evaluate_patient_timing(
    db: AsyncSession,
    practice_id: UUID,
    patient: Patient,
    timing: MessageTiming,
    now: datetime | None = None,
) -> TimingDecision:
    """Resolve the patient's zone, then decide whether to send right now."""
    practice = await load_practice(db, practice_id)
    if practice is None:
        # A missing practice row means nothing else on this path works either —
        # never turn missing configuration into a quiet-hours refusal.
        return TimingDecision(
            allowed=True,
            timing=timing,
            timezone="UTC",
            local_time_label="",
            reason="Practice not found — quiet hours not applied.",
            source="none",
        )
    context = await resolve_patient_timing_context(db, practice, patient)
    return evaluate_timing(context, timing, now=now)


async def load_practice(db: AsyncSession, practice_id: UUID) -> Practice | None:
    """Small convenience for senders that only carry a practice id."""
    result = await db.execute(select(Practice).where(Practice.id == practice_id))
    return result.scalar_one_or_none()
