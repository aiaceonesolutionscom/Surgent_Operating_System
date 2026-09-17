from __future__ import annotations


def normalize_phone(phone: str) -> str:
    """Digits only — no +, spaces, dashes, or parens. Shared canonical form
    so a phone number entered by staff (any punctuation) and one reported by
    Green API (already digits-only, e.g. from a WhatsApp chat id like
    "923468063112@c.us") land on the exact same string for matching.

    Was previously duplicated as a private helper scoped to patient portal
    OTP lookups only (patient_otp_store.py) — every other phone-comparison
    site (inbound WhatsApp patient matching, manual patient
    create/update) stored/compared whatever raw string it was given, so a
    patient entered as "+92 346 8063112" would never match Green API's
    "923468063112" and would silently spawn a second Patient row (and, from
    there, a second Conversation) for the same real person on their next
    WhatsApp message."""
    return "".join(ch for ch in phone if ch.isdigit())
