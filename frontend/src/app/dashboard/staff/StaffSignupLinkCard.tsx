import { useEffect, useState } from "react";
import { Link2Icon, CopyIcon, CheckIcon, RefreshCwIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { getStaffSignupCode, regenerateStaffSignupCode } from "../../../api/practice";

// Owner-only — the shareable link a receptionist uses to self-register (see
// app/auth/StaffApplyPage.tsx and backend/src/services/practice/
// practice_services.py's staff_signup_code). The receptionist mirror of
// DoctorSignupLinkCard, so front-desk staff onboard the SAME way doctors do
// (link + Owner approval), replacing the old Clerk email invite. Regenerating
// invalidates any previously shared link.
export function StaffSignupLinkCard() {
  const { authedFetch, role } = usePlan();
  const [signupUrl, setSignupUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || role !== "owner") {
        setLoading(false);
        return;
      }
      try {
        const result = await getStaffSignupCode(authedFetch);
        if (!cancelled) setSignupUrl(result.signup_url);
      } catch {
        if (!cancelled) setSignupUrl(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, role]);

  async function handleRegenerate() {
    if (!authedFetch) return;
    setBusy(true);
    try {
      const result = await regenerateStaffSignupCode(authedFetch);
      setSignupUrl(result.signup_url);
    } catch {
      // leave the existing link showing — regeneration just didn't happen
    } finally {
      setBusy(false);
    }
  }

  function handleCopy() {
    if (!signupUrl) return;
    navigator.clipboard?.writeText(signupUrl).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (role !== "owner") return null;

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <Link2Icon className="h-4 w-4 text-teal-600" /> Receptionist signup link
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        Share this with someone for the front desk — they register themselves, and you&apos;ll review and approve their
        access before it goes live.
      </p>

      {loading ?
      <p className="mt-3 text-sm text-ink-muted">Loading…</p> :
      !signupUrl ?
      <p className="mt-3 text-sm text-ink-muted">Couldn&apos;t load the signup link.</p> :

      <div className="mt-3 flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-xl bg-sand-100 px-3.5 py-2.5 text-xs text-ink-soft">{signupUrl}</code>
          <button
          type="button"
          onClick={handleCopy}
          className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

            {copied ? <CheckIcon className="h-3.5 w-3.5 text-teal-600" /> : <CopyIcon className="h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
          <button
          type="button"
          onClick={handleRegenerate}
          disabled={busy}
          title="Regenerate — invalidates the current link"
          className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2.5 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">

            <RefreshCwIcon className="h-3.5 w-3.5" /> {busy ? "…" : "Regenerate"}
          </button>
        </div>
      }
    </div>);

}