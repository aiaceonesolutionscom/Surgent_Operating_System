"""Locale resolution for one inbound conversation.

The SOP (s3) calls this "the routing layer" and treats it as the thing that runs
*before* the first word is written: get the market wrong and the currency, price
list, clinic, slot times, compliance rules and register are all wrong with it.
`markets.py` decides which market a single message points at; this module owns
the conversational part of the job:

* a market, once established, is **remembered** — it is stored on the
  conversation and written to the patient record, so follow-ups, reminders and
  quotes keep using the same currency, time zone and clinic (s3.2);
* the patient's own words can still **correct** it later (rank 1 beats
  everything, including our own memory of last week);
* the reply language follows the patient's **current** message, not their file.

Nothing here calls the LLM, and nothing here invents a price: prices, payment
methods and clinic details are read from the practice's own market config.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.models.conversation import Conversation
from src.models.patient import Patient
from src.models.practice import Practice
from src.services.ai_receptionist.markets import (
    MARKETS,
    Market,
    MarketConfig,
    MarketResolution,
    MarketSignal,
    default_market_code,
    detect_language,
    is_working_day,
    market_config,
    normalize_market_code,
    resolve_market,
    timezone_for_text,
)

logger = logging.getLogger(__name__)

# conversation.extra_data["locale"] — one key, so a later phase can read the
# remembered market without another migration.
LOCALE_MEMORY_KEY = "locale"

# Where a place-level hint may already live on the conversation, if some other
# flow (an ad landing, a QR code, a referral link) recorded it. s3.1 rank 5:
# trust the campaign source as a tiebreaker, never over the patient's own words.
_CAMPAIGN_KEYS = ("campaign_source", "ad_source", "referral_source", "utm_source")

# Language codes -> the label the model is told to write in. "en" is deliberate:
# when the signals conflict the SOP says reply in English and ask once — neutral
# formal English, with no regional idiom and no currency, is the safe default.
LANGUAGE_LABELS: dict[str, str] = {
    "roman-ur": "Roman Urdu (Urdu written in Latin letters)",
    "ur": "Urdu (Urdu script)",
    "ar": "Arabic",
    "en-US": "US English",
    "en-GB": "UK English",
    "en": "formal, neutral English (no regional idiom)",
}

_LANGUAGE_ALIASES: dict[str, str] = {
    "urdu": "ur",
    "ur": "ur",
    "ur-pk": "ur",
    "roman urdu": "roman-ur",
    "roman-urdu": "roman-ur",
    "roman urdu (urdu in latin letters)": "roman-ur",
    "ur-latn": "roman-ur",
    "arabic": "ar",
    "ar": "ar",
    "english": "",
    "en": "",
    "us english": "en-US",
    "american english": "en-US",
    "en-us": "en-US",
    "uk english": "en-GB",
    "british english": "en-GB",
    "en-gb": "en-GB",
}

_WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]{2,}")
# Below this many words a message carries no language worth acting on ("ok",
# "5000", "10 August", a location pin) — for those the patient's established
# language is the right answer, not English.
_LANGUAGE_UNDECIDED_MIN_WORDS = 4


@dataclass(frozen=True)
class ConversationLocale:
    """Everything the prompt and the booking flow need to answer as the right
    person in the right market, and nothing more."""

    market: Market | None
    config: MarketConfig | None
    confidence: str
    reason: str
    language_code: str
    currency: str | None
    # IANA zone of the patient, and whether it is an estimate derived from the
    # market rather than from anything the patient said.
    patient_timezone: str
    timezone_estimated: bool
    clinic_timezone: str
    needs_clarification: bool
    from_default: bool
    remembered: bool
    stays_in_english: bool = False
    signals: tuple[MarketSignal, ...] = ()
    # Local time facts about *this* message, so the model can behave correctly at
    # 03:00 patient time without doing date arithmetic itself (s11 quiet hours).
    local_time_label: str = ""
    local_hour: int = 0
    outside_quiet_hours: bool = False
    outside_working_week: bool = False
    # True while the market is only remembered from earlier in the thread rather
    # than re-derived from this message.
    adopted_from_memory: bool = False

    @property
    def language_label(self) -> str:
        return LANGUAGE_LABELS.get(self.language_code, LANGUAGE_LABELS["en"])

    @property
    def market_code(self) -> str | None:
        return self.market.code if self.market else None

    @property
    def is_confident(self) -> bool:
        return self.confidence == "high" and not self.needs_clarification

    def to_memory(self) -> dict:
        """The compact form stored on the conversation, for auditability: what we
        decided, why, and when — never the raw message."""
        return {
            "market": self.market_code,
            "language": self.language_code,
            "timezone": None if self.timezone_estimated else self.patient_timezone,
            "confidence": self.confidence,
            "needs_clarification": self.needs_clarification,
            "reason": self.reason,
            "signals": [f"rank {s.rank}: {s.reason}" for s in self.signals][:6],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class LocaleService:
    """Resolve and remember the market/language of an inbound conversation."""

    def resolve(
        self,
        practice: Practice,
        message_text: str = "",
        patient: Patient | None = None,
        conversation: Conversation | None = None,
        source: str | None = None,
    ) -> ConversationLocale:
        """Route one message. `patient` and `conversation` are optional so the
        same rule can be previewed for a practice with no conversation at all —
        which is exactly what the AI Receptionist monitor shows an owner."""
        settings = practice.settings or {}
        memory = self._memory(conversation) if conversation is not None else {}
        remembered_code = normalize_market_code(memory.get("market")) if memory else None

        resolution = resolve_market(
            message_text,
            phone=patient.phone if patient is not None else None,
            source=source or self._campaign_source(conversation),
            default_market_code=default_market_code(settings, practice.timezone),
        )

        # A remembered market is the conversation's established one (s3.2: once
        # the market is set, use that market's data and record it) and it stands
        # unless this message either states a different place outright (rank 1
        # beats everything, including our own memory of last week) or we are
        # still waiting on the neutral question — a stored guess must not be
        # promoted to an answer.
        stated_now = tuple(s for s in resolution.signals if s.rank == 1 and s.weight >= 3)
        remembered_is_established = bool(remembered_code) and not memory.get("needs_clarification")
        adopted_from_memory = False
        if remembered_is_established and (not stated_now or remembered_code == resolution.market_code):
            resolution = MarketResolution(
                market=MARKETS[remembered_code],
                confidence="high",
                reason="established earlier in this conversation",
                signals=resolution.signals,
            )
            adopted_from_memory = True

        market = resolution.market
        config = market_config(settings, market.code) if market else None

        # Language mirrors the patient's most recent message (s3.2): switch the
        # moment they switch, one language per message, and never answer an
        # English writer in Roman Urdu. A message with no language in it — a
        # number, a date, a location pin — is the one case where their already
        # established language (then their file, then the market default) wins.
        detected = detect_language(message_text)
        stays_in_english = False
        if resolution.needs_clarification:
            # Signals conflict: one neutral question, in formal English, before
            # any market data is used (s3.2).
            language_code = "en"
            stays_in_english = True
        elif detected:
            language_code = detected
        elif len(_WORD_RE.findall(message_text)) >= _LANGUAGE_UNDECIDED_MIN_WORDS:
            market_default = market.language_code if market else "en"
            language_code = market_default if market_default.startswith("en") else "en"
        else:
            language_code = (
                self._normalize_language(memory.get("language") if memory else None)
                or self._normalize_language(patient.preferred_language if patient is not None else None)
                or (market.language_code if market else "en")
            )

        detected_zone = timezone_for_text(message_text, market.code if market else None)
        remembered_zone = None
        if memory and memory.get("timezone"):
            remembered_zone = str(memory["timezone"])
        if detected_zone:
            patient_timezone, estimated = detected_zone, False
        elif remembered_zone:
            patient_timezone, estimated = remembered_zone, False
        elif market:
            # Best available estimate before we know their city. The prompt tells
            # the model this is an estimate and to state the city alongside it.
            patient_timezone, estimated = market.timezone, True
        else:
            patient_timezone, estimated = practice.timezone or "UTC", True

        local_hour, outside_quiet, outside_week, label = self._local_time_facts(
            patient_timezone, market
        )

        return ConversationLocale(
            market=market,
            config=config,
            confidence=resolution.confidence,
            reason=resolution.reason,
            language_code=language_code,
            # Never expose a currency we are not allowed to quote in — while the
            # signals conflict, the reply asks before any market data is used.
            # A practice's own currency override beats the registry default.
            currency=None
            if resolution.needs_clarification or market is None
            else ((config.currency if config and config.currency else market.currency)),
            patient_timezone=patient_timezone,
            timezone_estimated=estimated,
            clinic_timezone=practice.timezone or "UTC",
            needs_clarification=resolution.needs_clarification,
            from_default=resolution.from_default,
            remembered=bool(remembered_code),
            adopted_from_memory=adopted_from_memory,
            stays_in_english=stays_in_english,
            signals=resolution.signals,
            local_time_label=label,
            local_hour=local_hour,
            outside_quiet_hours=outside_quiet,
            outside_working_week=outside_week,
        )

    def preview(self, practice: Practice) -> ConversationLocale:
        """The locale a brand-new patient contacting this practice would get, for
        the dashboard's prompt monitor."""
        return self.resolve(practice)

    def remember(
        self, patient: Patient, conversation: Conversation, locale: ConversationLocale
    ) -> None:
        """Persist the decision: on the conversation always (so the next message
        — and any human reading the thread) sees the same market and language),
        on the patient record only when we are genuinely confident, so a
        one-message guess never rewrites their file."""
        extra = dict(conversation.extra_data or {})
        extra[LOCALE_MEMORY_KEY] = locale.to_memory()
        conversation.extra_data = extra

        if locale.is_confident and locale.market is not None:
            if (patient.preferred_language or "").strip() != locale.language_code:
                patient.preferred_language = locale.language_code

    def describe_for_log(self, locale: ConversationLocale) -> dict:
        """A short, non-identifying summary for the agent log."""
        return {
            "market": locale.market_code,
            "market_label": locale.market.label if locale.market else None,
            "language": locale.language_code,
            "currency": locale.currency,
            "confidence": locale.confidence,
            "needs_clarification": locale.needs_clarification,
            "reason": locale.reason,
        }

    # -- internals ---------------------------------------------------------

    def _memory(self, conversation: Conversation | None) -> dict:
        if conversation is None:
            return {}
        raw = (conversation.extra_data or {}).get(LOCALE_MEMORY_KEY)
        return raw if isinstance(raw, dict) else {}

    def _campaign_source(self, conversation: Conversation | None) -> str | None:
        extra = (conversation.extra_data or {}) if conversation is not None else {}
        for key in _CAMPAIGN_KEYS:
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _normalize_language(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text in LANGUAGE_LABELS:
            return None if text == "en" else text
        lowered = text.lower()
        if lowered in _LANGUAGE_ALIASES:
            # "English" on its own says nothing about which English; that is the
            # market's call, so it deliberately falls through to the market default.
            return _LANGUAGE_ALIASES[lowered] or None
        return None

    def _local_time_facts(
        self, patient_timezone: str, market: Market | None
    ) -> tuple[int, bool, bool, str]:
        """Where the patient is in their own day, so a 03:00 message never gets
        an "I'll call you this afternoon" that means nothing, and proactive
        follow-ups can be refused outright (s11)."""
        try:
            tz = ZoneInfo(patient_timezone)
        except Exception:
            tz = timezone.utc
        now = datetime.now(tz)
        hour = now.hour
        quiet = market.quiet_hours if market else (9, 21)
        outside_quiet = not (quiet[0] <= hour < quiet[1])
        # One rule, shared with the outbound quiet-hours gate (see
        # services/messaging/quiet_hours.py) — the prompt's claim and the
        # scheduler's behaviour must not be able to disagree.
        outside_week = not is_working_day(market, now.weekday())
        label = now.strftime("%A %d %B, %H:%M") + f" ({patient_timezone})"
        return hour, outside_quiet, outside_week, label
