import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClockIcon, CheckCircle2Icon, XCircleIcon, LinkIcon, CheckIcon } from "lucide-react";
import { useAuth } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { useAuthedFetch } from "../../api/authFetch";
import { getMyApplication, type DoctorApplicationResponse } from "../../api/entities";

const POLL_MS = 8000;

export function DoctorApplyPendingPage() {
  const { authedFetch } = useAuthedFetch();
  const { isLoaded, isSignedIn } = useAuth();
  const [application, setApplication] = useState<DoctorApplicationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    async function poll() {
      try {
        const app = await getMyApplication(authedFetch);
        if (cancelled) return;
        setApplication(app);
        setNotFound(false);
      } catch (err) {
        if (cancelled) return;
        const status = (err as { status?: number } | undefined)?.status;
        // A real 404 means there's no application for this account at all —
        // the user.created webhook never fired or sign-up wasn't finished
        // (live finding: the owner's Doctor Requests stayed empty while this
        // page showed "waiting" forever because no application row existed).
        // Stop the endless loop and say so honestly instead.
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

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(window.location.origin + "/doctor/apply/pending");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard unavailable — ignore
    }
  }

  // A signed-out visitor can land here from a saved bookmark (or the global
  // DoctorApplyRecovery race) before logging back in — show a sign-in CTA
  // instead of an endless "waiting" spinner, since getMyApplication would
  // just throw 401 in that state.
  if (isLoaded && !isSignedIn) {
    return (
      <AuthLayout variant="doctor">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-500/8 text-accent-500">
            <ClockIcon className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-2xl font-600 text-ink">Check your application</h1>
          <p className="mt-2 text-sm text-ink-muted">
            Sign back in with the email you applied with to see the latest status — once your practice approves you,
            your dashboard unlocks automatically.
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
      <AuthLayout variant="doctor">
        <p className="text-center text-sm text-ink-muted">Checking your application…</p>
      </AuthLayout>);

  }

  if (notFound) {
    return (
      <AuthLayout variant="doctor">
        <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-danger/10 text-danger">
            <XCircleIcon className="h-6 w-6" />
          </span>
          <h1 className="mt-4 font-display text-2xl font-600 text-ink">No application found</h1>
          <p className="mt-2 text-sm text-ink-muted">
            We couldn&apos;t find a doctor application for this account — sign-up likely wasn&apos;t finished, so
            nothing reached the practice for review. Start again with the practice&apos;s doctor signup link.
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
    <AuthLayout variant="doctor">
      <ApplicationCard application={application} />
      <div className="mt-4 flex flex-col items-center gap-2">
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex items-center gap-2 rounded-full border border-sand-200 bg-white px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:bg-sand-100 hover:text-ink">

          {copied ? <CheckIcon className="h-4 w-4 text-success" /> : <LinkIcon className="h-4 w-4" />}
          {copied ? "Link copied — keep it somewhere safe" : "Save this page to check back anytime"}
        </button>
        <p className="text-center text-xs text-ink-muted">
          You can close this tab and come back later — just sign in with the email you applied with. No new link or code
          needed.
        </p>
      </div>
    </AuthLayout>);

}

function ApplicationCard({ application }: { application: DoctorApplicationResponse | null }) {
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
        <p className="mt-2 text-sm text-ink-muted">Your dashboard is ready.</p>
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
      <Link
        to="/doctor/apply/complete"
        className="mt-6 inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

        Update and resubmit
      </Link>
    </div>);

}
