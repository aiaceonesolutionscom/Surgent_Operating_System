from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.server.dependencies import require_role
from src.models.user import User, UserRole
from src.schemas.inventory import (
    CreateInventoryItemRequest,
    UpdateInventoryItemRequest,
    ReceiveBatchRequest,
    ConsumeStockRequest,
    RecordWastageRequest,
    InventoryItemResponse,
    InventoryBatchResponse,
    InventoryAdjustmentResponse,
)
from src.controller.inventory.inventory_controllers import InventoryController

router = APIRouter(prefix="/inventory", tags=["Inventory"])
controller = InventoryController()

# Same split as Expenses (Phase 7) — Owner+Receptionist manage stock,
# Doctor has no stated need for it.
_ROLES = (UserRole.OWNER, UserRole.RECEPTIONIST)


@router.post("/items", response_model=InventoryItemResponse)
async def create_item(
    data: CreateInventoryItemRequest,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.create_item(db, user, data)


@router.get("/items", response_model=list[InventoryItemResponse])
async def list_items(
    include_archived: bool = False,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_items(db, user, include_archived=include_archived)


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_item(
    item_id: UUID,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.get_item(db, user, item_id)


@router.patch("/items/{item_id}", response_model=InventoryItemResponse)
async def update_item(
    item_id: UUID,
    data: UpdateInventoryItemRequest,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.update_item(db, user, item_id, data)


@router.post("/items/{item_id}/batches", response_model=InventoryBatchResponse)
async def receive_batch(
    item_id: UUID,
    data: ReceiveBatchRequest,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.receive_batch(db, user, item_id, data)


@router.get("/items/{item_id}/batches", response_model=list[InventoryBatchResponse])
async def list_batches(
    item_id: UUID,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_batches(db, user, item_id)


@router.post("/items/{item_id}/consume", response_model=InventoryItemResponse)
async def consume(
    item_id: UUID,
    data: ConsumeStockRequest,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.consume(db, user, item_id, data)


@router.post("/items/{item_id}/wastage", response_model=InventoryItemResponse)
async def record_wastage(
    item_id: UUID,
    data: RecordWastageRequest,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.record_wastage(db, user, item_id, data)


@router.get("/items/{item_id}/adjustments", response_model=list[InventoryAdjustmentResponse])
async def list_adjustments(
    item_id: UUID,
    user: User = Depends(require_role(*_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    return await controller.list_adjustments(db, user, item_id)
