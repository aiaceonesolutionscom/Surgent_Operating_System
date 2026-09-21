"""The outbound quiet-hours rule (SOP s11) and patient-local time rendering.

Pure logic — no database, no network. The database-backed half
(`resolve_patient_timing_context`) only decides *which zone* the rules below run
against; the rules themselves are what these tests pin down.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.services.ai_receptionist.markets import MARKETS
from src.services.messaging.quiet_hours import (
    MessageTiming,
    PatientTimingContext,
    evaluate_timing,
    format_for_patient,
)

PAKISTAN = PatientTimingContext(timezone="Asia/Karachi", market=MARKETS["PK"], source="patient_stated")
SAUDI = PatientTimingContext(timezone="Asia/Riyadh", market=MARKETS["SA"], source="market:SA")
UNKNOWN_MARKET = PatientTimingContext(timezone="Asia/Dubai", market=None, source="clinic")


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# 2026-09-19 is a Saturday; 2026-09-21 is a Monday.

def test_an_automated_reminder_is_held_when_it_is_3am_for_the_patient():
    """The bug this exists for: a UTC-server practice messaging Pakistan at 3am."""
    decision = evaluate_timing(PAKISTAN, MessageTiming.REMINDER, now=_utc(2026, 9, 21, 22, 0))

    assert decision.allowed is False
    assert "03:00" in decision.local_time_label
    assert decision.next_allowed_label is not None and "09:00" in decision.next_allowed_label
    assert "Asia/Karachi" in decision.next_allowed_label


def test_a_reminder_inside_the_patients_own_day_goes_out():
    # 06:00 UTC = 11:00 in Karachi.
    decision = evaluate_timing(PAKISTAN, MessageTiming.REMINDER, now=_utc(2026, 9, 21, 6, 0))

    assert decision.allowed is True


def test_proactive_messages_also_respect_the_gulf_working_week():
    """Friday is a weekend in Saudi Arabia even though it is a working day in London."""
    friday = evaluate_timing(SAUDI, MessageTiming.PROACTIVE, now=_utc(2026, 9, 18, 8, 0))
    monday = evaluate_timing(SAUDI, MessageTiming.PROACTIVE, now=_utc(2026, 9, 21, 8, 0))

    assert friday.allowed is False
    assert "working week" in friday.reason
    assert monday.allowed is True


def test_a_reminder_for_a_sunday_appointment_is_still_sent_on_the_saudi_weekend():
    """A booked appointment is not marketing — the waking-hours window is the
    only gate that applies to it."""
    decision = evaluate_timing(SAUDI, MessageTiming.REMINDER, now=_utc(2026, 9, 18, 8, 0))

    assert decision.allowed is True


def test_a_payment_receipt_is_never_held():
    decision = evaluate_timing(PAKISTAN, MessageTiming.ON_DEMAND, now=_utc(2026, 9, 21, 23, 30))

    assert decision.allowed is True


def test_a_market_less_context_still_applies_the_default_window():
    decision = evaluate_timing(UNKNOWN_MARKET, MessageTiming.REMINDER, now=_utc(2026, 9, 21, 23, 0))

    assert decision.allowed is False  # 03:00 in Dubai the next morning


def test_the_decision_log_details_are_complete_enough_to_answer_why():
    details = evaluate_timing(PAKISTAN, MessageTiming.PROACTIVE, now=_utc(2026, 9, 21, 23, 0)).as_log_details()

    assert details["timing"] == "proactive"
    assert details["patient_timezone"] == "Asia/Karachi"
    assert details["next_allowed"]
    assert details["timezone_source"] == "patient_stated"


def test_appointment_times_are_stated_in_the_patients_zone_first():
    when = format_for_patient(_utc(2026, 9, 22, 11, 30), "Asia/Dubai", "Asia/Karachi")

    # 11:30 UTC is 3:30pm in Dubai and 4:30pm at the Karachi clinic.
    assert "3:30 PM" in when
    assert "your time" in when
    assert "4:30 PM at the clinic" in when


def test_a_same_zone_appointment_does_not_repeat_itself():
    when = format_for_patient(_utc(2026, 9, 22, 11, 30), "Asia/Karachi", "Asia/Karachi")

    assert "your time" not in when
    assert "11:30 AM" not in when  # 11:30 UTC is 4:30pm in Karachi
    assert "4:30 PM" in when


def test_naive_appointment_times_are_read_as_utc():
    when = format_for_patient(datetime(2026, 9, 22, 11, 30), "Asia/Karachi", None)

    assert "4:30 PM" in when
