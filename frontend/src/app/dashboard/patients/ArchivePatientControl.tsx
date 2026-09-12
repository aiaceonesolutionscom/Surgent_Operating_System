import React, { useState } from "react";
import { ArchiveIcon, ArchiveRestoreIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { archivePatient, restorePatient } from "../../../api/entities";

// Owner + Receptionist (see patients_router.py's require_role(OWNER,
// RECEPTIONIST) on both endpoints) — there is deliberately no hard-delete
// for patients. Archiving hides the record from the default list, disables
// portal login, and blocks new appointments; nothing here destroys
// medical/financial data.
export function ArchivePatientControl({
  patientId,
  isArchived,
  onChanged
}: {
  patientId: string;
  isArchived: boolean;
  onChanged: (archived: boolean) => void;
}) {
  const { authedFetch } = usePlan();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleArchive() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await archivePatient(authedFetch, patientId);
      onChanged(true);
      setConfirming(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't archive this patient.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRestore() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await restorePatient(authedFetch, patientId);
      onChanged(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't restore this patient.");
    } finally {
      setBusy(false);
    }
  }

  if (isArchived) {
    return (
      <button
        type="button"
        onClick={handleRestore}
        disabled={busy}
        className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
        <ArchiveRestoreIcon className="h-3.5 w-3.5" /> {busy ? "Restoring…" : "Restore patient"}
      </button>
    );
  }

  if (confirming) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/[0.04] px-3 py-1.5">
        <span className="text-xs text-ink-soft">Archive this patient?</span>
        <button type="button" onClick={handleArchive} disabled={busy} className="rounded-lg bg-danger px-2.5 py-1 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50">
          {busy ? "…" : "Confirm"}
        </button>
        <button type="button" onClick={() => setConfirming(false)} className="text-xs font-medium text-ink-muted hover:text-ink">Cancel</button>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => setConfirming(true)}
      className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger">
      <ArchiveIcon className="h-3.5 w-3.5" /> Archive patient
    </button>
  );
}
