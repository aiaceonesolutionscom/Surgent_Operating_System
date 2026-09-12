import React, { createContext, useContext, useMemo } from "react";
import type { PlanTier } from "../../../data/planTiers";
import { tierAtLeast } from "../../../data/planTiers";
import type { Role } from "../../../data/roles";
import { usePlanTier, type PlanSource, capabilitiesFor, hasFeature, allowsCategory, allowsAgent } from "./plan";
import type { FeatureKey, PlanCapabilities } from "./plan";
import { useAuthedFetch } from "../../../api/authFetch";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;
type AuthedFetchBlob = ((path: string, init?: RequestInit) => Promise<Blob>) | null;

interface PlanContextValue {
  tier: PlanTier;
  role: Role;
  // Only meaningful when role === "doctor" — see data/doctorPermissions.ts.
  permissions: string[];
  source: PlanSource;
  loading: boolean;
  capabilities: PlanCapabilities;
  can: (feature: FeatureKey) => boolean;
  allowsCategory: (categoryId: string) => boolean;
  allowsAgent: (agentSlug: string) => boolean;
  atLeast: (min: PlanTier) => boolean;
  setOverride: (tier: PlanTier) => void;
  setRoleOverride: (role: Role) => void;
  // Exposed so other hooks that need a real backend call (e.g.
  // patients/usePatients.ts) don't have to repeat the Clerk-gated split
  // below just to get one — PlanProvider already wraps the whole dashboard
  // and already computes this for its own usePlanTier() call.
  authedFetch: AuthedFetch;
  // Sibling to authedFetch for endpoints that return a real file (invoice
  // PDFs) instead of JSON — see api/authFetch.ts's authedFetchBlob.
  authedFetchBlob: AuthedFetchBlob;
}

const PlanContext = createContext<PlanContextValue | null>(null);
const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

function useContextValue(
  tier: PlanTier,
  role: Role,
  permissions: string[],
  source: PlanSource,
  loading: boolean,
  setOverride: (t: PlanTier) => void,
  setRoleOverride: (r: Role) => void,
  authedFetch: AuthedFetch,
  authedFetchBlob: AuthedFetchBlob
): PlanContextValue {
  return useMemo<PlanContextValue>(
    () => ({
      tier,
      role,
      permissions,
      source,
      loading,
      capabilities: capabilitiesFor(tier),
      can: (feature: FeatureKey) => hasFeature(tier, feature),
      allowsCategory: (categoryId: string) => allowsCategory(tier, categoryId),
      allowsAgent: (agentSlug: string) => allowsAgent(tier, agentSlug),
      atLeast: (min: PlanTier) => tierAtLeast(tier, min),
      setOverride,
      setRoleOverride,
      authedFetch,
      authedFetchBlob
    }),
    [tier, role, permissions, source, loading, setOverride, setRoleOverride, authedFetch, authedFetchBlob]
  );
}

// useAuthedFetch() calls Clerk's useAuth(), which throws without a mounted
// <ClerkProvider> — index.tsx only mounts one when Clerk is configured. This
// component is only ever rendered when clerkEnabled is true (a build-time
// constant, never toggles mid-session), same split as
// profile/ProfilePage.tsx's AccountCard/AccountCardWithUser.
function PlanProviderWithClerk({ children }: { children: React.ReactNode }) {
  const { authedFetch, authedFetchBlob } = useAuthedFetch();
  const { tier, role, permissions, source, loading, setOverride, setRoleOverride } = usePlanTier(authedFetch);
  const value = useContextValue(tier, role, permissions, source, loading, setOverride, setRoleOverride, authedFetch, authedFetchBlob);
  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>;
}

function PlanProviderWithoutClerk({ children }: { children: React.ReactNode }) {
  const { tier, role, permissions, source, loading, setOverride, setRoleOverride } = usePlanTier(null);
  const value = useContextValue(tier, role, permissions, source, loading, setOverride, setRoleOverride, null, null);
  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>;
}

// Wraps DashboardLayout once — every page/component below it calls usePlan()
// instead of usePlanTier() directly, so the whole dashboard shares one
// resolution instead of each page mounting its own instance and potentially
// disagreeing (the same class of bug useDoctors.ts's comments already flag
// for per-page hook instances).
export function PlanProvider({ children }: { children: React.ReactNode }) {
  return clerkEnabled ?
  <PlanProviderWithClerk>{children}</PlanProviderWithClerk> :
  <PlanProviderWithoutClerk>{children}</PlanProviderWithoutClerk>;
}

export function usePlan(): PlanContextValue {
  const ctx = useContext(PlanContext);
  if (!ctx) throw new Error("usePlan() must be called inside <PlanProvider>");
  return ctx;
}
