from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import date, datetime


class TimeSlot(BaseModel):
    """One bookable window for a doctor. `available` is False when the slot
    falls inside an already-booked appointment (or, in the future, an
    Owner-set constraint) — the frontend greys it out but still shows it so
    the patient understands the shape of the day."""

    start_time: datetime
    end_time: datetime
    available: bool


class DoctorSlotsResponse(BaseModel):
    """Per-day slots for one doctor. `date` is the practice-local calendar
    day the slots belong to; slot timestamps are timezone-aware."""

    doctor_id: UUID
    date: date
    slots: list[TimeSlot]