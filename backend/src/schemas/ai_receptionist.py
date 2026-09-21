from __future__ import annotations
from pydantic import BaseModel, Field


class HandleCallResponse(BaseModel):
    response: str
    twiml: str


class ChatMessageRequest(BaseModel):
    message: str


class ChatMessageResponse(BaseModel):
    response: str


class TranslateRequest(BaseModel):
    text: str
    target_language: str


class TranslateResponse(BaseModel):
    translated_text: str


class SendReminderResponse(BaseModel):
    appointment_id: str
    message_id: str
    sent: bool
    # Set when the reminder was held back rather than sent: the patient's own
    # 09:00-21:00 window (SOP s11), in their local time. `sent=False` with a
    # reason is a real, honest outcome — not an error.
    held_until: str | None = None
    hold_reason: str | None = None


class ReceptionistPipeline(BaseModel):
    # Real funnel numbers for the monitor page's booking-pipeline widget —
    # computed from Patient lifecycle stages, live Appointment rows, and the
    # AgentLog/Message records of the auto-follow-up agents.
    qualified_leads: int
    appointments_scheduled: int
    auto_followups_sent: int


class ReceptionistChannelStatus(BaseModel):
    # Mirrors the frontend's data/channels.ts ChannelId values.
    channel: str
    connected: bool
    detail: str


class ReceptionistHealth(BaseModel):
    # No infra telemetry (CPU/memory/docs) exists yet — these are the honest
    # numbers a practice can actually measure today: has the AI done anything,
    # and how much in the last 24h.
    status: str
    last_activity_at: str | None
    sessions_24h: int
    interactions_24h: int


class ReceptionistActivityEntry(BaseModel):
    id: str
    label: str
    channel: str | None
    summary: str | None
    created_at: str


class SystemPromptResponse(BaseModel):
    # The effective prompt actually sent to the LLM on each inbound WhatsApp
    # message (base template + this practice's custom instructions).
    system_prompt: str
    custom_instructions: str
    updated_at: str | None
    updated_by: str | None


class UpdateSystemPromptRequest(BaseModel):
    # Practice-authored instructions appended to the base receptionist prompt.
    # Visible to Owner/Doctor/Receptionist, editable by the Owner only. Send
    # an empty string to clear custom instructions and revert to the base.
    custom_instructions: str


class ClinicLocation(BaseModel):
    """One physical clinic location within a market — a practice can run more
    than one branch in the same country (e.g. Lahore and Karachi both routing
    to the PK market), each with its own city and full address so the
    receptionist can actually direct a patient to the right door, not just
    name the country."""
    city: str
    address: str | None = None


class MarketSettings(BaseModel):
    # One market, exactly as the receptionist's prompt block will read it: the
    # registry's facts plus whatever this practice has configured on top.
    code: str
    label: str
    # False means the AI is currently told not to quote a figure for this market.
    configured: bool
    is_home: bool
    currency: str
    # What the market defaults to, so the UI can show "you overrode this".
    default_currency: str
    language_label: str
    timezone: str
    regulator: str
    advertising_note: str
    consult_format: str
    video_first: bool
    clinic_name: str | None = None
    # Legacy single-city field — still populated (from clinics[0].city when
    # clinics is set) for any caller not yet reading `clinics` below.
    clinic_city: str | None = None
    clinics: list[ClinicLocation] = Field(default_factory=list)
    consultation_fee: str | None = None
    payment_methods: str | None = None
    prices: dict[str, str] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)


class MarketSettingsUpdate(BaseModel):
    # Every field optional — a PUT replaces only what it is given, so saving one
    # field never wipes the rest of the market's configuration.
    currency: str | None = None
    clinic_name: str | None = None
    clinic_city: str | None = None
    clinics: list[ClinicLocation] | None = None
    consultation_fee: str | None = None
    payment_methods: str | None = None
    prices: dict[str, str] | None = None
    languages: list[str] | None = None
    # Make this market the practice's home market: where a message with no
    # usable signal routes to (SOP s3.2).
    is_home: bool = False


class MarketsSettingsResponse(BaseModel):
    home_market: str | None
    markets: list[MarketSettings]
    supported_currencies: list[str]
    updated_at: str | None
    updated_by: str | None


class HumanAvailabilityUpdate(BaseModel):
    # Practice-local "HH:MM" — the same clock the front desk itself works to,
    # read against Practice.timezone (not the patient's market — staff work
    # fixed hours regardless of which country a message routed to).
    start: str = "09:00"
    end: str = "18:00"
    # Working weekdays, Monday=0..Sunday=6 — mirrors markets.py's own
    # working_days convention so the two never need translating between.
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class HumanAvailabilityResponse(BaseModel):
    start: str
    end: str
    days: list[int]
    timezone: str
    available_now: bool
    # A ready-to-show sentence — "Available now" / "Back tomorrow at 9:00 AM"
    # — the same wording the AI receptionist's tool result also uses, so the
    # settings page and what the AI actually tells a patient never disagree.
    status_label: str


class AIReceptionistOverviewResponse(BaseModel):
    calls_handled: int
    reminders_sent: int
    translations_done: int
    total_interactions: int
    # Real spend computed from AgentLog counts x AgentCosting's real
    # per-session rates — not a fabricated number. $0 with zero activity is
    # a true value, same reasoning as FinanceOverviewResponse.
    estimated_cost_total: float
    estimated_cost_last_30_days: float
    # Monitor-page widgets, real data — replaces the old mock-only
    # BookingPipelineFunnel / SystemHealthCard / OmnichannelHubCard inputs.
    pipeline: ReceptionistPipeline
    channels: list[ReceptionistChannelStatus]
    health: ReceptionistHealth
    recent_activity: list[ReceptionistActivityEntry]
