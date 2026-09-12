// Single shared vocabulary for "which plan" — imported by both the
// marketing site (data/plans.ts) and the dashboard's gating layer
// (app/dashboard/plan/) so the two can never drift on what "practice" means.
export type PlanTier = "solo" | "practice" | "enterprise";

// "solo" is a legacy tier from the old catalog — it no longer exists on the
// backend (solo subscriptions were migrated to practice). It stays in the
// union so stale API responses don't crash the UI; normalizeTier() collapses
// it to practice everywhere.
export const PLAN_ORDER: PlanTier[] = ["practice", "enterprise"];

export function normalizeTier(tier: PlanTier): PlanTier {
  return tier === "solo" ? "practice" : tier;
}

export function tierRank(tier: PlanTier): number {
  return PLAN_ORDER.indexOf(normalizeTier(tier));
}

// True if `tier` is at least as high as `min` (e.g. tierAtLeast("practice", "practice") === true).
export function tierAtLeast(tier: PlanTier, min: PlanTier): boolean {
  return tierRank(tier) >= tierRank(min);
}
