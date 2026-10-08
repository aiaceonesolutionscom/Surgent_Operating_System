from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.subscription import Subscription, SubscriptionStatus
from src.models.plan import Plan
from src.models.subscription import SubscriptionTier
from src.services.payment.payment_service import PaymentService
from src.server.dependencies import get_current_practice_context, get_owner_practice_context

router = APIRouter(prefix="/billing", tags=["Billing"])
payment = PaymentService()


@router.post("/cancel")
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    ctx=Depends(get_owner_practice_context),
):
    """Cancel subscription at period end (standard SaaS behavior)."""
    practice_id = ctx.practice.id
    result = await db.execute(
        select(Subscription).where(
            Subscription.practice_id == practice_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalars().first()
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    if not payment.is_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        res = await payment.cancel_subscription(sub.stripe_subscription_id)
        return {"success": True, "status": res["status"], "current_period_end": res["current_period_end"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resume")
async def resume_subscription(
    db: AsyncSession = Depends(get_db),
    ctx=Depends(get_owner_practice_context),
):
    """Resume a subscription that was set to cancel at period end."""
    practice_id = ctx.practice.id
    result = await db.execute(
        select(Subscription).where(
            Subscription.practice_id == practice_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL, SubscriptionStatus.PAST_DUE]),
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalars().first()
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No subscription found to resume")

    if not payment.is_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        res = await payment.resume_subscription(sub.stripe_subscription_id)
        return {"success": True, "status": res["status"], "current_period_end": res["current_period_end"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/change-plan")
async def change_plan(
    new_plan_tier: str,
    db: AsyncSession = Depends(get_db),
    ctx=Depends(get_owner_practice_context),
):
    """Upgrade/downgrade to a different plan tier."""
    practice_id = ctx.practice.id
    try:
        new_tier = SubscriptionTier(new_plan_tier)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan tier")

    # Get the new plan's stripe_price_id
    plan_result = await db.execute(select(Plan).where(Plan.tier == new_tier, Plan.is_active.is_(True)))
    new_plan = plan_result.scalar_one_or_none()
    if not new_plan or not new_plan.stripe_price_id:
        raise HTTPException(status_code=400, detail="Plan not available or not configured")

    result = await db.execute(
        select(Subscription).where(
            Subscription.practice_id == practice_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL]),
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalars().first()
    if not sub or not sub.stripe_subscription_id:
        raise HTTPException(status_code=404, detail="No active subscription found")

    if not payment.is_configured():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    try:
        res = await payment.change_subscription_plan(sub.stripe_subscription_id, new_plan.stripe_price_id)
        return {"success": True, "status": res["status"], "new_plan_tier": new_tier.value}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription")
async def get_subscription_status(
    db: AsyncSession = Depends(get_db),
    ctx=Depends(get_current_practice_context),
):
    """Get current subscription status for the practice."""
    practice_id = ctx.practice.id
    result = await db.execute(
        select(Subscription).where(
            Subscription.practice_id == practice_id,
        ).order_by(Subscription.created_at.desc())
    )
    sub = result.scalars().first()
    if not sub:
        return {"has_subscription": False}

    return {
        "has_subscription": True,
        "tier": sub.tier.value,
        "status": sub.status.value,
        "start_date": sub.start_date.isoformat() if sub.start_date else None,
        "end_date": sub.end_date.isoformat() if sub.end_date else None,
        "price": sub.price,
        "stripe_subscription_id": sub.stripe_subscription_id,
        "auto_renew": sub.auto_renew,
    }