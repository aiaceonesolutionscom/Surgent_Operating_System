import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";
import { useAuthedFetch } from "../../api/authFetch";
import { submitMyStaffApplication } from "../../api/entities";
import { STAFF_APPLY_SESSION_KEY, clearStaffApplyFlow } from "./StaffApplyPage";

// Reached right after Clerk sign-up (StaffApplyPage's forceRedirectUrl) —
// the applicant's User row already exists (inactive) by now, created by the
// user.created webhook's staff_self_apply branch. This form turns that bare
// account into a real, reviewable application the Owner can approve.
export function StaffApplyCompletePage() {
  const { user } = useUser();
  const { authedFetch } = useAuthedFetch();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setName(`${user.firstName || ""} ${user.lastName || ""}`.trim());
    }
  }, [user]);

  const email = user?.primaryEmailAddress?.emailAddress || "";
  const canSubmit = Boolean(name.trim() && email) && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitMyStaffApplication(authedFetch, {
        name: name.trim(),
        email,
        phone: phone || null
      });
      try {
        sessionStorage.removeItem(STAFF_APPLY_SESSION_KEY);
      } catch {
        // private browsing / storage disabled — nothing to clear
      }
      clearStaffApplyFlow();
      navigate("/staff/apply/pending");
    } catch (err) {
      setError(err instanceof Error && err.message ? `Couldn't submit — ${err.message}` : "Couldn't submit — try again.");
      setSubmitting(false);
    }
  }

  const inputClass =
    "w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white";

  return (
    <AuthLayout variant="staff">
      <div className="w-full max-w-lg">
        <h1 className="mb-1 font-display text-2xl font-600 text-ink">Tell us about yourself</h1>
        <p className="mb-6 text-sm text-ink-muted">
          This goes to the practice owner for review — once they approve, your front-desk access unlocks automatically.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Full name *</span>
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="Sarah Ahmed" required className={inputClass} />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Email</span>
            <input type="email" value={email} disabled className={`${inputClass} disabled:opacity-60`} />
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Phone</span>
            <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 (555) 000-0000" className={inputClass} />
          </label>

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-40">

            {submitting ? "Submitting…" : "Submit for review"}
          </button>
        </form>
      </div>
    </AuthLayout>);

}