import React, { useEffect, useState } from "react";
import { KeyRoundIcon, RefreshCwIcon, SendIcon, PowerIcon, CheckCircle2Icon, ShieldAlertIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import {
  enablePatientPortal,
  resendPatientPortalInvite,
  generatePatientPortalPin,
  disablePatientPortal,
  getPatientPortalAccess
} from "../../../api/entities";

// Owner-only — manages a patient's Patient Portal access. Staff flip access
// on/off, and the clinic one-time login PIN lives here: staff read it back to
// the patient over the phone (or it goes out with the WhatsApp/email invite).
// The patient logs in at /user with their phone number + this PIN, then sets
// their own permanent PIN on first login. Backed by
// backend/src/router/patient_portal/patient_portal_router.py.
export function PatientPortalLinkCard({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const [portalId, setPortalId] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [pin, setPin] = useState<string | null>(null);
  const [pinExpiresAt, setPinExpiresAt] = useState<string | null>(null);
  const [pinSet, setPinSet] = useState(false);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [lastInviteSent, setLastInviteSent] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || role !== "owner") {
        setLoading(false);
        return;
      }
      try {
        const res = await getPatientPortalAccess(authedFetch, patientId);
        if (!cancelled) {
          setPortalId(res.portal_id);
          setEnabled(res.enabled);
          setPin(res.pin);
          setPinExpiresAt(res.pin_expires_at);
          setPinSet(res.pin_set);
        }
      } catch {
        // leave defaults — treated as "not enabled yet"
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, role, patientId]);

  if (role !== "owner") return null;

  async function handleEnable() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      const res = await enablePatientPortal(authedFetch, patientId);
      setPortalId(res.portal_id);
      setEnabled(true);
      setPin(res.pin);
      setPinExpiresAt(res.pin_expires_at);
      setLastInviteSent(res.invite_sent);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't enable the portal — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleGeneratePin() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      const res = await generatePatientPortalPin(authedFetch, patientId);
      setPin(res.pin);
      setPinExpiresAt(res.pin_expires_at);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't generate a new PIN — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResendInvite() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      const res = await resendPatientPortalInvite(authedFetch, patientId);
      setPin(res.pin);
      setPinExpiresAt(res.pin_expires_at);
      setLastInviteSent(true);
    } catch (err: unknown) {
      setLastInviteSent(false);
      setError(err instanceof Error && err.message ? err.message : "Couldn't resend the invite — check the patient has a phone or email on file.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      const res = await disablePatientPortal(authedFetch, patientId);
      setEnabled(res.enabled);
      setLastInviteSent(null);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't disable the portal — try again.");
    } finally {
      setBusy(false);
    }
  }

  function copyPin() {
    if (!pin) return;
    navigator.clipboard.writeText(pin).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const expiresLabel = pinExpiresAt ? new Date(pinExpiresAt).toLocaleString() : null;

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <KeyRoundIcon className="h-4 w-4 text-teal-600" /> Patient portal access
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        The patient logs in at <span className="font-mono">/user</span> with their phone number and the one-time login
        PIN below — then sets their own permanent PIN on first login.
      </p>

      {loading ?
      <p className="mt-3 text-sm text-ink-muted">Loading…</p> :

      <div className="mt-3 space-y-3">
          {portalId &&
        <div className="flex flex-wrap items-center gap-2">
              <code className="rounded-lg bg-sand-100 px-3 py-2 text-sm font-semibold text-ink">{portalId}</code>
              <span className="text-xs text-ink-muted">reference ID — not needed to log in</span>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${enabled ? "bg-success/10 text-success" : "bg-ink-muted/10 text-ink-muted"}`}>
                {enabled ? "Active" : "Disabled"}
              </span>
            </div>
        }

          {enabled && pin &&
        <div className="rounded-2xl border border-teal-600/20 bg-teal-600/5 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">One-time login PIN</p>
                  <p className="mt-1 font-mono text-3xl font-bold tracking-[0.3em] text-teal-700">{pin}</p>
                  <p className="mt-1 text-[11px] text-ink-muted">
                    Single-use, expires {expiresLabel ? `on ${expiresLabel}` : "soon"} — hand it to the patient if the invite never arrived.
                  </p>
                </div>
                <div className="flex flex-col gap-2">
                  <button
                    type="button"
                    onClick={copyPin}
                    className="rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700"
                  >
                    {copied ? "Copied" : "Copy PIN"}
                  </button>
                  <button
                    type="button"
                    onClick={handleGeneratePin}
                    disabled={busy}
                    className="flex items-center justify-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50"
                  >
                    <RefreshCwIcon className="h-3.5 w-3.5" /> {busy ? "…" : "New PIN"}
                  </button>
                </div>
              </div>
              <p className="mt-2 text-xs text-ink-muted">
                Patient set their own PIN: <span className={`font-semibold ${pinSet ? "text-success" : "text-warning"}`}>{pinSet ? "Yes" : "Not yet"}</span>
              </p>
            </div>
        }

          {lastInviteSent === true &&
        <div className="flex items-center gap-1.5 text-xs font-medium text-success">
              <CheckCircle2Icon className="h-3.5 w-3.5" /> Invite sent — the patient can log in with their phone number + PIN now.
            </div>
        }
          {lastInviteSent === false &&
        <div className="flex items-center gap-1.5 text-xs font-medium text-warning">
              <ShieldAlertIcon className="h-3.5 w-3.5" /> Portal is on, but the invite couldn't be delivered — read the PIN above to the patient over the phone.
            </div>
        }

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <div className="flex flex-wrap gap-2">
            {!enabled &&
          <button
            type="button"
            onClick={handleEnable}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2.5 text-xs font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50">
                <KeyRoundIcon className="h-3.5 w-3.5" /> {busy ? "…" : portalId ? "Re-enable portal" : "Enable portal"}
              </button>
          }
            {enabled &&
          <>
                <button
              type="button"
              onClick={handleResendInvite}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                  <SendIcon className="h-3.5 w-3.5" /> {busy ? "…" : "Resend invite"}
                </button>
                <button
              type="button"
              onClick={handleDisable}
              disabled={busy}
              className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2.5 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">
                  <PowerIcon className="h-3.5 w-3.5" /> {busy ? "…" : "Disable"}
                </button>
              </>
          }
          </div>
        </div>
      }
    </div>);

}