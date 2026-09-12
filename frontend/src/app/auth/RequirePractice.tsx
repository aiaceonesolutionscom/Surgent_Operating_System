import React, { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { SparklesIcon } from "lucide-react";
import { readPlanOverride } from "../dashboard/plan/plan";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyPractice } from "../../api/practice";
import { getMyApplication, getMyStaffApplication, getMyOrgRequest } from "../../api/entities";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

// Closes the gap app/auth/README.md documents: RequireAuth only proves
// someone is signed in, not that they belong to a practice with an active
// role. Checks the REAL backend (GET /practice/me) directly rather than
// through usePlan()/PlanProvider — PlanProvider only mounts inside
// DashboardLayout, which this component wraps, so it isn't available yet
// here. This is the actual enforcement point that keeps a pending doctor
// application (is_active=False until an Owner approves — see
// doctor_applications_service.py) out of the dashboard; plan.ts's
// usePlanTier role default is only a defense-in-depth backstop, not the
// primary gate. Degrades to "always allow" when Clerk itself is disabled,
// so local dev/testing is never blocked by this.
export function RequirePractice({ children }: { children: React.ReactNode }) {
  if (!clerkEnabled) return <>{children}</>;
  return <RealPracticeGate>{children}</RealPracticeGate>;
}

type CheckState = "loading" | "ok" | "pending-doctor" | "pending-staff" | "org-request" | "no-practice";

function RealPracticeGate({ children }: { children: React.ReactNode }) {
  const { authedFetch, isSignedIn, isLoaded } = useAuthedFetch();
  const [state, setState] = useState<CheckState>("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Clerk's isSignedIn is undefined while it's still figuring out the
      // session (e.g. right after a fresh page load/reload) — `!isSignedIn`
      // alone can't tell "still loading" apart from "actually signed out",
      // so it was racing into the "no active plan" screen on every reload
      // even for a genuinely signed-in user. Wait for isLoaded first.
      if (!isLoaded) return;
      if (!isSignedIn) {
        if (!cancelled) setState(readPlanOverride() ? "ok" : "no-practice");
        return;
      }
      try {
        await getMyPractice(authedFetch);
        if (!cancelled) setState("ok");
        return;
      } catch {
        // No active User/Practice for this session yet — check whether it's
        // specifically a pending doctor application before falling back to
        // the generic "no plan" message.
      }
      try {
        const application = await getMyApplication(authedFetch);
        if (!cancelled) setState(application.status === "pending" ? "pending-doctor" : "no-practice");
        return;
      } catch {
        // no doctor application — check the receptionist path before giving up
      }
      try {
        const staffApplication = await getMyStaffApplication(authedFetch);
        if (!cancelled) setState(staffApplication.status === "pending" ? "pending-staff" : "no-practice");
        return;
      } catch {
        // no staff application — check the org-request path before giving up
      }
      try {
        await getMyOrgRequest(authedFetch);
        if (!cancelled) setState("org-request");
      } catch {
        if (!cancelled) setState(readPlanOverride() ? "ok" : "no-practice");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, isSignedIn, isLoaded]);

  if (state === "loading") return null;
  if (state === "ok") return <>{children}</>;
  if (state === "pending-doctor") return <Navigate to="/doctor/apply/pending" replace />;
  if (state === "pending-staff") return <Navigate to="/staff/apply/pending" replace />;
  if (state === "org-request") return <Navigate to="/org/apply" replace />;

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-6">
      <div className="w-full max-w-sm rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
          <SparklesIcon className="h-6 w-6" />
        </span>
        <p className="mt-4 text-lg font-bold text-ink">No active plan yet</p>
        <p className="mt-1.5 text-sm text-ink-muted">
          Your account isn't linked to a plan yet — pick one to get your dashboard set up.
        </p>
        <Link
          to="/#pricing"
          className="mt-6 block w-full rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          See plans
        </Link>
      </div>
    </div>);

}
