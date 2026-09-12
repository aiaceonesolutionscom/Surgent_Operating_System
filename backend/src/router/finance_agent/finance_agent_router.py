from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import get_current_practice_context, require_agent, PracticeContext
from src.schemas.finance_agent import (
    AskFinanceAgentRequest,
    AskFinanceAgentResponse,
    FinanceAgentReport,
    FinanceAgentSessionSummary,
    FinanceAgentSessionDetail,
)
from src.controller.finance_agent.finance_agent_controllers import FinanceAgentController

router = APIRouter(prefix="/finance-agent", tags=["Finance Agent"])
controller = FinanceAgentController()
FINANCE_AGENT_SLUG = "finance_agent"


@router.get("/report", response_model=FinanceAgentReport)
async def get_finance_agent_report(
    ctx: PracticeContext = Depends(require_agent(FINANCE_AGENT_SLUG)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.report(db, ctx)


@router.post("/ask", response_model=AskFinanceAgentResponse)
async def ask_finance_agent(
    data: AskFinanceAgentRequest,
    ctx: PracticeContext = Depends(require_agent(FINANCE_AGENT_SLUG)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.ask(db, ctx, data)


@router.get("/sessions", response_model=list[FinanceAgentSessionSummary])
async def list_finance_agent_sessions(
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_sessions(db, ctx)


@router.get("/sessions/{session_id}", response_model=FinanceAgentSessionDetail)
async def get_finance_agent_session(
    session_id: UUID,
    ctx: PracticeContext = Depends(get_current_practice_context),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_session(db, ctx, session_id)