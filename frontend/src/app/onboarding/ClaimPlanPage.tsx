import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2Icon } from "lucide-react";
import { OnboardingLayout } from "./OnboardingLayout";
import { writePlanOverride } from "../dashboard/plan/plan";
import type { PlanTier } from "../../data/planTiers";
import { ONBOARDING_ROUTES } from "./routes";
import { useAuthedFetch } from "../../api/authFetch";
import { claimPlan } from "../../api/practice";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

// Reached after Clerk sign-up completes (forceRedirectUrl from
// CheckoutSuccessPage, carrying session_id + plan_tier). Calls the real
// POST /api/v1/practice/claim (backend/src/router/practice/practice_router.py)
// to provision Practice + User + Subscription from the paid session. Any
// failure (backend unreachable, session not found, email mismatch) degrades
// to the local plan override instead of trapping the user — same
// graceful-degradation pattern used everywhere else Clerk is touched in this
// app. The dashboard reads the same source either way (usePlanTier.ts's
// chain: real /practice/me first, local override as fallback).
export function ClaimPlanPage() {
  return clerkEnabled ? <ClaimWithClerk /> : <ClaimWithoutClerk />;
}

function ClaimWithoutClerk() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const planTier = (params.get("plan_tier") as PlanTier) || "practice";

  useEffect(() => {
    writePlanOverride(planTier);
    const t = setTimeout(() => navigate(ONBOARDING_ROUTES.setup), 600);
    return () => clearTimeout(t);
  }, [planTier, navigate]);

  return <ClaimingScreen />;
}

// useAuthedFetch() calls Clerk's useAuth(), safe here only because this
// component is exclusively rendered when clerkEnabled is true (see
// PlanContext.tsx's identical split for why this is safe despite looking
// conditional).
function ClaimWithClerk() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { authedFetch, isSignedIn } = useAuthedFetch();
  const planTier = (params.get("plan_tier") as PlanTier) || "practice";
  const sessionId = params.get("session_id") || "";
  const [attempted, setAttempted] = useState(false);

  useEffect(() => {
    if (isSignedIn === undefined || attempted) return;
    setAttempted(true);
    (async () => {
      if (isSignedIn && sessionId) {
        try {
          const result = await claimPlan(authedFetch, sessionId);
          writePlanOverride(result.plan_tier);
          navigate(ONBOARDING_ROUTES.setup);
          return;
        } catch {
          // Real claim failed — fall through to local-only below rather
          // than stranding the user on this page.
        }
      }
      writePlanOverride(planTier);
      navigate(ONBOARDING_ROUTES.setup);
    })();
  }, [isSignedIn, attempted, sessionId, planTier, authedFetch, navigate]);

  return <ClaimingScreen />;
}

function ClaimingScreen() {
  return (
    <OnboardingLayout step={{ current: 2, total: 3 }}>
      <div className="flex flex-col items-center gap-3 py-10 text-center">
        <Loader2Icon className="h-6 w-6 animate-spin text-teal-600" />
        <p className="text-sm text-ink-muted">Setting up your account…</p>
      </div>
    </OnboardingLayout>);

}
