import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SignUp, useAuth, useClerk, useUser } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { validateStaffCode } from "../../api/practice";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyStaffApplication } from "../../api/entities";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

const clerkAppearance = {
  variables: {
    colorPrimary: "#2563EB",
    colorText: "#0F172A",
    colorTextSecondary: "#64748B",
    colorBackground: "#FFFFFF",
    borderRadius: "0.75rem",
    fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif'
  },
  elements: {
    rootBox: "w-full",
    card: "shadow-[0_20px_50px_-20px_rgba(11,29,38,0.25)] border border-sand-200 rounded-3xl",
    headerTitle: "font-display text-2xl",
    formButtonPrimary: "bg-accent-500 hover:bg-accent-700 text-sm normal-case"
  }
};

// Receptionist apply flow — the mirror of DoctorApplyPage, so front-desk staff
// onboard through the SAME share-link + Owner-approval mechanism as doctors
// (see dashboard/staff/StaffSignupLinkCard.tsx and backend
// /practice/validate-staff-code + the webhook's staff_self_apply branch).
export const STAFF_APPLY_SESSION_KEY = "aesthetixai_staff_apply_validated";
const SESSION_KEY = STAFF_APPLY_SESSION_KEY;
const STAFF_APPLY_WAS_SIGNED_IN_KEY = "aesthetixai_staff_apply_was_signed_in";

function readStoredValidation(): { practiceId: string; practiceName: string | null } | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as { practiceId: string; practiceName: string | null }) : null;
  } catch {
    return null;
  }
}

function writeStoredValidation(data: { practiceId: string; practiceName: string | null }) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  } catch {
    // private browsing / storage disabled — falls back to re-validating
  }
}

export function clearStaffApplyFlow() {
  try {
    sessionStorage.removeItem(STAFF_APPLY_WAS_SIGNED_IN_KEY);
  } catch {
    // nothing to clear
  }
}

export function StaffApplyPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<"checking" | "valid" | "invalid">("checking");
  const [practiceName, setPracticeName] = useState<string | null>(null);
  const [practiceId, setPracticeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Same decision as DoctorApplyPage: Clerk's routing="path" widget hard-
      // navigates for sub-steps (email verification) and drops ?code=, so a
      // validated code is persisted in sessionStorage (survives reloads).
      const stored = readStoredValidation();
      if (stored) {
        setPracticeId(stored.practiceId);
        setPracticeName(stored.practiceName);
        setStatus("valid");
        return;
      }

      const code = searchParams.get("code") || "";
      if (!code) {
        setStatus("invalid");
        return;
      }
      try {
        const result = await validateStaffCode(code);
        if (cancelled) return;
        if (result.valid && result.practice_id) {
          setPracticeName(result.practice_name);
          setPracticeId(result.practice_id);
          setStatus("valid");
          writeStoredValidation({ practiceId: result.practice_id, practiceName: result.practice_name });
        } else {
          setStatus("invalid");
        }
      } catch {
        if (!cancelled) setStatus("invalid");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === "checking") {
    return (
      <AuthLayout variant="staff">
        <p className="text-center text-sm text-ink-muted">Checking your invite link…</p>
      </AuthLayout>);

  }

  if (status === "invalid") {
    return (
      <AuthLayout variant="staff">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <h1 className="font-display text-2xl font-600 text-ink">This link isn&apos;t valid</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Ask the practice for a fresh staff signup link, or check that you copied the whole URL.
          </p>
          <Link
            to="/"
            className="mt-6 inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

            Back to home
          </Link>
        </div>
      </AuthLayout>);

  }

  return (
    <AuthLayout variant="staff">
      {clerkEnabled ?
      <StaffApplySignUpForm practiceName={practiceName} practiceId={practiceId} /> :

      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <h1 className="font-display text-2xl font-600 text-ink">Sign-up isn&apos;t configured yet</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Set <code className="rounded bg-sand-100 px-1.5 py-0.5 text-xs">VITE_CLERK_PUBLISHABLE_KEY</code> to enable
            authentication.
          </p>
        </div>
      }
    </AuthLayout>);

}

// Split out so useAuth() (a Clerk hook, throws without a mounted
// ClerkProvider) is only ever called when clerkEnabled — mirrors the doctor
// form's structure exactly.
function StaffApplySignUpForm({ practiceName, practiceId }: { practiceName: string | null; practiceId: string | null }) {
  const { isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const { authedFetch } = useAuthedFetch();
  const navigate = useNavigate();

  // Capture the already-signed-in decision once, persisted across Clerk's
  // hard navigations — same rationale as DoctorApplyPage.
  const [wasAlreadySignedIn, setWasAlreadySignedIn] = useState<boolean | null>(null);
  useEffect(() => {
    if (!isLoaded || wasAlreadySignedIn !== null) return;
    try {
      const raw = sessionStorage.getItem(STAFF_APPLY_WAS_SIGNED_IN_KEY);
      if (raw !== null) {
        setWasAlreadySignedIn(raw === "1");
        return;
      }
    } catch {
      // fall through to deriving from isSignedIn
    }
    const value = Boolean(isSignedIn);
    try {
      sessionStorage.setItem(STAFF_APPLY_WAS_SIGNED_IN_KEY, value ? "1" : "0");
    } catch {
      // storage unavailable
    }
    setWasAlreadySignedIn(value);
  }, [isLoaded, isSignedIn, wasAlreadySignedIn]);

  // A returning receptionist applicant (already signed in, application filed)
  // is routed straight to the status page instead of the notice.
  const [existingApp, setExistingApp] = useState<"checking" | "none" | "exists">("checking");
  useEffect(() => {
    if (wasAlreadySignedIn !== true) return;
    let cancelled = false;
    (async () => {
      try {
        await getMyStaffApplication(authedFetch);
        if (!cancelled) setExistingApp("exists");
      } catch {
        if (!cancelled) setExistingApp("none");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [wasAlreadySignedIn, authedFetch]);

  useEffect(() => {
    if (existingApp === "exists") {
      navigate("/staff/apply/pending", { replace: true });
    }
  }, [existingApp, navigate]);

  // Fresh sign-up after the widget finishes — route to /complete ourselves as
  // a belt-and-suspenders for Clerk's forceRedirectUrl (same race DoctorApplyPage
  // patches).
  useEffect(() => {
    if (!isSignedIn || wasAlreadySignedIn !== false) return;
    let cancelled = false;
    (async () => {
      try {
        await getMyStaffApplication(authedFetch);
        if (!cancelled) navigate("/staff/apply/pending", { replace: true });
      } catch {
        if (!cancelled) navigate("/staff/apply/complete", { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, wasAlreadySignedIn, authedFetch, navigate]);

  async function handleSignOut() {
    await signOut();
    clearStaffApplyFlow();
    window.location.replace(window.location.href);
  }

  if (wasAlreadySignedIn === null) return null;

  if (wasAlreadySignedIn) {
    if (existingApp === "checking") {
      return <p className="text-center text-sm text-ink-muted">Checking your account…</p>;
    }
    if (existingApp === "exists") return null;

    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        <h1 className="font-display text-2xl font-600 text-ink">You&apos;re already signed in</h1>
        <p className="mt-2 text-sm text-ink-muted">
          {user?.primaryEmailAddress?.emailAddress ? (
            <>
              You&apos;re signed in as{" "}
              <span className="font-semibold text-ink">{user.primaryEmailAddress.emailAddress}</span>.
            </>
          ) : (
            "You're signed in with an existing account."
          )}{" "}
          Applying here would file the application under that same account. Sign out first if you meant to apply as
          someone else.
        </p>
        <button
          type="button"
          onClick={handleSignOut}
          className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

          Sign out and continue
        </button>
        <Link
          to="/dashboard"
          className="mt-3 inline-flex w-full items-center justify-center rounded-full border border-sand-200 px-6 py-3 text-sm font-semibold text-ink transition-colors hover:border-teal-600/40 hover:text-teal-600">

          Take me to my dashboard
        </Link>
      </div>);

  }

  return (
    <>
      {practiceName &&
      <p className="mb-4 text-center text-sm text-ink-muted">
          Joining <span className="font-semibold text-ink">{practiceName}</span>
        </p>
      }
      <SignUp
        routing="path"
        path="/staff/apply"
        forceRedirectUrl="/staff/apply/complete"
        unsafeMetadata={{ invite_type: "staff_self_apply", practice_id: practiceId }}
        appearance={clerkAppearance} />

      <p className="mt-4 text-center text-xs text-ink-muted">
        You&apos;ll be able to access the front desk once the practice approves your application.
      </p>
    </>);

}