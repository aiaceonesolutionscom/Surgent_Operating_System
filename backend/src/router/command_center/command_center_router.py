from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_agent, PracticeContext
from src.schemas.command_center import (
    AskCommandCenterRequest,
    AskCommandCenterResponse,
    CommandCenterSessionSummary,
    CommandCenterSessionDetail,
)
from src.controller.command_center.command_center_controllers import CommandCenterController

router = APIRouter(prefix="/command-center", tags=["Command Center"])
controller = CommandCenterController()


@router.post("/ask", response_model=AskCommandCenterResponse)
async def ask_command_center(
    data: AskCommandCenterRequest,
    ctx: PracticeContext = Depends(require_agent("main_agent")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.ask(db, ctx, data)


@router.get("/sessions", response_model=list[CommandCenterSessionSummary])
async def list_command_center_sessions(
    ctx: PracticeContext = Depends(require_agent("main_agent")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_sessions(db, ctx)


@router.get("/sessions/{session_id}", response_model=CommandCenterSessionDetail)
async def get_command_center_session(
    session_id: UUID,
    ctx: PracticeContext = Depends(require_agent("main_agent")),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_session(db, ctx, session_id)