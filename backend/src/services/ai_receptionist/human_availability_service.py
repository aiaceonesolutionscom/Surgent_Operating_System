"""Whether a real human (front desk / receptionist) is actually reachable
right now — the thing the AI receptionist needs to know before it decides
whether "connecting you with our team now" is an honest holding line or a
promise it can't keep.

Storage is `Practice.settings["human_support_hours"]`, the same JSONB blob
markets and Green API credentials already live in:

    "human_support_hours": {"start": "09:00", "end": "18:00", "days": [0,1,2,3,4]}

Unlike a market's quiet hours (s11 — computed against the *patient's* local
time, so a proactive message never lands at 3am wherever they are), this is
computed against the *practice's own* time zone: front desk works fixed
hours regardless of which country a given conversation routed to.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.schemas.ai_receptionist import HumanAvailabilityResponse, HumanAvailabilityUpdate
from src.server.exceptions import AppException, NotFoundException

SETTINGS_KEY = "human_support_hours"
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_START = "09:00"
DEFAULT_END = "18:00"
DEFAULT_DAYS: tuple[int, ...] = (0, 1, 2, 3, 4)


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def compute_status(
    practice_timezone: str | None, start: str, end: str, days: list[int], now: datetime | None = None
) -> tuple[bool, str]:
    """Pure function (no DB) so both the settings endpoint and the AI's own
    tool handler always agree — see inbound_service.py's escalation tools."""
    try:
        tz = ZoneInfo(practice_timezone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now_local = (now or datetime.now(dt_timezone.utc)).astimezone(tz)

    try:
        start_h, start_m = _parse_hhmm(start)
        end_h, end_m = _parse_hhmm(end)
    except (ValueError, AttributeError):
        start_h, start_m = _parse_hhmm(DEFAULT_START)
        end_h, end_m = _parse_hhmm(DEFAULT_END)

    days = days or list(DEFAULT_DAYS)

    today_start = now_local.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    today_end = now_local.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    if now_local.weekday() in days and today_start <= now_local <= today_end:
        return True, f"Available now, until {today_end.strftime('%I:%M %p').lstrip('0')}"

    # Find the next opening — today (later), or the next matching weekday.
    for offset in range(0, 8):
        candidate = now_local + timedelta(days=offset)
        if candidate.weekday() not in days:
            continue
        candidate_start = candidate.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        if offset == 0 and candidate_start <= now_local:
            continue
        time_label = candidate_start.strftime("%I:%M %p").lstrip("0")
        if offset == 0:
            return False, f"Back later today at {time_label}"
        if offset == 1:
            return False, f"Back tomorrow at {time_label}"
        return False, f"Back {_WEEKDAY_NAMES[candidate_start.weekday()]} at {time_label}"

    return False, "Team hours not configured"


class HumanAvailabilityService:
    """Read/write a practice's front-desk support-hours window."""

    async def _load(self, db: AsyncSession, practice_id: UUID) -> Practice:
        practice = await db.get(Practice, practice_id)
        if practice is None:
            raise NotFoundException("Practice not found")
        return practice

    def _read_block(self, practice: Practice) -> dict:
        block = (practice.settings or {}).get(SETTINGS_KEY)
        if not isinstance(block, dict):
            block = {}
        return {
            "start": str(block.get("start") or DEFAULT_START),
            "end": str(block.get("end") or DEFAULT_END),
            "days": [int(d) for d in (block.get("days") or list(DEFAULT_DAYS)) if isinstance(d, (int, float, str)) and str(d).lstrip("-").isdigit()],
        }

    async def get_settings(self, db: AsyncSession, practice_id: UUID) -> HumanAvailabilityResponse:
        practice = await self._load(db, practice_id)
        return self._to_response(practice)

    async def save_settings(
        self, db: AsyncSession, practice_id: UUID, payload: HumanAvailabilityUpdate
    ) -> HumanAvailabilityResponse:
        practice = await self._load(db, practice_id)
        self._validate_hhmm(payload.start)
        self._validate_hhmm(payload.end)
        days = sorted({d for d in payload.days if 0 <= d <= 6})
        if not days:
            raise AppException("Pick at least one working day.")

        settings = dict(practice.settings or {})
        settings[SETTINGS_KEY] = {"start": payload.start, "end": payload.end, "days": days}
        practice.settings = settings
        await db.commit()
        await db.refresh(practice)
        return self._to_response(practice)

    @staticmethod
    def _validate_hhmm(value: str) -> None:
        try:
            hour, minute = _parse_hhmm(value)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except (ValueError, AttributeError):
            raise AppException(f"'{value}' isn't a valid time — use 24-hour HH:MM, e.g. 09:00.")

    def _to_response(self, practice: Practice) -> HumanAvailabilityResponse:
        block = self._read_block(practice)
        available_now, status_label = compute_status(practice.timezone, block["start"], block["end"], block["days"])
        return HumanAvailabilityResponse(
            start=block["start"],
            end=block["end"],
            days=block["days"],
            timezone=practice.timezone or "UTC",
            available_now=available_now,
            status_label=status_label,
        )

    async def status_for_practice(self, db: AsyncSession, practice_id: UUID) -> tuple[bool, str]:
        """Used by the AI receptionist's own escalation tools — a thin
        wrapper so inbound_service.py doesn't need to know the storage shape."""
        practice = await self._load(db, practice_id)
        block = self._read_block(practice)
        return compute_status(practice.timezone, block["start"], block["end"], block["days"])
