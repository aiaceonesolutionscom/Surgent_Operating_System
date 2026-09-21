"""The market registry — the single source of truth for what changes per market.

Derived from `assets/knowledge_base/Front-Desk-Call-Script-SOP.pdf`:

* s3.1 — the ranked detection signals (what the patient states beats everything,
  including their phone number; a plain-English message is undecided on its own).
* s3.2 — the decision rule (two signals agreeing is enough to act; conflicting
  signals mean one neutral question, asked once, in English).
* s3.4 — what actually changes once the market is known: language default,
  currency, consultation format, regulator/regime.

This module is deliberately pure data + pure functions: no DB, no practice, no
LLM. That keeps the routing rules unit-testable and stops per-market policy from
being scattered across services. Prices and payment methods are NOT here — the
SOP (s7, s9.2, s10.1) forbids quoting or offering anything that is not on that
market's approved list, so they only ever come from the practice's own settings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Market:
    """One market the clinic serves. Everything the receptionist must switch on
    when the market is known."""

    code: str
    label: str
    calling_code: str
    language_code: str
    language_label: str
    currency: str
    timezone: str
    consult_format: str
    regulator: str
    advertising_note: str
    video_first: bool
    # Working week as a label for the prompt AND as weekday indexes (Monday=0)
    # for the quiet-hours gate, so the phrase shown to the model and the rule the
    # scheduler enforces can never drift apart.
    working_week: str
    working_days: tuple[int, ...]
    # s11 — send between 09:00 and 21:00 in the *patient's* local time, never
    # the clinic's. Stored as (start_hour, end_hour), local, inclusive of start.
    quiet_hours: tuple[int, int] = (9, 21)


# s3.4's table, row for row. `timezone` is the patient-side default used to
# state slot offers in "their local time" before they have told us where they
# are; for the US it is a placeholder — the country spans four zones, so the
# practice's own city is the better source once a video consult is booked.
MARKETS: dict[str, Market] = {
    "PK": Market(
        code="PK",
        label="Pakistan",
        calling_code="92",
        language_code="roman-ur",
        language_label="Roman Urdu or Urdu, English on request",
        currency="PKR",
        timezone="Asia/Karachi",
        consult_format="In-person in Karachi / Lahore; video for other cities",
        regulator="PMC / provincial healthcare commissions (PHC)",
        advertising_note=(
            "No guaranteed-outcome claims. Patient consent before any photo or testimonial use."
        ),
        video_first=False,
        working_week="Monday-Friday",
        working_days=(0, 1, 2, 3, 4),
    ),
    "AE": Market(
        code="AE",
        label="UAE",
        calling_code="971",
        language_code="en-US",
        language_label="English first, Arabic on signal",
        currency="AED",
        timezone="Asia/Dubai",
        consult_format="In-person in Dubai; video for GCC patients",
        regulator="DHA / DoH / MoHAP advertising rules",
        advertising_note=(
            "Strict cosmetic advertising rules: no before/after imagery in public channels, "
            "no discount or prize promotions, no superlative claims such as 'best' or 'safest'."
        ),
        video_first=False,
        working_week="Sunday-Thursday",
        working_days=(6, 0, 1, 2, 3),
    ),
    "SA": Market(
        code="SA",
        label="Saudi Arabia",
        calling_code="966",
        language_code="ar",
        language_label="Arabic first, English on signal",
        currency="SAR",
        timezone="Asia/Riyadh",
        consult_format="Video first; patient travels for the procedure",
        regulator="MoH / SFDA advertising rules",
        advertising_note=(
            "No before/after imagery, no superlative claims, and no promotional discounting "
            "of cosmetic procedures."
        ),
        video_first=True,
        working_week="Sunday-Thursday",
        working_days=(6, 0, 1, 2, 3),
    ),
    "US": Market(
        code="US",
        label="United States",
        calling_code="1",
        language_code="en-US",
        language_label="US English (Spanish if the patient uses it)",
        currency="USD",
        timezone="America/New_York",
        consult_format="Video consult first; state licensing applies",
        regulator="HIPAA, state medical boards, FTC advertising rules",
        advertising_note=(
            "HIPAA governs everything identifiable, including the fact that someone is a patient. "
            "Written authorisation before any disclosure or testimonial. Never imply cross-state "
            "care the clinic is not licensed to provide."
        ),
        video_first=True,
        working_week="Monday-Friday",
        working_days=(0, 1, 2, 3, 4),
    ),
    "UK": Market(
        code="UK",
        label="United Kingdom",
        calling_code="44",
        language_code="en-GB",
        language_label="UK English",
        currency="GBP",
        timezone="Europe/London",
        consult_format="Video consult first, then in-person",
        regulator="CQC, GMC, UK GDPR, ASA / CAP advertising rules",
        advertising_note=(
            "ASA / CAP rules prohibit advertising surgical cosmetic procedures in a way that "
            "trivialises them or targets under-18s; UK GDPR governs consent and data-subject rights."
        ),
        video_first=True,
        working_week="Monday-Friday",
        working_days=(0, 1, 2, 3, 4),
    ),
}


def is_working_day(market: Market | None, weekday: int) -> bool:
    """Monday=0. The Gulf weekend (Friday-Saturday in Saudi Arabia, Saturday-
    Sunday in the UAE) is why "just send on a weekday" is not portable."""
    if market is None:
        return weekday < 5
    return weekday in market.working_days


# Strictly stronger than any single signaller: the stricter of the local rule and
# clinic policy always wins (s10.3), and this line is repeated in every prompt.
STRICTER_RULE_WINS = "The stricter of the local rule and clinic policy always wins."

MARKET_CODES: tuple[str, ...] = tuple(MARKETS.keys())

# The patient's own words always beat the phone number (s3.1 rank 1) — an
# expatriate keeping an old +92 number is the exact failure this ranking exists
# to prevent.
_STATED_LOCATION_CUES = (
    "i'm in", "i am in", "im in", "i live in", "living in", "based in", "i'm based",
    "flying in from", "flying from", "coming from", "visiting from", "travelling from",
    "traveling from", "originally from", "i'm from", "i am from", "im from", "we're in",
    "i stay in", "my city is", "writing from", "contacting from", "currently in",
    "outside", "and i'm in",
)

# Country and city aliases. Gulf cities are exact per country (s3.4 rank 4
# explicitly lists "Gulf city names" as a UAE / KSA signal); anything that can
# legitimately belong to two markets is handled by emitting *both* signals so
# they cancel out and force the neutral question rather than a coin flip.
_PLACE_ALIASES: dict[str, tuple[str, ...]] = {
    "PK": (
        "pakistan", "pakistani", "karachi", "lahore", "islamabad", "rawalpindi",
        "faisalabad", "multan", "peshawar", "quetta", "sialkot", "gujranwala", "hyderabad pk",
    ),
    "AE": (
        "uae", "u.a.e", "emirates", "dubai", "abu dhabi", "sharjah", "ajman",
        "ras al khaimah", "al ain", "fujairah",
    ),
    "SA": (
        "saudi", "ksa", "riyadh", "jeddah", "dammam", "makkah", "mecca", "medina",
        "khobar", "jubail",
    ),
    "US": (
        "usa", "u.s.a", "united states", "america", "american", "new york", "houston",
        "chicago", "los angeles", "miami", "dallas", "atlanta", "california",
        "texas", "new jersey", "virginia", "michigan",
    ),
    "UK": (
        "uk", "u.k", "united kingdom", "britain", "british", "england", "scotland",
        "wales", "london", "manchester", "birmingham", "leeds", "glasgow", "bradford",
        "luton", "slough", "bristol",
    ),
}

# Rank 3 — language and script. Urdu-specific letters first: the Arabic block
# alone cannot tell Urdu from Arabic, and both are written in it.
_URDU_SCRIPT_RE = re.compile(r"[\u0679\u0688\u0691\u06ba\u06be\u06d2\u06d3\u06cc]")
_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")

# The markers the SOP names explicitly (s3.1 rank 3), plus a few that are
# equally unambiguous in Roman Urdu. The weak set needs two hits: "hai" or "ji"
# alone shows up in English small talk often enough to mislead.
_ROMAN_URDU_STRONG = ("kya", "kitna", "kitne", "kitni", "mujhe", "karwana", "karwani", "karwana hai")
_ROMAN_URDU_WEAK = (
    "hai", "hain", "nahi", "haan", "kaise", "acha", "theek", "chahiye", "paisa",
    "bhai", "zara", "kaisa", "aisa", "karna", "krna", "bataye", "milega", "hoga",
)

# Rank 4 — currency tokens, spelling variants and number formatting.
_CURRENCY_TOKENS: dict[str, tuple[str, ...]] = {
    "PK": ("pkr", "rs", "rs.", "rupees", "rupaye", "lakh", "lac", "crore"),
    "AE": ("aed", "dhs", "dirham", "dirhams", "dh"),
    "SA": ("sar", "riyal", "riyals", "sr"),
    "US": ("usd", "$", "dollars", "bucks"),
    "UK": ("gbp", "£", "pounds", "quid"),
}

_UK_SPELLINGS = ("colour", "specialise", "specialised", "organise", "favourite", "practise", "centre", "litre", "programme", "mum ")
_US_SPELLINGS = ("color", "specialize", "specialized", "organize", "favorite", "center", "liter", "program ", "mom ")

# City -> IANA zone, for the one thing a market alone cannot answer: what time
# it actually is where the patient is sitting. A US enquiry can be four hours
# off across the country, and s9.1 is explicit that time-zone confusion is the
# single biggest cause of international no-shows. Only cities that appear above
# and have an unambiguous zone are listed; anything else says nothing rather
# than guessing a zone, and the model is told to confirm instead.
CITY_TIMEZONES: dict[str, str] = {
    # Pakistan
    "karachi": "Asia/Karachi", "lahore": "Asia/Karachi", "islamabad": "Asia/Karachi",
    "rawalpindi": "Asia/Karachi", "faisalabad": "Asia/Karachi", "multan": "Asia/Karachi",
    "peshawar": "Asia/Karachi", "quetta": "Asia/Karachi", "sialkot": "Asia/Karachi",
    "gujranwala": "Asia/Karachi",
    # Gulf
    "dubai": "Asia/Dubai", "abu dhabi": "Asia/Dubai", "sharjah": "Asia/Dubai",
    "ajman": "Asia/Dubai", "ras al khaimah": "Asia/Dubai", "al ain": "Asia/Dubai",
    "fujairah": "Asia/Dubai",
    "riyadh": "Asia/Riyadh", "jeddah": "Asia/Riyadh", "dammam": "Asia/Riyadh",
    "makkah": "Asia/Riyadh", "mecca": "Asia/Riyadh", "medina": "Asia/Riyadh",
    "khobar": "Asia/Riyadh", "jubail": "Asia/Riyadh",
    # United States — the country spans four zones, so the city decides
    "new york": "America/New_York", "miami": "America/New_York", "atlanta": "America/New_York",
    "new jersey": "America/New_York", "virginia": "America/New_York", "michigan": "America/Detroit",
    "chicago": "America/Chicago", "dallas": "America/Chicago", "houston": "America/Chicago",
    "texas": "America/Chicago", "los angeles": "America/Los_Angeles", "california": "America/Los_Angeles",
    # United Kingdom — one zone
    "london": "Europe/London", "manchester": "Europe/London", "birmingham": "Europe/London",
    "leeds": "Europe/London", "glasgow": "Europe/London", "bradford": "Europe/London",
    "luton": "Europe/London", "slough": "Europe/London", "bristol": "Europe/London",
}


def timezone_for_text(text: str, market_code: str | None = None) -> str | None:
    """The patient's own zone, when they have named a place we know.

    `market_code` is only used to prefer that market's own cities when a message
    names several ("I'm from Lahore but living in London" — the last-named place
    is almost always the current one, and both are scanned in text order).
    """
    lowered = text.lower()
    hits: list[tuple[int, str]] = []
    for city, zone in CITY_TIMEZONES.items():
        match = re.search(rf"(?<![\w]){re.escape(city)}(?![\w])", lowered)
        if match:
            hits.append((match.start(), zone))
    if not hits:
        return None
    if market_code == "US" and any(zone.startswith("America/") for _, zone in hits):
        return max((h for h in hits if h[1].startswith("America/")), key=lambda h: h[0])[1]
    return max(hits, key=lambda h: h[0])[1]


@dataclass(frozen=True)
class MarketSignal:
    """One hint, with the SOP's own rank so the reason can be shown to a human
    reading the agent log. `weight` is what the decision rule sums."""

    rank: int
    market_code: str
    reason: str
    weight: int


@dataclass(frozen=True)
class MarketResolution:
    """The outcome of routing one message. `confidence` is the SOP's own
    high / medium / low vocabulary, not a probability."""

    market: Market | None
    confidence: str
    reason: str
    signals: tuple[MarketSignal, ...] = ()
    needs_clarification: bool = False
    # True while the market came from a stored/configured default rather than
    # anything the patient did or said — logged for auditability, never shown.
    from_default: bool = False

    @property
    def market_code(self) -> str | None:
        return self.market.code if self.market else None


# ---------------------------------------------------------------------------
# Individual signal detectors
# ---------------------------------------------------------------------------


def _detect_stated_market(text: str) -> list[MarketSignal]:
    """Rank 1. A location cue next to a place name is an explicit statement;
    a bare place name is a weaker mention that still beats the phone number."""
    lowered = text.lower()
    signals: list[MarketSignal] = []
    has_cue = any(cue in lowered for cue in _STATED_LOCATION_CUES)
    for code, aliases in _PLACE_ALIASES.items():
        hit = next((alias for alias in aliases if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", lowered)), None)
        if hit is None:
            continue
        if has_cue:
            signals.append(MarketSignal(1, code, f"patient stated their location ({hit})", 3))
        else:
            signals.append(MarketSignal(1, code, f"place mentioned ({hit})", 2))
    return signals


def _detect_calling_code_market(phone: str | None) -> list[MarketSignal]:
    """Rank 2. Country code — a strong hint but explicitly "not proof": overseas
    nationals routinely keep an old number."""
    if not phone:
        return []
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits:
        return []
    # Longest match first so +1 never shadows +44 / +971 / +92.
    for code in sorted(MARKETS, key=lambda c: -len(MARKETS[c].calling_code)):
        calling = MARKETS[code].calling_code
        if digits.startswith(calling):
            return [MarketSignal(2, code, f"phone country code +{calling}", 2)]
    return []


def detect_language(text: str) -> str | None:
    """The language of one message, or None when it is plain English / undecided.

    Shared by market detection and by the language-switch rule (s3.2: if the
    patient switches language mid-conversation, switch with them on the very
    next reply) so the two can never disagree about what a message is written in.
    """
    if _URDU_SCRIPT_RE.search(text):
        return "ur"
    if _ARABIC_SCRIPT_RE.search(text):
        return "ar"
    lowered = f" {text.lower()} "
    strong = [m for m in _ROMAN_URDU_STRONG if re.search(rf"(?<![\w]){re.escape(m)}(?![\w])", lowered)]
    weak = [m for m in _ROMAN_URDU_WEAK if re.search(rf"(?<![\w]){re.escape(m)}(?![\w])", lowered)]
    if strong or len(weak) >= 2:
        return "roman-ur"
    return None


def _detect_script_market(text: str) -> list[MarketSignal]:
    """Rank 3. Urdu script is Pakistan's; Arabic script is Gulf but cannot tell
    the UAE from Saudi Arabia, so it emits for both and lets them cancel."""
    language = detect_language(text)
    if language == "ur":
        return [MarketSignal(3, "PK", "Urdu script", 2)]
    if language == "ar":
        return [
            MarketSignal(3, "AE", "Arabic script (Gulf, unresolved)", 1),
            MarketSignal(3, "SA", "Arabic script (Gulf, unresolved)", 1),
        ]
    if language == "roman-ur":
        lowered = f" {text.lower()} "
        marker = next(
            (m for m in (*_ROMAN_URDU_STRONG, *_ROMAN_URDU_WEAK) if re.search(rf"(?<![\w]){re.escape(m)}(?![\w])", lowered)),
            "roman urdu",
        )
        return [MarketSignal(3, "PK", f"Roman Urdu ('{marker}')", 2)]
    return []


def _detect_formatting_market(text: str) -> list[MarketSignal]:
    """Rank 4. Currency tokens, UK / US spelling and number formatting."""
    lowered = text.lower()
    signals: list[MarketSignal] = []
    for code, tokens in _CURRENCY_TOKENS.items():
        for token in tokens:
            token_re = re.escape(token) if token not in ("$", "£") else re.escape(token)
            if re.search(rf"(?<![\w]){token_re}(?![\w])" if token.isalpha() else token_re, lowered):
                signals.append(MarketSignal(4, code, f"currency token '{token}'", 1))
                break
    if any(re.search(rf"(?<![\w]){re.escape(s)}(?![\w])", lowered) for s in _UK_SPELLINGS):
        signals.append(MarketSignal(4, "UK", "UK spelling / usage", 1))
    elif any(re.search(rf"(?<![\w]){re.escape(s)}(?![\w])", lowered) for s in _US_SPELLINGS):
        signals.append(MarketSignal(4, "US", "US spelling / usage", 1))
    if re.search(r"\b(1[3-9]|2[0-3]):[0-5]\d\b", text):
        signals.append(MarketSignal(4, "UK", "24-hour clock time", 1))
    return signals


def _detect_source_market(source: str | None) -> list[MarketSignal]:
    """Rank 5. Campaign / ad source. A tiebreaker only — "never over the
    patient's own words" — so it carries the smallest weight."""
    if not source:
        return []
    lowered = source.lower()
    for code, aliases in _PLACE_ALIASES.items():
        hit = next((a for a in aliases if re.search(rf"(?<![\w]){re.escape(a)}(?![\w])", lowered)), None)
        if hit:
            return [MarketSignal(5, code, f"lead source '{source}'", 1)]
    return []


def detect_signals(
    text: str, phone: str | None = None, source: str | None = None
) -> tuple[MarketSignal, ...]:
    """Every signal the SOP's rank 1-5 produces for one message.

    Rank 6 (time the message arrives) is intentionally absent: on its own it can
    only say "probably not this market", which cannot pick one of five, and the
    SOP itself calls it the weakest signal and forbids using it alone.
    """
    signals: list[MarketSignal] = []
    signals.extend(_detect_stated_market(text))
    signals.extend(_detect_calling_code_market(phone))
    signals.extend(_detect_script_market(text))
    signals.extend(_detect_formatting_market(text))
    signals.extend(_detect_source_market(source))
    return tuple(signals)


# ---------------------------------------------------------------------------
# The decision rule
# ---------------------------------------------------------------------------


def resolve_market(
    text: str,
    phone: str | None = None,
    source: str | None = None,
    default_market_code: str | None = None,
) -> MarketResolution:
    """Apply s3.1-3.2's decision rule to one message.

    The ranking is a *priority order*, not a score to be summed: the strongest
    signal available decides, and a second signal pointing at the same market is
    what makes the read confident. Two strong hints cannot be outvoted by three
    weak ones, which is the failure a summed score produces ("+1 number, but the
    words '£' and 'colour' appear" must not become a UK enquiry).

    * A stated location wins outright, whatever any other signal says.
    * Signals at the strongest rank that name *different* markets are a genuine
      conflict: reply in English and ask the one neutral question.
    * A lone weak hint (rank 4-5) is not enough on its own: the clinic's own home
      market beats it, and if the two disagree, ask rather than quote.
    * Nothing at all falls back to the practice's configured home market — a
      decision the practice made, not a guess by the model.
    """
    signals = detect_signals(text, phone, source)
    stated = [s for s in signals if s.rank == 1 and s.weight >= 3]
    if stated:
        counts: dict[str, int] = {}
        for signal in stated:
            counts[signal.market_code] = counts.get(signal.market_code, 0) + 1
        winner = max(counts, key=lambda code: counts[code])
        return MarketResolution(
            market=MARKETS[winner],
            confidence="high",
            reason=next(s.reason for s in stated if s.market_code == winner),
            signals=signals,
        )

    fallback = MARKETS.get((default_market_code or "").upper())
    if not signals:
        if fallback is not None:
            return MarketResolution(
                market=fallback,
                confidence="medium",
                reason=f"no signal in the message; using the clinic's home market ({fallback.label})",
                signals=signals,
                from_default=True,
            )
        return MarketResolution(
            market=None,
            confidence="low",
            reason="no usable signal — market not yet known",
            signals=signals,
            needs_clarification=True,
        )

    best_rank = min(signal.rank for signal in signals)
    strongest = [s for s in signals if s.rank == best_rank]
    strongest_markets = {s.market_code for s in strongest}
    if len(strongest_markets) > 1:
        # Two equally strong signals naming different markets — Arabic script
        # (Gulf, unresolved) is the routine case: the UAE and Saudi Arabia
        # cannot be told apart from the script itself.
        leader = sorted(strongest_markets)[0]
        return MarketResolution(
            market=MARKETS[leader],
            confidence="low",
            reason="conflicting signals ("
            + ", ".join(MARKETS[c].label for c in sorted(strongest_markets))
            + ")",
            signals=signals,
            needs_clarification=True,
        )

    winner = strongest[0].market_code
    agreeing = [s for s in signals if s.market_code == winner and s.rank != best_rank]

    if best_rank <= 3:
        reason = "; ".join(s.reason for s in strongest + agreeing) if agreeing else strongest[0].reason
        if agreeing:
            return MarketResolution(market=MARKETS[winner], confidence="high", reason=reason, signals=signals)
        # A single decent hint (a country code alone, or Roman Urdu alone) is
        # enough to act on, but not enough to be certain of it.
        return MarketResolution(market=MARKETS[winner], confidence="medium", reason=reason, signals=signals)

    # Only weak hints — a currency symbol, a spelling variant. If they point at
    # the clinic's own market, fine; if they contradict it, that is exactly the
    # case the neutral question exists for.
    if fallback is not None and fallback.code == winner:
        return MarketResolution(
            market=fallback,
            confidence="medium",
            reason=f"weak hint consistent with the clinic's home market ({fallback.label}): {strongest[0].reason}",
            signals=signals,
            from_default=True,
        )
    return MarketResolution(
        market=fallback or MARKETS[winner],
        confidence="low",
        reason=f"only a weak hint to go on ({strongest[0].reason})",
        signals=signals,
        needs_clarification=True,
    )


# ---------------------------------------------------------------------------
# Helpers for reading a practice's configuration
# ---------------------------------------------------------------------------


def normalize_market_code(value: str | None) -> str | None:
    """Accept whatever an owner typed into settings — 'Pakistan', 'pk', 'UAE',
    'Dubai' — and return a registry code, or None if it means nothing."""
    if not value:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    upper = candidate.upper()
    if upper in MARKETS:
        return upper
    lowered = candidate.lower()
    for code, aliases in _PLACE_ALIASES.items():
        if lowered == code.lower() or lowered == MARKETS[code].label.lower():
            return code
        if re.search(rf"(?<![\w]){re.escape(lowered)}(?![\w])", " ".join(aliases)):
            return code
    return None


def market_for_timezone(timezone_name: str | None) -> str | None:
    """Infer a practice's home market from its IANA time zone — the fallback of
    the fallback, for practices set up before they had a market configured."""
    if not timezone_name:
        return None
    tz = timezone_name.strip()
    if tz.startswith("Asia/Karachi"):
        return "PK"
    if tz.startswith("Asia/Dubai"):
        return "AE"
    if tz.startswith("Asia/Riyadh"):
        return "SA"
    if tz.startswith("America/") or tz.startswith("US/"):
        return "US"
    if tz.startswith("Europe/London") or tz.startswith("Europe/Belfast"):
        return "UK"
    return None


@dataclass(frozen=True)
class MarketConfig:
    """A practice's own per-market configuration, read from
    `Practice.settings["markets"][<code>]`. Every field is optional: an owner who
    has configured nothing gets the registry defaults and the model is told not
    to quote a price at all rather than invent one."""

    market: Market
    # The practice's own override of the registry currency — a Dubai clinic may
    # legitimately quote USD, and the registry's default must never silently win
    # over something the owner actually chose. None means "use the registry's".
    currency: str | None = None
    clinic_name: str | None = None
    # Legacy single-city field — kept in sync with clinics[0].city so any
    # reader still using it (prompt fallback, old UI) doesn't break.
    clinic_city: str | None = None
    # One or more physical branches in this market, each its own city +
    # address — a practice with more than one clinic in the same country
    # (e.g. Lahore and Karachi both routing to PK) lists them all here so the
    # receptionist can name the right one instead of just the country.
    clinics: tuple[dict, ...] = ()
    # procedure -> "starts from" string, already carrying its own currency.
    prices: dict[str, str] = field(default_factory=dict)
    consultation_fee: str | None = None
    payment_methods: str | None = None
    languages: tuple[str, ...] = ()
    raw: dict = field(default_factory=dict)


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def market_config(settings: dict | None, code: str) -> MarketConfig:
    """Read one market's configuration out of practice settings."""
    market = MARKETS[code]
    block = ((settings or {}).get("markets") or {}).get(code) or {}
    if not isinstance(block, dict):
        block = {}
    raw_prices = block.get("prices") or {}
    prices: dict[str, str] = {}
    if isinstance(raw_prices, dict):
        for key, value in raw_prices.items():
            text = _as_str(value)
            if text:
                prices[str(key)] = text
    raw_languages = block.get("languages")
    languages: tuple[str, ...] = ()
    if isinstance(raw_languages, (list, tuple)):
        languages = tuple(str(item).strip() for item in raw_languages if str(item).strip())
    elif isinstance(raw_languages, str) and raw_languages.strip():
        languages = tuple(part.strip() for part in raw_languages.split(",") if part.strip())

    raw_clinics = block.get("clinics")
    clinics: tuple[dict, ...] = ()
    if isinstance(raw_clinics, (list, tuple)):
        cleaned_clinics = []
        for entry in raw_clinics:
            if not isinstance(entry, dict):
                continue
            city = _as_str(entry.get("city"))
            if not city:
                continue
            cleaned_clinics.append({"city": city, "address": _as_str(entry.get("address"))})
        clinics = tuple(cleaned_clinics)

    legacy_city = _as_str(block.get("clinic_city") or block.get("city"))
    # Backward compatible in both directions: an old single-city config with
    # no `clinics` list yet still produces one clinic entry; a practice that
    # has since added a `clinics` list gets its first city mirrored onto the
    # legacy field for anything not yet reading the list.
    if not clinics and legacy_city:
        clinics = ({"city": legacy_city, "address": None},)
    clinic_city = legacy_city or (clinics[0]["city"] if clinics else None)

    return MarketConfig(
        market=market,
        currency=(_as_str(block.get("currency")) or "").upper() or None,
        clinic_name=_as_str(block.get("clinic_name")),
        clinic_city=clinic_city,
        clinics=clinics,
        prices=prices,
        consultation_fee=_as_str(block.get("consultation_fee")),
        payment_methods=_as_str(block.get("payment_methods")),
        languages=languages,
        raw=block,
    )


def default_market_code(settings: dict | None, practice_timezone: str | None = None) -> str | None:
    """The practice's home market, most explicit source first: `settings.default_market`,
    then any single configured market block, then the practice's time zone."""
    settings = settings or {}
    code = normalize_market_code(_as_str(settings.get("default_market")))
    if code:
        return code
    configured = settings.get("markets")
    if isinstance(configured, dict):
        valid = [c for c in configured if normalize_market_code(c)]
        if len(valid) == 1:
            return normalize_market_code(valid[0])
    return market_for_timezone(practice_timezone)
