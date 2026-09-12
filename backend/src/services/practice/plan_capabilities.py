"""The backend enforcement mirror of
frontend/src/app/dashboard/plan/planCapabilities.ts — same mapping, same
derivation from data/plans.ts's marketing copy, kept as a SEPARATE file on
purpose (not shared code — frontend/backend are different languages/deploys)
so a change to what a plan includes means updating both files deliberately,
not a silent one-sided drift. If you change one, change the other.

The frontend file is presentation only (gates what's shown/clickable) and is
trivially bypassed via devtools. THIS file is what actually matters for
security — every endpoint that scopes access by plan tier must go through
require_plan_feature()/require_agent_category() in server/dependencies.py,
which read from here.
"""
from __future__ import annotations

from src.models.subscription import SubscriptionTier

# Mirrors frontend/src/data/agents/index.ts's AGENT_CATEGORIES groupings —
# the backend has no separate "category" model, so this is the one place
# that encodes which of the 9 clinic agent slugs belong to which category.
# The product was consolidated from 31 scratch agents to 9 real ones:
#   front-desk      — receptionist, appointment_reminder
#   consultation    — lead_qualification, patient_intake, consultation_assistant
#   post-care       — post_op_recovery, marketing_retention
#   business        — finance_agent, main_agent
# The old fold-ins (booking, surgery logistics, cost estimation, etc.) were
# absorbed into these 9 or dropped; legacy slugs like "command_center" only
# survive in existing Conversation rows, not in the catalog.
AGENT_CATEGORIES: dict[str, list[str]] = {
    "front-desk": [
        "receptionist",
        "appointment_reminder",
    ],
    "consultation": [
        "lead_qualification",
        "patient_intake",
        "consultation_assistant",
    ],
    "post-care": [
        "post_op_recovery",
        "marketing_retention",
    ],
    "business": [
        "finance_agent",
        "main_agent",
    ],
}

# Category ids unlocked per tier — same derivation as the frontend's
# planCapabilities.ts. Every clinic plan (Practice & up) includes the full
# 9-agent suite; the tiers differentiate on location count, support level and
# enterprise extras (EHR/custom integrations/BAA), not on agent access.
TIER_CATEGORIES: dict[SubscriptionTier, list[str]] = {
    SubscriptionTier.PRACTICE: ["front-desk", "consultation", "post-care", "business"],
    SubscriptionTier.ENTERPRISE: ["front-desk", "consultation", "post-care", "business"],
    SubscriptionTier.CUSTOM: ["front-desk", "consultation", "post-care", "business"],
}

TIER_LIMITS: dict[SubscriptionTier, dict[str, float]] = {
    SubscriptionTier.PRACTICE: {"max_doctors": float("inf"), "max_social_channels": float("inf"), "max_locations": 1},
    SubscriptionTier.ENTERPRISE: {"max_doctors": float("inf"), "max_social_channels": float("inf"), "max_locations": float("inf")},
    SubscriptionTier.CUSTOM: {"max_doctors": float("inf"), "max_social_channels": float("inf"), "max_locations": float("inf")},
}


def allowed_categories(tier: SubscriptionTier) -> list[str]:
    # Legacy SOLO rows (pre-consolidation) map to the full Practice catalog —
    # they were never sold multi-location, so the tier's only real limiter
    # (max_locations=1) still binds them.
    return TIER_CATEGORIES.get(tier, TIER_CATEGORIES[SubscriptionTier.PRACTICE])


def allowed_agent_slugs(tier: SubscriptionTier) -> set[str]:
    categories = allowed_categories(tier)
    return {slug for cat in categories for slug in AGENT_CATEGORIES.get(cat, [])}


def category_for_agent(agent_slug: str) -> str | None:
    for cat, slugs in AGENT_CATEGORIES.items():
        if agent_slug in slugs:
            return cat
    return None


def allows_category(tier: SubscriptionTier, category_id: str) -> bool:
    return category_id in allowed_categories(tier)


def allows_agent(tier: SubscriptionTier, agent_slug: str) -> bool:
    return agent_slug in allowed_agent_slugs(tier)


def has_analytics(tier: SubscriptionTier) -> bool:
    return tier in (SubscriptionTier.PRACTICE, SubscriptionTier.ENTERPRISE, SubscriptionTier.CUSTOM)


def limits_for(tier: SubscriptionTier) -> dict[str, float]:
    # Legacy SOLO rows resolve to the Practice limits (as with allowed_categories).
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.PRACTICE])
