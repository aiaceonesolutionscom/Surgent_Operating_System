from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.practice import Practice
from src.models.user import User, UserRole
from src.schemas.sample_data import SampleDataActionResponse, SampleDataCounts
from src.server.dependencies import require_role
from src.server.exceptions import AppException
from src.services.demo.sample_data_service import SampleDataService

# Owner-only: seeding and clearing demo data is a workspace-level action. A
# doctor or receptionist must not be able to populate or wipe a practice's
# tables — see multiclinic.md §8.
#
# Practice scoping comes from the SESSION, never from a request body or path
# parameter. `require_role` resolves through get_current_practice_user, so
# `user.practice_id` is the only practice these endpoints can ever touch. There
# is no org_id parameter for a caller to get wrong or tamper with — that is
# what makes the clinic-A-can't-touch-clinic-B guarantee structural here rather
# than a rule someone has to remember.
router = APIRouter(prefix="/sample-data", tags=["Sample Data"])
service = SampleDataService()

_ENTITIES = (
    ("patients", "patients"),
    ("appointments", "appointments"),
    ("conversations", "conversations"),
    ("inventory_items", "stock items"),
    ("expenses", "expenses"),
)


def _label(counts: dict[str, int]) -> str:
    return ", ".join(f"{counts.get(key, 0)} {label}" for key, label in _ENTITIES)


@router.get("/counts", response_model=SampleDataCounts)
async def get_sample_data_counts(
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    return SampleDataCounts(**await service.sample_data_counts(db, user.practice_id))


@router.post("/seed", response_model=SampleDataActionResponse)
async def seed_sample_data(
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    # Read the current state BEFORE seeding so the confirmation copy can
    # honestly distinguish "loaded 12 patients" from "you already had them".
    # Asking after the fact would be indistinguishable, because seeding is
    # idempotent by design.
    before = await service.sample_data_counts(db, user.practice_id)

    practice = await db.get(Practice, user.practice_id)
    if practice is None:
        raise AppException("Practice not found.")

    after = await service.seed_sample_data(db, practice)

    if before["total"] > 0:
        message = f"Sample data was already loaded — nothing changed. Currently: {_label(after)}."
    else:
        message = f"Sample data loaded — {_label(after)}."

    return SampleDataActionResponse(
        action="seeded",
        counts=SampleDataCounts(**after),
        message=message,
    )


@router.delete("", response_model=SampleDataActionResponse)
async def clear_sample_data(
    user: User = Depends(require_role(UserRole.OWNER)),
    db: AsyncSession = Depends(get_db),
):
    removed = await service.clear_sample_data(db, user.practice_id)

    if removed["total"] == 0:
        message = "There was no sample data to remove."
    else:
        message = f"Removed {removed['total']} sample rows — {_label(removed)}."

    return SampleDataActionResponse(
        action="cleared",
        counts=SampleDataCounts(
            **{k: v for k, v in removed.items() if k in SampleDataCounts.model_fields}
        ),
        message=message,
    )