from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class FinanceAgentDoctorEarning(BaseModel):
    doctor_name: str
    total_earned: float
    invoices_paid: int


class FinanceAgentAgentCost(BaseModel):
    agent_slug: str
    sessions: int
    estimated_cost: float


class FinanceAgentRecentInvoice(BaseModel):
    patient_name: str
    status: str
    amount: float


class FinanceAgentReport(BaseModel):
    total_revenue: float
    total_expenses: float
    net: float
    outstanding: float
    invoice_count: int
    expense_count: int
    month_label: str = ""
    per_doctor: list[FinanceAgentDoctorEarning] = []
    per_agent_cost: list[FinanceAgentAgentCost] = []
    recent_invoices: list[FinanceAgentRecentInvoice] = []


class AskFinanceAgentRequest(BaseModel):
    question: str
    session_id: UUID | None = None


class FinanceAgentStep(BaseModel):
    # Mirrors CommandCenterStep's shape (schemas/command_center.py) — same
    # "which sub-tool got consulted" reveal, now real instead of a fake
    # setTimeout animation, and now something Finance Agent has too instead
    # of always dumping one giant snapshot regardless of the question.
    tool_label: str
    summary: str


class AskFinanceAgentResponse(BaseModel):
    session_id: UUID
    answer: str
    steps: list[FinanceAgentStep] = []


class FinanceAgentMessage(BaseModel):
    role: Literal["staff", "agent"]
    content: str
    steps: list[FinanceAgentStep] = []
    created_at: datetime


class FinanceAgentSessionSummary(BaseModel):
    id: UUID
    title: str
    updated_at: datetime


class FinanceAgentSessionDetail(BaseModel):
    id: UUID
    title: str
    messages: list[FinanceAgentMessage]