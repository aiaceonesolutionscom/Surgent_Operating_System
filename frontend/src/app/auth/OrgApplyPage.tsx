import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClockIcon, CheckCircle2Icon, XCircleIcon, Building2Icon } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyOrgRequest, submitOrgRequest, type OrgRequestResponse } from "../../api/entities";

const POLL_MS = 8000;

// Lands here after a brand-new plain /sign-up (see SignUpPage.tsx's
// unsafeMetadata={{invite_type: "org_request"}}) — no practice/dashboard
// access exists yet. First collects the practice name (self-heals the
// PendingSignup row if the user.created webhook hasn't reached this backend
// yet — same reasoning as DoctorApplyPage's known local-dev gap), then polls
// for a Super Admin's approve/reject decision.
export function OrgApplyPage() {
  const { authedFetch } = useAuthedFetch();
  const { isLoaded, isSignedIn } = useAuth();
  const [request, setRequest] = useState<OrgRequestResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const req = await getMyOrgRequest(authedFetch);
        if (cancelled) return;
        setRequest(req);
      } catch {
        // No PendingSignup row yet (webhook hasn't landed) — the form below
        // will create one on first submit. Not an error state.
        if (!cancelled) setRequest(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
      if (!cancelled) timer = setTimeout(poll, POLL_MS);
    }
    poll();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [authedFetch]);

  if (isLoaded && !isSignedIn) {
    return (
      <AuthLayout variant="doctor">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
            <Building2Icon className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-2xl font-600 text-ink">Check your request</h1>
          <p className="mt-2 text-sm text-ink-muted">Sign back in to see the latest status of your organization request.</p>
          <Link
            to="/sign-in"
            className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">
            Sign in to check
          </Link>
        </div>
      </AuthLayout>
    );
  }

  if (loading) {
    return (
      <AuthLayout variant="doctor">
        <p className="text-center text-sm text-ink-muted">Checking your request…</p>
      </AuthLayout>
    );
  }

  if (!request || !request.org_name) {
    return (
      <AuthLayout variant="doctor">
        <OrgNameForm onSubmitted={(r) => setRequest(r)} authedFetch={authedFetch} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout variant="doctor">
      <RequestCard request={request} />
    </AuthLayout>
  );
}

function OrgNameForm({ authedFetch, onSubmitted }: { authedFetch: ReturnType<typeof useAuthedFetch>["authedFetch"]; onSubmitted: (r: OrgRequestResponse) => void }) {
  const [orgName, setOrgName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!orgName.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      const result = await submitOrgRequest(authedFetch, orgName.trim());
      onSubmitted(result);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't submit — try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
        <Building2Icon className="h-6 w-6" />
      </span>
      <h1 className="mt-4 font-display text-2xl font-600 text-ink">Tell us about your practice</h1>
      <p className="mt-2 text-sm text-ink-muted">
        One more step — your own practice name. Our team reviews every new organization before it goes live.
      </p>
      <input
        autoFocus
        value={orgName}
        onChange={(e) => setOrgName(e.target.value)}
        placeholder="e.g. Riverside Aesthetic Clinic"
        className="mt-5 w-full rounded-xl border border-sand-200 bg-canvas px-4 py-3 text-sm text-ink outline-none transition-colors focus:border-accent-500/50 focus:bg-white"
      />
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      <button
        type="submit"
        disabled={saving || !orgName.trim()}
        className="mt-5 inline-flex w-full items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-40">
        {saving ? "Submitting…" : "Submit for review"}
      </button>
    </form>
  );
}

function RequestCard({ request }: { request: OrgRequestResponse }) {
  if (request.status === "pending") {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
          <ClockIcon className="h-6 w-6" />
        </span>
        <h1 className="mt-4 font-display text-2xl font-600 text-ink">Reviewing your request</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Our team is reviewing <span className="font-semibold text-ink">{request.org_name}</span>. This page updates
          automatically once approved — no need to refresh. You can close this tab and sign back in anytime.
        </p>
      </div>
    );
  }

  if (request.status === "approved") {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-success/10 text-success">
          <CheckCircle2Icon className="h-6 w-6" />
        </span>
        <h1 className="mt-4 font-display text-2xl font-600 text-ink">You&apos;re approved!</h1>
        <p className="mt-2 text-sm text-ink-muted">{request.org_name} is ready to set up.</p>
        <Link
          to="/onboarding/setup"
          className="mt-6 inline-flex items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">
          Set up your practice
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10 text-danger">
        <XCircleIcon className="h-6 w-6" />
      </span>
      <h1 className="mt-4 font-display text-2xl font-600 text-ink">Request not approved</h1>
      {request.rejected_reason && <p className="mt-2 text-sm text-ink-muted">{request.rejected_reason}</p>}
    </div>
  );
}
