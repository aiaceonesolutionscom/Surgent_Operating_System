import { useCallback, useEffect, useState } from "react";
import type { PlanTier } from "../../../data/planTiers";
import { tierAtLeast, PLAN_ORDER, normalizeTier } from "../../../data/planTiers";
import type { Role } from "../../../data/roles";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import type { AgentCategory } from "../../../data/agents";
import { PLANS } from "../../../data/plans";
import { getMyPractice } from "../../../api/practice";
import { RECOMMENDED_DOCTOR_PERMISSIONS } from "../../../data/doctorPermissions";
import { RECOMMENDED_RECEPTIONIST_PERMISSIONS } from "../../../data/receptionistPermissions";

// ============================================================================
// Types
// ============================================================================

export type SupportLevel = "email" | "priority" | "dedicated";

// A page/surface that isn't an agent category — checked with hasFeature().
export type FeatureKey = "analytics" | "billingAgents" | "ehrIntegration" | "customIntegrations" | "baa";

export interface PlanLimits {
  maxDoctors: number; // Infinity = unlimited
  maxSocialChannels: number;
  maxLocations: number;
}

export interface PlanCapabilities {
  tier: PlanTier;
  // Which of the 4 AGENT_CATEGORIES ids (front-desk/consultation/post-care/business) this tier unlocks.
  agentCategoryIds: AgentCategory["id"][];
  features: Partial<Record<FeatureKey, boolean>>;
  limits: PlanLimits;
  supportLevel: SupportLevel;
}

export type PlanSource = "api" | "local" | "default";

// ============================================================================
// Local overrides (storage) — mirrors profile/usePracticeProfile.ts's
// localStorage pattern. Fallbacks a real onboarding claim step or
// billing/PlanComparisonTable.tsx's dev "Switch to this plan" buttons write,
// read as source #2 in usePlanTier()'s chain (behind a real /practice/me).
// ============================================================================

const STORAGE_KEY = "aesthetixai_dashboard_plan_tier";
const ROLE_STORAGE_KEY = "aesthetixai_dashboard_role_preview";

export function readPlanOverride(): PlanTier | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === "solo" || raw === "practice" || raw === "enterprise" ? raw : null;
  } catch {
    return null;
  }
}

export function writePlanOverride(tier: PlanTier) {
  try {
    localStorage.setItem(STORAGE_KEY, tier);
  } catch {
    // private browsing / storage disabled — the tier just won't persist across reloads
  }
}

// Dev-only "preview as" role switch — same shape as the plan-tier override
// above, so local QA can see the Doctor dashboard without a real Clerk
// invite+sign-up round trip. Only ever a fallback when the real API hasn't
// resolved a role (see usePlanTier) — a real signed-in session always wins.
export function readRoleOverride(): Role | null {
  try {
    const raw = localStorage.getItem(ROLE_STORAGE_KEY);
    return raw === "owner" || raw === "doctor" || raw === "receptionist" || raw === "staff" ? raw : null;
  } catch {
    return null;
  }
}

export function writeRoleOverride(role: Role) {
  try {
    localStorage.setItem(ROLE_STORAGE_KEY, role);
  } catch {
    // private browsing / storage disabled — the role just won't persist across reloads
  }
}

// Clears the dev "preview as" role override (and the Portal switcher's demo
// override) so a real signed-in session's role takes over again.
export function clearRoleOverride() {
  try {
    localStorage.removeItem(ROLE_STORAGE_KEY);
  } catch {
    // ignore storage failures
  }
}

// ============================================================================
// Capabilities — the single source of truth for what each plan unlocks in the
// DASHBOARD, derived line-by-line from data/plans.ts's marketing copy (see the
// comment on each entry). This is presentation-layer only (trivially bypassed
// via devtools) — safe exclusively because every gated surface currently reads
// mock data. A future backend/src/services/practice/plan_capabilities.py is
// meant to mirror this exactly for real enforcement; if you change a value
// here, change it there too once that file exists.
// ============================================================================

export const PLAN_CAPABILITIES: Record<PlanTier, PlanCapabilities> = {
  // Legacy "solo" — same caps as practice (the Solo plan was removed; all solo
  // subscriptions migrated to practice). Kept only so a stale solo tier in an
  // API response resolves to the same gating as practice.
  solo: {
    tier: "solo",
    agentCategoryIds: ["front-desk", "consultation", "post-care", "business"],
    features: {
      analytics: true
    },
    limits: {
      maxDoctors: Infinity,
      maxSocialChannels: Infinity,
      maxLocations: 1
    },
    supportLevel: "priority"
  },
  practice: {
    tier: "practice",
    // All 4 catalog categories — this plan ships every one of the 9 agents.
    agentCategoryIds: ["front-desk", "consultation", "post-care", "business"],
    features: {
      analytics: true
    },
    limits: {
      maxDoctors: Infinity,
      maxSocialChannels: Infinity,
      maxLocations: 1
    },
    supportLevel: "priority"
  },
  enterprise: {
    tier: "enterprise",
    agentCategoryIds: ["front-desk", "consultation", "post-care", "business"],
    features: {
      analytics: true,
      billingAgents: true,
      ehrIntegration: true,
      customIntegrations: true,
      baa: true
    },
    limits: {
      maxDoctors: Infinity,
      maxSocialChannels: Infinity,
      maxLocations: Infinity
    },
    supportLevel: "dedicated"
  }
};

export function capabilitiesFor(tier: PlanTier): PlanCapabilities {
  return PLAN_CAPABILITIES[normalizeTier(tier)];
}

export function hasFeature(tier: PlanTier, feature: FeatureKey): boolean {
  return Boolean(PLAN_CAPABILITIES[normalizeTier(tier)].features[feature]);
}

export function allowsCategory(tier: PlanTier, categoryId: string): boolean {
  return PLAN_CAPABILITIES[normalizeTier(tier)].agentCategoryIds.includes(categoryId);
}

export function allowsAgent(tier: PlanTier, agentSlug: string): boolean {
  const agent = AGENTS_BY_SLUG[agentSlug];
  if (!agent) return false;
  return allowsCategory(tier, agent.categoryId);
}

// Lowest tier that unlocks a category — drives "Included in Practice — $999/mo" copy.
export function minTierForCategory(categoryId: string): PlanTier | null {
  for (const tier of PLAN_ORDER) {
    if (allowsCategory(tier, categoryId)) return tier;
  }
  return null;
}

export function minTierForFeature(feature: FeatureKey): PlanTier | null {
  for (const tier of PLAN_ORDER) {
    if (hasFeature(tier, feature)) return tier;
  }
  return null;
}

// The marketing Plan record (name/price) for a tier — so upgrade copy never
// hardcodes a price that could drift from the Pricing section.
export function planFor(tier: PlanTier) {
  return PLANS.find((p) => p.id === normalizeTier(tier))!;
}

// ============================================================================
// usePlanTier hook — ordered source chain: real API -> local override
// (onboarding claim / the Plan & Billing page's dev switch buttons) -> "practice"
// default. Every dashboard component reads `tier`/`source` from this without
// knowing which source answered. `role` follows the same chain — a real
// signed-in session (API) always wins; the local role-preview override only
// ever applies when the API hasn't resolved one.
//
// Source #1 — GET /api/v1/practice/me. Only reachable when Clerk is enabled
// and signed in (authedFetch is null otherwise — see PlanContext.tsx's
// Clerk-gated split, same pattern as profile/ProfilePage.tsx's
// AccountCard/AccountCardWithUser). A 404/401 (not claimed yet, or claim
// hasn't run) falls through to the local override instead of erroring.
// ============================================================================

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

async function fetchFromApi(authedFetch: AuthedFetch): Promise<{ tier: PlanTier; role: Role; permissions: string[] } | null> {
  if (!authedFetch) return null;
  try {
    const practice = await getMyPractice(authedFetch);
    return { tier: practice.plan_tier, role: practice.role, permissions: practice.permissions || [] };
  } catch {
    return null;
  }
}

export function usePlanTier(authedFetch: AuthedFetch = null) {
  const [tier, setTier] = useState<PlanTier>(() => readPlanOverride() || "practice");
  const [role, setRole] = useState<Role>(() => readRoleOverride() || "owner");
  // Only meaningful for role === "doctor" (see backend/src/data/doctor_permissions.py)
  // — the granted permission keys an Owner assigned at application-approval
  // time. No local override exists for this (unlike role/tier's dev
  // switchers) since it's meaningless without a real approved Doctor record.
  const [permissions, setPermissions] = useState<string[]>([]);
  const [source, setSource] = useState<PlanSource>(() => (readPlanOverride() ? "local" : "default"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchFromApi(authedFetch);
      if (cancelled) return;
      if (result) {
        // A REAL practice membership resolved from the backend — this is the
        // source of truth and it ALWAYS wins. The dev "preview as" override
        // deliberately does NOT apply here: it was the root of the role
        // mixing seen live (an Owner "previewing as Doctor" while the backend
        // session stayed Owner → doctor URLs 403'd or bounced to the Owner
        // dashboard, and vice versa). To demo a Doctor or Receptionist
        // dashboard you sign in with a real account of that role.
        setTier(result.tier);
        setRole(result.role);
        setPermissions(result.permissions);
        setSource("api");
      } else if (!authedFetch) {
        // No real auth session at all (Clerk disabled) — safe to use the
        // local dev overrides (Plan & Billing's "preview as" switcher).
        const local = readPlanOverride();
        setTier(local || "practice");
        setRole(readRoleOverride() || "owner");
        setPermissions([]);
        setSource(local ? "local" : "default");
      } else {
        // A real Clerk session exists but the backend has no active
        // practice/user for it yet (pending doctor/staff approval, unclaimed
        // signup, or a Portal demo with no local User). The demo override is
        // allowed ONLY here — never when a real practice role resolved above.
        const override = readRoleOverride();
        if (override) {
          const local = readPlanOverride();
          setTier(local || "practice");
          setRole(override);
          // A demo/Portal doctor or receptionist needs the recommended default
          // permissions, otherwise Patients/Procedures/etc. never surface in the
          // sidebar. Owners are never permission-gated.
          setPermissions(
            override === "doctor"
              ? RECOMMENDED_DOCTOR_PERMISSIONS
              : override === "receptionist"
              ? RECOMMENDED_RECEPTIONIST_PERMISSIONS
              : []
          );
          setSource(local ? "local" : "default");
        } else {
          // Must never default to a privileged role here — get_current_practice_user
          // rejects inactive/staff-floor accounts anyway, and RequirePractice.tsx
          // blocks the dashboard; this is a defense-in-depth floor.
          setTier("practice");
          setRole("staff");
          setPermissions([]);
          setSource("default");
        }
      }
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  // Plan & Billing's dev switch buttons, or onboarding's claim step, call
  // this — writes the local override and updates state immediately (doesn't
  // wait for a reload).
  const setOverride = useCallback((next: PlanTier) => {
    writePlanOverride(next);
    setTier(next);
    setSource("local");
  }, []);

  // Plan & Billing's "Preview as" dev switcher calls this — but only when no
  // real backend role resolved (source === "api" means the live session IS
  // that role, so a demo override could only fake a role that would then
  // 403/loop against the real backend). Same no-op guard as the effect above.
  const setRoleOverride = useCallback((next: Role) => {
    if (source === "api") return;
    writeRoleOverride(next);
    setRole(next);
  }, [source]);

  return { tier, role, permissions, source, loading, setOverride, setRoleOverride };
}

export { tierAtLeast };
