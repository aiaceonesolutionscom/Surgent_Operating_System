from __future__ import annotations
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from typing import Optional


class CreateInventoryItemRequest(BaseModel):
    name: str
    sku: str | None = None
    category: str | None = None
    unit: str | None = None
    reorder_threshold: int | None = None
    is_implant: bool = False
    unit_cost: Decimal | None = None


class UpdateInventoryItemRequest(BaseModel):
    name: str | None = None
    sku: str | None = None
    category: str | None = None
    unit: str | None = None
    reorder_threshold: int | None = None
    is_implant: bool | None = None
    is_active: bool | None = None
    unit_cost: Decimal | None = None


class InventoryItemResponse(BaseModel):
    id: UUID
    practice_id: UUID
    name: str
    sku: str | None
    category: str | None
    unit: str | None
    reorder_threshold: int | None
    is_implant: bool = False
    is_active: bool
    unit_cost: Decimal | None = None
    # Computed from the item's batches (see InventoryService), not a stored
    # column — always the current real sum, never stale.
    on_hand_quantity: int = 0
    is_low_stock: bool = False
    # Calculated: on_hand_quantity * unit_cost (null if unit_cost not set)
    total_value: Decimal | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReceiveBatchRequest(BaseModel):
    lot_number: str | None = None
    quantity: int
    expiry_date: date | None = None
    received_at: date | None = None


class ConsumeStockRequest(BaseModel):
    quantity: int


class RecordWastageRequest(BaseModel):
    quantity: int
    reason: str


class InventoryBatchResponse(BaseModel):
    id: UUID
    inventory_item_id: UUID
    lot_number: str | None
    quantity: int
    expiry_date: date | None
    received_at: date
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryAdjustmentResponse(BaseModel):
    id: UUID
    inventory_batch_id: UUID
    adjustment_type: str
    quantity: int
    reason: str | None
    resource_type: str | None
    resource_id: UUID | None
    performed_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
