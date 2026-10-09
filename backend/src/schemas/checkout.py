from __future__ import annotations
from pydantic import BaseModel, EmailStr


class CheckoutSessionRequest(BaseModel):
    email: EmailStr
    plan_tier: str  # "solo" | "practice" — Enterprise never reaches this endpoint, see Pricing.tsx


class CheckoutSessionResponse(BaseModel):
    # Mounts Stripe's embedded payment form in the browser (there is no hosted
    # checkout URL to redirect to).
    client_secret: str
    session_id: str


class CheckoutSessionStatusResponse(BaseModel):
    paid: bool
    plan_tier: str
    email: str
    claimed: bool
