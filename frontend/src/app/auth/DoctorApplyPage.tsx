import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SignUp, useAuth, useClerk, useUser, useSignUp } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { validateDoctorCode } from "../../api/practice";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyApplication } from "../../api/entities";

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

// Exported so DoctorApplyRecovery.tsx (a global safety net mounted at the
// app root, see App.tsx) can check the same marker regardless of which page
// Clerk's post-signup redirect actually lands the user on.
export const DOCTOR_APPLY_SESSION_KEY = "aesthetixai_doctor_apply_validated";
const SESSION_KEY = DOCTOR_APPLY_SESSION_KEY;

// Whether this visitor was ALREADY signed in (with a pre-existing session)
// when the apply flow first started, as opposed to becoming signed in right
// here via the <SignUp> form below. Clerk's routing="path" widget does a hard
// (full-page) navigation for the email-verification sub-step — which wipes
// React state — and its post-verification session-sync can hard-reload the
// page after the session already exists. After such a reload `isSignedIn` is
// true even though the visitor is mid-flow from THIS form, so the value must
// be captured once at flow start and persisted in sessionStorage (survives
// reloads) rather than re-derived from `isSignedIn` on every mount. Without
// this a fresh sign-up landed back on the "You're already signed in" dead-end
// notice instead of /doctor/apply/complete.
const DOCTOR_APPLY_WAS_SIGNED_IN_KEY = "aesthetixai_doctor_apply_was_signed_in";

function readWasSignedInDecision(): boolean | null {
  try {
    const raw = sessionStorage.getItem(DOCTOR_APPLY_WAS_SIGNED_IN_KEY);
    if (raw === null) return null;
    return raw === "1";
  } catch {
    return null;
  }
}

function writeWasSignedInDecision(value: boolean) {
  try {
    sessionStorage.setItem(DOCTOR_APPLY_WAS_SIGNED_IN_KEY, value ? "1" : "0");
  } catch {
    // private browsing / storage disabled — falls back to re-deriving from
    // `isSignedIn` on each mount, same as before this fix existed.
  }
}

function clearWasSignedInDecision() {
  try {
    sessionStorage.removeItem(DOCTOR_APPLY_WAS_SIGNED_IN_KEY);
  } catch {
    // nothing to clear
  }
}

// Export so DoctorApplyCompletePage.tsx can also clear the decision the moment
// a real application is submitted — otherwise the persisted "0" (from the
// sign-up that just finished) would keep a later visit to the apply page in
// the same tab classified as "mid-flow" forever.
export function clearDoctorApplyFlow() {
  clearWasSignedInDecision();
}

interface StoredValidation {
  practiceId: string;
  practiceName: string | null;
}

function readStoredValidation(): StoredValidation | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as StoredValidation) : null;
  } catch {
    return null;
  }
}

function writeStoredValidation(data: StoredValidation) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data));
  } catch {
    // private browsing / storage disabled — falls back to re-validating
    // from the URL on Clerk's next internal navigation, same as before
    // this fix existed.
  }
}

// Public entry point for a doctor self-registering — reached via a practice's
// shareable signup link (see dashboard/doctors/DoctorSignupLinkCard.tsx and
// backend/src/router/practice/practice_router.py's GET
// /practice/validate-doctor-code). Unlike DoctorSignUpPage.tsx (invite-only,
// no public link), this page has no gate other than a valid ?code= — the
// resulting account is created inactive server-side (see the user.created
// webhook's doctor_self_apply branch) until the Owner reviews and approves.
export function DoctorApplyPage() {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState<"checking" | "valid" | "invalid">("checking");
  const [practiceName, setPracticeName] = useState<string | null>(null);
  const [practiceId, setPracticeId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Clerk's own internal routing (routing="path") does a HARD
      // (full-page) navigation for some sub-steps — e.g.
      // /doctor/apply/verify-email-address for email verification — which
      // wipes React state entirely and drops the ?code= query param. Without
      // this, a legitimate mid-signup reload landed on "This link isn't
      // valid" — sessionStorage survives a real page reload within the same
      // tab, unlike component/URL state.
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
        const result = await validateDoctorCode(code);
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
      <AuthLayout variant="doctor">
        <p className="text-center text-sm text-ink-muted">Checking your invite link…</p>
      </AuthLayout>);

  }

  if (status === "invalid") {
    return (
      <AuthLayout variant="doctor">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <h1 className="font-display text-2xl font-600 text-ink">This link isn&apos;t valid</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Ask the practice for a fresh signup link, or check that you copied the whole URL.
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
    <AuthLayout variant="doctor">
      {clerkEnabled ?
      <DoctorApplySignUpForm practiceName={practiceName} practiceId={practiceId} /> :

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
// ClerkProvider) is only ever called when clerkEnabled — mirrors
// app/dashboard/plan/PlanContext.tsx's PlanProviderWithClerk split.
function DoctorApplySignUpForm({ practiceName, practiceId }: { practiceName: string | null; practiceId: string | null }) {
  const { isSignedIn, isLoaded } = useAuth();
  const { user } = useUser();
  const { signOut } = useClerk();
  const { authedFetch } = useAuthedFetch();
  const navigate = useNavigate();

  // Was there ALREADY a signed-in session the moment this page loaded, as
  // opposed to one that became signed-in because the visitor just completed
  // the SignUp form below? Distinguishes "reused an existing login" (show a
  // warning, see AlreadySignedInNotice below) from "just finished signing up
  // here" (the real redirect case this component exists for). Found the hard
  // way: an Owner opening this link in their own already-logged-in browser
  // silently filed a doctor application under their own Owner account with no
  // warning, because `isSignedIn` was already true before any effect ran.
  //
  // Clerk's routing="path" widget does a HARD (full-page) navigation for the
  // email-verification sub-step, which unmounts this component and reloads
  // the app — and its post-verification session-sync can produce another hard
  // reload AFTER the session already exists. On such a reload `isSignedIn`
  // is true even though the sign-up came from this very flow. Re-deriving
  // from `isSignedIn` on every mount therefore misclassifies a fresh sign-up
  // as "already signed in" (reproduced live: /clerk blank card race). The
  // one-time decision is persisted to sessionStorage, which survives reloads.
  const [wasAlreadySignedIn, setWasAlreadySignedIn] = useState<boolean | null>(null);
  useEffect(() => {
    if (!isLoaded || wasAlreadySignedIn !== null) return;
    const persisted = readWasSignedInDecision();
    if (persisted !== null) {
      setWasAlreadySignedIn(persisted);
      return;
    }
    const value = Boolean(isSignedIn);
    writeWasSignedInDecision(value);
    setWasAlreadySignedIn(value);
  }, [isLoaded, isSignedIn, wasAlreadySignedIn]);

  // A signed-in visitor with `wasAlreadySignedIn=true` already HAS an account
  // here on purpose — if that account already filed an application (a pending
  // doctor returning via the practice's shared signup link, e.g. saved while
  // waiting for approval), send them straight to the status page instead of
  // the "already signed in" dead-end. GET /doctor-applications/me returns it
  // for any signed-in user (pending/approved/rejected all live there). When
  // no application exists (an Owner opened their own practice's link by
  // accident), fall through to the notice — the original silent-filing guard.
  const [existingApp, setExistingApp] = useState<"checking" | "none" | "exists">("checking");
  useEffect(() => {
    if (wasAlreadySignedIn !== true) return;
    let cancelled = false;
    (async () => {
      try {
        await getMyApplication(authedFetch);
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
      navigate("/doctor/apply/pending", { replace: true });
    }
  }, [existingApp, navigate]);

  // Belt-and-suspenders for forceRedirectUrl: Clerk's own post-verification
  // redirect can lose a race against its internal dev-instance session-sync
  // navigation (observed via a captured `net::ERR_ABORTED` on the
  // /doctor/apply/complete request — a real, reproduced Clerk dev-mode
  // quirk during the accounts.dev cross-origin handoff, not just slow
  // network), leaving the SignUp widget blank at /verify-email-address even
  // though the account was actually created and signed in. Once Clerk
  // reports a real session THAT WASN'T ALREADY THERE ON LOAD, take the user
  // to /complete ourselves rather than trusting Clerk's redirect alone.
  // A returning applicant who signed in elsewhere mid-flow (stale persisted
  // "0" decision) is routed to the status page instead of being forced back
  // through the form.
  useEffect(() => {
    if (!isSignedIn || wasAlreadySignedIn !== false) return;
    let cancelled = false;
    (async () => {
      try {
        await getMyApplication(authedFetch);
        if (!cancelled) navigate("/doctor/apply/pending", { replace: true });
      } catch {
        if (!cancelled) navigate("/doctor/apply/complete", { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isSignedIn, wasAlreadySignedIn, authedFetch, navigate]);

  // SELF-HEALING: a deleted Clerk account can leave a stale session token in
  // the browser (Clerk docs: deleting a user does NOT invalidate their
  // existing client sessions), which made this page boot straight into the
  // "already signed in" notice — and even after sign-out, Clerk's widget can
  // mount as a silent blank card. Detect that (no .cl-card mounted a few
  // seconds after Clerk reports loaded) and offer recovery instead of leaving
  // a dead blank page (reported live on production-style flow testing).
  const [formMode, setFormMode] = useState<"widget" | "simple">("widget");
  const [widgetKey, setWidgetKey] = useState(0);
  const [widgetStuck, setWidgetStuck] = useState(false);

  useEffect(() => {
    if (formMode !== "widget" || !isLoaded || wasAlreadySignedIn !== false) return;
    let checks = 0;
    const interval = window.setInterval(() => {
      checks += 1;
      const card = document.querySelector<HTMLElement>(".cl-card");
      if (typeof card?.offsetHeight === "number" && card.offsetHeight > 0) {
        setWidgetStuck(false);
        window.clearInterval(interval);
        return;
      }
      if (checks >= 6) {
        setWidgetStuck(true);
        window.clearInterval(interval);
      }
    }, 1000);
    return () => window.clearInterval(interval);
  }, [formMode, isLoaded, wasAlreadySignedIn, widgetKey]);

  async function handleSignOut() {
    // signOut({ redirectUrl }) used to do the navigation itself — but after
    // an account is deleted at Clerk, the return leg of that redirect could
    // boot the widget straight back into a stale/blank state. Awaiting
    // signOut fully, THEN forcing a hard reload, gives Clerk a clean
    // signed-out boot every time with none of the redirect race.
    await signOut();
    // Drop the persisted "was already signed in" decision — if we kept it,
    // the reload below would read it back and re-show the notice even though
    // the user just signed out.
    clearWasSignedInDecision();
    window.location.replace(window.location.href);
  }

  if (wasAlreadySignedIn === null) return null;

  if (wasAlreadySignedIn) {
    // Checking the backend for an existing application happens async — show
    // a neutral "checking" state rather than flashing the notice first, since
    // a returning pending doctor will be navigated to the status page within
    // a few hundred ms.
    if (existingApp === "checking") {
      return (
        <p className="text-center text-sm text-ink-muted">Checking your account…</p>);

    }
    if (existingApp === "exists") return null;

    return (
      <AlreadySignedInNotice
        email={user?.primaryEmailAddress?.emailAddress}
        onSignOut={handleSignOut} />);

  }

  return (
    <>
      {practiceName &&
      <p className="mb-4 text-center text-sm text-ink-muted">
          Joining <span className="font-semibold text-ink">{practiceName}</span>
        </p>
      }
      {formMode === "widget" ?
      <>
          <SignUp
            key={widgetKey}
            routing="path"
            path="/doctor/apply"
            forceRedirectUrl="/doctor/apply/complete"
            unsafeMetadata={{ invite_type: "doctor_self_apply", practice_id: practiceId }}
            appearance={clerkAppearance} />

          {widgetStuck &&
          <StuckWidgetNotice
              onRetry={() => { setWidgetStuck(false); setWidgetKey((k) => k + 1); }}
              onUseSimple={() => setFormMode("simple")} />
          }

          <p className="mt-4 text-center text-xs text-ink-muted">
            Having trouble with the form?{" "}
            <button
              type="button"
              onClick={() => setFormMode("simple")}
              className="font-semibold text-accent-600 hover:underline">

              Use the simple sign-up instead
            </button>
          </p>
        </> :
      <SimpleSignUpForm
          practiceId={practiceId}
          onBackToWidget={() => { setFormMode("widget"); setWidgetStuck(false); }} />

      }
    </>);

}

// Recovery UI for the blank-widget state (see the SELF-HEALING comment above).
function StuckWidgetNotice({ onRetry, onUseSimple }: { onRetry: () => void; onUseSimple: () => void }) {
  return (
    <div className="mt-4 rounded-2xl border border-sand-200 bg-sand-100 p-4 text-center">
      <p className="text-sm font-semibold text-ink">The sign-up form is taking a while.</p>
      <p className="mt-1 text-xs text-ink-muted">
        Reload the form — or use the simple sign-up, which does the same thing with just email and password.
      </p>
      <div className="mt-3 flex items-center justify-center gap-3">
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center justify-center rounded-full bg-ink px-5 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent-600">

          Reload form
        </button>
        <button
          type="button"
          onClick={onUseSimple}
          className="inline-flex items-center justify-center rounded-full border border-sand-200 bg-white px-5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:text-ink">

          Use simple sign-up
        </button>
      </div>
    </div>);

}

// Falls back to Clerk's programmatic API (clerk.signUp.create) when the
// hosted <SignUp> widget can't mount — same unsafeMetadata the widget sets,
// so the backend user.created webhook's doctor_self_apply branch sees
// exactly the same payload. Email + password on step 1; if Clerk wants email
// verification, an OTP step (email_code) follows. On success this sets the
// session, and DoctorApplySignUpForm's "fresh sign-in" effect above takes
// the user to /doctor/apply/complete just like the widget path does.
function SimpleSignUpForm({ practiceId, onBackToWidget }: { practiceId: string | null; onBackToWidget: () => void }) {
  const { isLoaded, signUp, setActive } = useSignUp();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"create" | "verify">("create");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoaded) return;
    setSubmitting(true);
    setError(null);
    try {
      await signUp.create({
        emailAddress: email.trim(),
        password,
        unsafeMetadata: { invite_type: "doctor_self_apply", practice_id: practiceId }
      });
      if (signUp.status === "complete" && signUp.createdSessionId) {
        await setActive({ session: signUp.createdSessionId });
        return;
      }
      if (signUp.verifications?.emailAddress?.status === "unverified") {
        await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
        setStep("verify");
        return;
      }
      setError("This account needs an extra verification step the simple form can't handle — use the standard form.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create the account — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoaded) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await signUp.attemptEmailAddressVerification({ code: code.trim() });
      if (result.status === "complete" && result.createdSessionId) {
        await setActive({ session: result.createdSessionId });
        return;
      }
      setError("That code didn't verify — check it and try again, or reload for a fresh one.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed — try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white";

  if (step === "verify") {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 shadow-lift">
        <h1 className="font-display text-xl font-600 text-ink">Verify your email</h1>
        <p className="mt-1 text-sm text-ink-muted">
          We emailed a code to the address you entered. Enter it to finish creating your account.
        </p>
        <form onSubmit={handleVerify} className="mt-5 space-y-4">
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="6-digit code"
            className={inputClass}
            required />

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <button
            type="submit"
            disabled={!code.trim() || submitting}
            className="w-full rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-40">

            {submitting ? "Verifying…" : "Verify email"}
          </button>
        </form>
        <button type="button" onClick={onBackToWidget} className="mt-4 w-full text-center text-xs font-semibold text-ink-muted hover:text-ink">
          Back to standard form
        </button>
      </div>);

  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 shadow-lift">
      <h1 className="font-display text-xl font-600 text-ink">Create your account</h1>
      <p className="mt-1 text-sm text-ink-muted">
        Sign up with a new email — your application will be sent to the practice for approval.
      </p>
      <form onSubmit={handleCreate} className="mt-5 space-y-4">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email address"
          className={inputClass}
          required />

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password (at least 8 characters)"
          className={inputClass}
          minLength={8}
          required />

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <button
          type="submit"
          disabled={!email.trim() || !password || submitting}
          className="w-full rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-40">

          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <button type="button" onClick={onBackToWidget} className="mt-4 w-full text-center text-xs font-semibold text-ink-muted hover:text-ink">
        Back to standard form
      </button>
    </div>);

}

function AlreadySignedInNotice({ email, onSignOut }: { email: string | undefined; onSignOut: () => void }) {
  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
      <h1 className="font-display text-2xl font-600 text-ink">You&apos;re already signed in</h1>
      <p className="mt-2 text-sm text-ink-muted">
        {email ? <>You&apos;re signed in as <span className="font-semibold text-ink">{email}</span>.</> : "You're signed in with an existing account."}{" "}
        Applying here would file the application under that same account, not a new doctor. Sign out first if you meant
        to apply as someone else. If you recently removed this account from Clerk, signing out clears the leftover
        browser session too.
      </p>
      <button
        type="button"
        onClick={onSignOut}
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
