import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClockIcon, CheckCircle2Icon, XCircleIcon } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyStaffApplication, type StaffApplicationResponse } from "../../api/entities";

const POLL_MS = 8000;

// Status page for a receptionist self-application — the mirror of
// DoctorApplyPendingPage. Polls until the Owner reviews. Unlike the doctor
// page it deliberately distinguishes "no application found" (the Clerk
// webhook never created the account, or the sign-up step was skipped) from a
// transient network error, so it never waits forever on a ghost application.
export function StaffApplyPendingPage() {
  const { authedFetch } = useAuthedFetch();
  const { isLoaded, isSignedIn } = useAuth();
  const [application, setApplication] = useState<StaffApplicationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const app = await getMyStaffApplication(authedFetch);
        if (cancelled) return;
        setApplication(app);
        setNotFound(false);
      } catch (err) {
        if (cancelled) return;
        const status = (err as { status?: number } | undefined)?.status;
        // A real 404 means there's no application for this account at all —
        // the webhook never fired or sign-up wasn't finished. Stop the
        // endless "waiting" loop and say so honestly instead.
        if (status === 404) {
          setNotFound(true);
          return;
        }
        // transient error — keep polling
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
      <AuthLayout variant="staff">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
            <ClockIcon className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-2xl font-600 text-ink">Check your application</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Sign back in with the email you applied with to see the latest status — once your practice approves you,
            your front-desk access unlocks automatically.
          </p>
          <Link
            to="/sign-in"
            className="mt-6 inline-flex w-full items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

            Sign in to check
          </Link>
        </div>
      </AuthLayout>);

  }

  if (loading) {
    return (
      <AuthLayout variant="staff">
        <p className="text-center text-sm text-ink-muted">Checking your application…</p>
      </AuthLayout>);

  }

  if (notFound) {
    return (
      <AuthLayout variant="staff">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10 text-danger">
            <XCircleIcon className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-2xl font-600 text-ink">No application found</h1>
          <p className="mt-2 text-sm text-ink-muted">
            We couldn&apos;t find a receptionist application for this account — it likely means sign-up wasn&apos;t
            finished or the practice link wasn&apos;t used. Start again with the practice&apos;s staff signup link.
          </p>
          <Link
            to="/"
            className="mt-6 inline-flex items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

            Back to home
          </Link>
        </div>
      </AuthLayout>);

  }

  return (
    <AuthLayout variant="staff">
      <ApplicationCard application={application} />
    </AuthLayout>);

}

function ApplicationCard({ application }: { application: StaffApplicationResponse | null }) {
  if (!application || application.status === "pending") {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
          <ClockIcon className="h-6 w-6" />
        </span>
        <h1 className="mt-4 font-display text-2xl font-600 text-ink">Waiting for approval</h1>
        <p className="mt-2 text-sm text-ink-muted">
          The practice has your application. This page will update automatically once they review it — no need to
          refresh.
        </p>
      </div>);

  }

  if (application.status === "approved") {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-success/10 text-success">
          <CheckCircle2Icon className="h-6 w-6" />
        </span>
        <h1 className="mt-4 font-display text-2xl font-600 text-ink">You&apos;re approved!</h1>
        <p className="mt-2 text-sm text-ink-muted">Your front-desk access is ready.</p>
        <Link
          to="/dashboard"
          className="mt-6 inline-flex items-center justify-center rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

          Go to dashboard
        </Link>
      </div>);

  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10 text-danger">
        <XCircleIcon className="h-6 w-6" />
      </span>
      <h1 className="mt-4 font-display text-2xl font-600 text-ink">Application not approved</h1>
      {application.rejected_reason &&
      <p className="mt-2 text-sm text-ink-muted">{application.rejected_reason}</p>
      }
      <p className="mt-2 text-sm text-ink-muted">Ask the practice if you&apos;d like to re-apply.</p>
    </div>);

}