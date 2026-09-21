"""The AI Receptionist's routing layer — market/language detection (SOP s3) and
the prompt blocks built from it (Appendix A).

Pure unit tests: no database, no LLM. Every rule asserted here is a line in
`assets/knowledge_base/Front-Desk-Call-Script-SOP.pdf`, and the failure each one
prevents is quoting the wrong currency, answering in the wrong language, or
promising a 03:00 reply.
"""

from __future__ import annotations

from datetime import date

from src.models.conversation import Conversation
from src.models.patient import Patient
from src.models.practice import Practice
from src.services.ai_receptionist.locale_service import ConversationLocale, LocaleService
from src.services.ai_receptionist.markets import (
    MARKETS,
    default_market_code,
    market_config,
    normalize_market_code,
    resolve_market,
    timezone_for_text,
)
from src.services.ai_receptionist.prompt_blocks import build_system_prompt

PAKISTAN_NUMBER = "923001234567"
UAE_NUMBER = "971501234567"
UK_NUMBER = "447700900123"
US_NUMBER = "12125550100"


def _practice(*, timezone_name: str = "Asia/Karachi", settings: dict | None = None, name: str = "Aiaceone Clinic") -> Practice:
    return Practice(name=name, settings=settings or {}, timezone=timezone_name)


def _patient(phone: str | None = None, preferred_language: str | None = None) -> Patient:
    return Patient(first_name="Ayesha", last_name="Khan", phone=phone, preferred_language=preferred_language)


def _conversation(extra_data: dict | None = None) -> Conversation:
    return Conversation(extra_data=extra_data or {})


# ---------------------------------------------------------------------------
# Market detection (s3.1-3.2)
# ---------------------------------------------------------------------------


def test_stated_location_beats_the_phone_country_code():
    """s3.1 rank 1: an expatriate keeping an old +92 number must not be quoted PKR."""
    resolution = resolve_market("I'm in Dubai, how much for a rhinoplasty?", phone=PAKISTAN_NUMBER)

    assert resolution.market is not None and resolution.market.code == "AE"
    assert resolution.confidence == "high"


def test_country_code_alone_is_enough_to_act_but_not_to_be_certain():
    resolution = resolve_market("Hi, what is the price of a facelift?", phone=PAKISTAN_NUMBER)

    assert resolution.market is not None and resolution.market.code == "PK"
    assert resolution.confidence == "medium"


def test_urdu_script_points_at_pakistan():
    resolution = resolve_market("مجھے ناک کی سرجری کا ریٹ بتائیں")

    assert resolution.market is not None and resolution.market.code == "PK"


def test_arabic_script_alone_is_a_gulf_tie_not_a_guess():
    """Arabic cannot separate the UAE from Saudi Arabia — ask, do not pick."""
    resolution = resolve_market("مرحبا، كم سعر العملية؟")

    assert resolution.needs_clarification is True
    assert resolution.confidence == "low"


def test_arabic_script_with_a_uae_number_resolves_to_the_uae():
    resolution = resolve_market("مرحبا، كم سعر العملية؟", phone=UAE_NUMBER)

    assert resolution.market is not None and resolution.market.code == "AE"
    assert resolution.confidence == "high"


def test_roman_urdu_points_at_pakistan():
    resolution = resolve_market("kya price kitna hai")

    assert resolution.market is not None and resolution.market.code == "PK"


def test_no_signal_uses_the_clinics_own_home_market():
    resolution = resolve_market("Hello", default_market_code="PK")

    assert resolution.market is not None and resolution.market.code == "PK"
    assert resolution.from_default is True


def test_no_signal_and_no_home_market_asks_instead_of_guessing():
    resolution = resolve_market("Hello")

    assert resolution.market is None
    assert resolution.needs_clarification is True


def test_a_lone_weak_hint_does_not_beat_the_clinics_home_market():
    """A currency symbol on its own is not a market (s3.1 rank 4)."""
    resolution = resolve_market("Is it about £400?", default_market_code="PK")

    assert resolution.needs_clarification is True
    assert resolution.confidence == "low"


def test_a_lone_weak_hint_that_agrees_with_the_home_market_is_accepted():
    resolution = resolve_market("Is it about £400?", default_market_code="UK")

    assert resolution.market is not None and resolution.market.code == "UK"
    assert resolution.needs_clarification is False


def test_a_dropped_place_name_is_a_hint_not_a_statement():
    resolution = resolve_market("Is your Dubai clinic open on Fridays?")

    assert resolution.market is not None and resolution.market.code == "AE"
    assert resolution.confidence == "medium"


def test_city_timezones_use_the_last_place_named():
    assert timezone_for_text("I'm in Houston") == "America/Chicago"
    assert timezone_for_text("I'm from Lahore but living in London") == "Europe/London"
    assert timezone_for_text("Hello there") is None


def test_default_market_code_prefers_the_explicit_setting():
    assert default_market_code({"default_market": "Pakistan"}) == "PK"
    assert default_market_code({"markets": {"UK": {}}}) == "UK"
    assert default_market_code({}, "Asia/Karachi") == "PK"
    assert default_market_code({}) is None


def test_normalize_market_code_accepts_what_an_owner_typed():
    assert normalize_market_code("pk") == "PK"
    assert normalize_market_code("UAE") == "AE"
    assert normalize_market_code("Dubai") == "AE"
    assert normalize_market_code("Saudi Arabia") == "SA"
    assert normalize_market_code("Mars") is None


def test_market_config_reads_the_practices_own_price_list():
    settings = {
        "markets": {
            "PK": {
                "clinic_city": "Lahore",
                "prices": {"Rhinoplasty": "PKR 900,000"},
                "consultation_fee": "PKR 5,000",
                "payment_methods": "Bank transfer or card at the clinic",
            }
        }
    }
    config = market_config(settings, "PK")

    assert config.prices == {"Rhinoplasty": "PKR 900,000"}
    assert config.clinic_city == "Lahore"
    assert config.consultation_fee == "PKR 5,000"


def test_every_market_carries_a_currency_and_a_compliance_note():
    for code, market in MARKETS.items():
        assert market.currency
        assert market.advertising_note
        assert market.regulator
        assert market.code == code


# ---------------------------------------------------------------------------
# Locale resolution (locale_service)
# ---------------------------------------------------------------------------


def test_resolve_routes_a_pakistani_number_to_pkr_and_roman_urdu():
    locale = LocaleService().resolve(
        _practice(), "kya rhinoplasty ka price kitna hai?", _patient(PAKISTAN_NUMBER)
    )

    assert locale.market_code == "PK"
    assert locale.currency == "PKR"
    assert locale.language_code == "roman-ur"


def test_a_long_english_message_is_answered_in_english_even_after_roman_urdu():
    """s3.2: mirror the most recent message; never answer an English writer in
    Roman Urdu."""
    conversation = _conversation({"locale": {"market": "PK", "language": "roman-ur"}})
    locale = LocaleService().resolve(
        _practice(), "Actually what are the timings for the clinic on Friday?", _patient(PAKISTAN_NUMBER), conversation
    )

    assert locale.language_code == "en"


def test_a_message_with_no_language_in_it_keeps_the_established_language():
    conversation = _conversation({"locale": {"market": "PK", "language": "roman-ur"}})
    locale = LocaleService().resolve(_practice(), "10 August", _patient(PAKISTAN_NUMBER), conversation)

    assert locale.language_code == "roman-ur"


def test_the_patients_own_words_override_the_remembered_market():
    conversation = _conversation({"locale": {"market": "PK", "language": "roman-ur"}})
    locale = LocaleService().resolve(
        _practice(), "I'm in London now, can I book a consultation?", _patient(PAKISTAN_NUMBER), conversation
    )

    assert locale.market_code == "UK"
    assert locale.currency == "GBP"


def test_a_remembered_market_survives_a_stray_currency_symbol():
    conversation = _conversation({"locale": {"market": "PK", "language": "roman-ur"}})
    locale = LocaleService().resolve(
        _practice(), "And how much is the filler, is it $200?", _patient(PAKISTAN_NUMBER), conversation
    )

    assert locale.market_code == "PK"
    assert locale.currency == "PKR"


def test_conflicting_signals_stay_in_neutral_english_with_no_currency():
    locale = LocaleService().resolve(_practice(), "مرحبا، كم سعر العملية؟")

    assert locale.needs_clarification is True
    assert locale.stays_in_english is True
    assert locale.language_code == "en"


def test_remember_writes_the_conversation_and_only_labels_a_confident_patient():
    service = LocaleService()
    patient = _patient(PAKISTAN_NUMBER)
    conversation = _conversation()
    locale = service.resolve(_practice(), "kya price kitna hai", patient, conversation)
    service.remember(patient, conversation, locale)

    assert conversation.extra_data["locale"]["market"] == "PK"
    assert conversation.extra_data["locale"]["confidence"] == "high"
    assert patient.preferred_language == "roman-ur"

    unclear_patient = _patient()
    unclear_conversation = _conversation()
    unclear = service.resolve(_practice(), "مرحبا، كم سعر العملية؟", unclear_patient, unclear_conversation)
    service.remember(unclear_patient, unclear_conversation, unclear)

    assert unclear_patient.preferred_language is None


def test_preview_needs_no_conversation_and_is_always_usable_for_the_monitor():
    locale = LocaleService().preview(_practice(settings={"default_market": "UK"}))

    assert locale.market_code == "UK"
    assert locale.language_code == "en-GB"


# ---------------------------------------------------------------------------
# Prompt composition (Appendix A)
# ---------------------------------------------------------------------------


def _pakistan_practice() -> Practice:
    return _practice(
        settings={
            "default_market": "PK",
            "markets": {
                "PK": {
                    "clinic_city": "Lahore",
                    "prices": {"Rhinoplasty": "PKR 900,000"},
                    "consultation_fee": "PKR 5,000",
                }
            },
        }
    )


def _prompt(locale: ConversationLocale | None, *, custom: str | None = None, channel: str = "whatsapp") -> str:
    return build_system_prompt(
        practice_name="Aiaceone Clinic",
        is_new_patient=True,
        today=date(2026, 9, 19),
        draft=None,
        locale=locale,
        custom_instructions=custom,
        channel=channel,
    )


def test_prompt_carries_the_markets_currency_and_approved_price_list():
    practice = _pakistan_practice()
    locale = LocaleService().resolve(practice, "kya price kitna hai", _patient(PAKISTAN_NUMBER))
    prompt = _prompt(locale)

    assert "PKR 900,000" in prompt
    assert "PKR 5,000" in prompt
    assert "Roman Urdu" in prompt
    assert "GUARDRAILS" in prompt
    assert "ESCALATION" in prompt


def test_prompt_refuses_to_quote_when_no_price_list_is_configured():
    practice = _practice(settings={"default_market": "PK"})
    locale = LocaleService().resolve(practice, "kya price kitna hai", _patient(PAKISTAN_NUMBER))
    prompt = _prompt(locale)

    assert "none configured for this market" in prompt
    assert "Do NOT state a figure" in prompt


def test_clarification_prompt_uses_the_one_neutral_question_and_no_currency():
    locale = LocaleService().resolve(_practice(settings={"default_market": "PK"}), "مرحبا، كم سعر العملية؟")
    prompt = _prompt(locale)

    assert "which city are you contacting us from" in prompt
    assert "APPROVED PRICE LIST" not in prompt
    assert "PKR" not in prompt


def test_prompt_without_a_locale_quotes_no_market_at_all():
    prompt = _prompt(None)

    assert "THIS CONVERSATION'S MARKET" not in prompt
    assert "PKR" not in prompt
    assert "GBP" not in prompt
    assert "GUARDRAILS" in prompt


def test_practice_instructions_are_appended_without_weakening_the_guardrails():
    prompt = _prompt(None, custom="We offer free parking and a Ramadan discount.")

    assert "free parking" in prompt
    assert "they never override the guardrails" in prompt
    assert prompt.index("GUARDRAILS") < prompt.index("PRACTICE-SPECIFIC INSTRUCTIONS")
    assert prompt.rstrip().endswith("did I end with a question?")


def test_the_voice_channel_gets_spoken_style_but_the_same_guardrails():
    """s3.3 / s5: one SOP, every channel — the phone line must not be the hole
    where unapproved prices and clinical advice get through."""
    prompt = _prompt(None, channel="voice")

    assert "THIS IS A VOICE CALL" in prompt
    assert "the way a person types on WhatsApp" not in prompt
    assert "GUARDRAILS" in prompt
    assert "may not be licensed" in prompt


def test_quiet_hours_are_stated_in_the_patients_own_time():
    quiet = ConversationLocale(
        market=MARKETS["PK"],
        config=market_config({}, "PK"),
        confidence="high",
        reason="test",
        language_code="roman-ur",
        currency="PKR",
        patient_timezone="Asia/Karachi",
        timezone_estimated=False,
        clinic_timezone="Asia/Karachi",
        needs_clarification=False,
        from_default=False,
        remembered=True,
        local_time_label="Tuesday 03:00 (Asia/Karachi)",
        local_hour=3,
        outside_quiet_hours=True,
        outside_working_week=False,
    )
    prompt = _prompt(quiet)

    assert "outside their 09:00-21:00 window" in prompt
    assert "do not promise a call" in prompt
