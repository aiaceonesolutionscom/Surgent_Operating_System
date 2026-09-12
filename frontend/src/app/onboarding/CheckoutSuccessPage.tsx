import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2Icon, Loader2Icon, MailIcon } from "lucide-react";
import { SignUpButton, useUser } from "@clerk/clerk-react";
import { OnboardingLayout } from "./OnboardingLayout";
import { planFor, writePlanOverride } from "../dashboard/plan/plan";
import type { PlanTier } from "../../data/planTiers";
import { ONBOARDING_ROUTES } from "./routes";
import { getCheckoutSession } from "../../api/commerce";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);
const POLL_ATTEMPTS = 5;
const POLL_INTERVAL_MS = 1200;

// Stripe redirects here after a successful payment
// (backend/src/services/checkout/checkout_services.py builds this URL).
// `plan_tier`/`email` arrive as plain query params set before the Stripe
// redirect (not something Stripe fills in) — shown immediately while a
// short poll of GET /checkout/session/{id} confirms the backend actually
// has it marked paid. That confirmation matters once real Stripe is
// connected: Stripe's webhook and the browser's redirect can race, so the
// PendingSignup row isn't guaranteed to be marked completed the instant this
// page loads. In demo mode (no real Stripe keys — see checkout_services.py's
// _demo_checkout) there's no race, so this resolves on the first poll.
export function CheckoutSuccessPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const planTier = (params.get("plan_tier") as PlanTier) || "practice";
  const email = params.get("email") || "";
  const sessionId = params.get("session_id") || "";
  const plan = planFor(planTier);

  const [confirming, setConfirming] = useState(true);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setConfirming(false);
      return;
    }
    let cancelled = false;
    (async () => {
      for (let attempt = 0; attempt < POLL_ATTEMPTS; attempt++) {
        try {
          const status = await getCheckoutSession(sessionId);
          if (status.paid) {
            if (!cancelled) {
              setConfirmed(true);
              setConfirming(false);
            }
            return;
          }
        } catch {
          // keep polling — the row may just not exist yet
        }
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
      if (!cancelled) setConfirming(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const claimUrl = `${ONBOARDING_ROUTES.claim}?plan_tier=${planTier}&session_id=${encodeURIComponent(sessionId)}`;

  function continueWithoutClerk() {
    // Graceful degrade — same pattern used everywhere else Clerk is touched
    // in this app (Navbar, RequireAuth): if Clerk isn't configured, don't
    // block the flow, just skip straight to claiming.
    writePlanOverride(planTier);
    navigate(claimUrl);
  }

  if (confirming) {
    return (
      <OnboardingLayout step={{ current: 1, total: 3 }}>
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <Loader2Icon className="mx-auto h-6 w-6 animate-spin text-teal-600" />
          <p className="mt-3 text-sm text-ink-muted">Confirming your payment…</p>
        </div>
      </OnboardingLayout>);

  }

  if (!confirmed && sessionId) {
    return (
      <OnboardingLayout step={{ current: 1, total: 3 }}>
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-warning/10 text-warning">
            <MailIcon className="h-7 w-7" />
          </span>
          <p className="mt-4 text-lg font-bold text-ink">Still confirming your payment</p>
          <p className="mt-1.5 text-sm text-ink-muted">
            This can take a moment. We'll email you as soon as it's confirmed — no need to wait here.
          </p>
        </div>
      </OnboardingLayout>);

  }

  return (
    <OnboardingLayout step={{ current: 1, total: 3 }}>
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
          <CheckCircle2Icon className="h-7 w-7" />
        </span>
        <p className="mt-4 text-lg font-bold text-ink">Payment confirmed</p>
        <p className="mt-1.5 text-sm text-ink-muted">
          You're on the <span className="font-semibold text-teal-600">{plan.name}</span> plan — {plan.price}{plan.period}.
        </p>

        {clerkEnabled ?
        <ClerkAccountStep email={email} claimUrl={claimUrl} /> :

        <>
            <button
            onClick={continueWithoutClerk}
            className="mt-6 w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

              Continue to setup
            </button>
            <p className="mt-3 text-xs text-ink-muted">Use the same email you paid with.</p>
          </>
        }
      </div>
    </OnboardingLayout>);

}

// Split out so useUser() (a real Clerk hook) is only ever called when
// clerkEnabled is true — same pattern as profile/ProfilePage.tsx's
// AccountCard/AccountCardWithUser split, since useUser() throws without a
// mounted <ClerkProvider>.
function ClerkAccountStep({ email, claimUrl }: { email: string; claimUrl: string }) {
  const navigate = useNavigate();
  const { isSignedIn, isLoaded } = useUser();

  if (!isLoaded) {
    return <Loader2Icon className="mx-auto mt-6 h-5 w-5 animate-spin text-teal-600" />;
  }

  // Clerk (single-session mode, the default) refuses to open a sign-up modal
  // while already signed in — "cannot_render_single_session_enabled". Rather
  // than showing a button that throws, detect this and skip straight to
  // claiming with the existing session instead of asking for a new account.
  if (isSignedIn) {
    return (
      <>
        <button
          onClick={() => navigate(claimUrl)}
          className="mt-6 w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          Continue to setup
        </button>
        <p className="mt-3 text-xs text-ink-muted">You're already signed in — continuing with your current account.</p>
      </>);

  }

  return (
    <>
      <SignUpButton mode="modal" initialValues={email ? { emailAddress: email } : undefined} forceRedirectUrl={claimUrl}>
        <button className="mt-6 w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
          Create your account
        </button>
      </SignUpButton>
      <p className="mt-3 text-xs text-ink-muted">Use the same email you paid with.</p>
    </>);

}
