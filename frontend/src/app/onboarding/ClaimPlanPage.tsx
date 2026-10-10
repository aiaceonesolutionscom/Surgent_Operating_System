import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangleIcon, Loader2Icon } from "lucide-react";
import { OnboardingLayout } from "./OnboardingLayout";
import { writePlanOverride } from "../dashboard/plan/plan";
import type { PlanTier } from "../../data/planTiers";
import { ONBOARDING_ROUTES } from "./routes";
import { useAuthedFetch } from "../../api/authFetch";
import { ApiError } from "../../api/client";
import { claimPlan } from "../../api/practice";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

// Reached after Clerk sign-up completes (forceRedirectUrl from
// CheckoutSuccessPage, carrying session_id + plan_tier). Calls the real
// POST /api/v1/practice/claim (backend/src/router/practice/practice_router.py)
// to provision Practice + User + Subscription from the paid session. If the
// claim fails (backend unreachable, session not found, email mismatch) the user
// sees the reason and can retry - there is no silent local fallback, because a
// clinic that was never provisioned can't use the dashboard. Without Clerk
// (local QA only) the dev plan override stands in for the claim.
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
  const sessionId = params.get("session_id") || "";
  const [attempt, setAttempt] = useState(0);
  const [failure, setFailure] = useState<string | null>(null);
  const started = useRef(-1);

  useEffect(() => {
    if (isSignedIn === undefined || started.current === attempt) return;
    started.current = attempt;
    setFailure(null);
    (async () => {
      if (!isSignedIn || !sessionId) {
        // Nothing to claim (no payment session in the URL, or not signed in yet).
        navigate(ONBOARDING_ROUTES.setup);
        return;
      }
      try {
        await claimPlan(authedFetch, sessionId);
        navigate(ONBOARDING_ROUTES.setup);
      } catch (err) {
        // Don't pretend it worked: without a provisioned clinic the dashboard
        // would just bounce the user back. Say what happened and let them retry.
        console.error("Claiming the paid plan failed:", err);
        setFailure(err instanceof ApiError && err.message ? err.message : "We couldn't finish setting up your account.");
      }
    })();
  }, [isSignedIn, attempt, sessionId, authedFetch, navigate]);

  if (failure) {
    return (
      <OnboardingLayout step={{ current: 2, total: 3 }}>
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertTriangleIcon className="h-6 w-6 text-danger" />
          <p className="text-sm text-ink">{failure}</p>
          <p className="text-xs text-ink-muted">Your payment is safe. Use the same email you paid with, then try again.</p>
          <button
            type="button"
            onClick={() => setAttempt((n) => n + 1)}
            className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            Try again
          </button>
        </div>
      </OnboardingLayout>);

  }

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
