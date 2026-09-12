from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class WalletBalanceResponse(BaseModel):
    balance: float
    currency: str


class WalletTransactionResponse(BaseModel):
    id: UUID
    amount: float
    currency: str
    status: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTopupRequest(BaseModel):
    amount: float
