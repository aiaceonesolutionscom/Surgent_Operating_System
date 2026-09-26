from __future__ import annotations
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import User
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
from src.services.inventory.inventory_services import InventoryService


class InventoryController:
    def __init__(self):
        self.service = InventoryService()

    async def create_item(self, db: AsyncSession, user: User, data: CreateInventoryItemRequest) -> InventoryItemResponse:
        item = await self.service.create_item(db, user.practice_id, data)
        return InventoryItemResponse.model_validate(item)

    async def list_items(self, db: AsyncSession, user: User, include_archived: bool = False) -> list[InventoryItemResponse]:
        items = await self.service.list_items(db, user.practice_id, include_inactive=include_archived)
        return [InventoryItemResponse.model_validate(i) for i in items]

    async def get_item(self, db: AsyncSession, user: User, item_id: UUID) -> InventoryItemResponse:
        item = await self.service.get_item(db, user.practice_id, item_id)
        return InventoryItemResponse.model_validate(item)

    async def update_item(self, db: AsyncSession, user: User, item_id: UUID, data: UpdateInventoryItemRequest) -> InventoryItemResponse:
        item = await self.service.update_item(db, user.practice_id, item_id, data)
        return InventoryItemResponse.model_validate(item)

    async def receive_batch(self, db: AsyncSession, user: User, item_id: UUID, data: ReceiveBatchRequest) -> InventoryBatchResponse:
        batch = await self.service.receive_batch(db, user.practice_id, item_id, data, performed_by=str(user.id))
        return InventoryBatchResponse.model_validate(batch)

    async def list_batches(self, db: AsyncSession, user: User, item_id: UUID) -> list[InventoryBatchResponse]:
        batches = await self.service.list_batches(db, user.practice_id, item_id)
        return [InventoryBatchResponse.model_validate(b) for b in batches]

    async def consume(self, db: AsyncSession, user: User, item_id: UUID, data: ConsumeStockRequest) -> InventoryItemResponse:
        item = await self.service.consume(db, user.practice_id, item_id, data.quantity, performed_by=str(user.id))
        return InventoryItemResponse.model_validate(item)

    async def record_wastage(self, db: AsyncSession, user: User, item_id: UUID, data: RecordWastageRequest) -> InventoryItemResponse:
        item = await self.service.record_wastage(db, user.practice_id, item_id, data.quantity, data.reason, performed_by=str(user.id))
        return InventoryItemResponse.model_validate(item)

    async def list_adjustments(self, db: AsyncSession, user: User, item_id: UUID) -> list[InventoryAdjustmentResponse]:
        adjustments = await self.service.list_adjustments(db, user.practice_id, item_id)
        return [InventoryAdjustmentResponse.model_validate(a) for a in adjustments]
