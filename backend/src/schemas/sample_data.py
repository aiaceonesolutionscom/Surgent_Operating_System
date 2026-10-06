from __future__ import annotations

from pydantic import BaseModel, Field


class SampleDataCounts(BaseModel):
    """Per-entity counts of `is_sample=True` rows for one practice.

    `total` deliberately excludes `messages`: messages are not flagged and are
    removed by cascade from their Conversation, so they are reported
    informationally but aren't a separately-deletable bucket.
    """

    patients: int = 0
    appointments: int = 0
    conversations: int = 0
    messages: int = 0
    inventory_items: int = 0
    expenses: int = 0
    total: int = 0

    model_config = {"from_attributes": True}


class SampleDataActionResponse(BaseModel):
    """Returned by both seed and clear. `action` tells the UI which verb to use
    in its confirmation text so the client never has to guess whether the
    numbers it just received are additions or deletions."""

    action: str = Field(description="'seeded' or 'cleared'")
    counts: SampleDataCounts
    message: str