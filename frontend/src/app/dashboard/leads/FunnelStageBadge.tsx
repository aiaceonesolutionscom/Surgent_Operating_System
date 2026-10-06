import { useState } from "react";
import { ChevronDownIcon, CheckIcon, XIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { updatePatientStage } from "../../../api/entities";
import type { Patient } from "../patients/types";

const STAGE_OPTIONS: { value: Patient["lifecycleStage"]; label: string }[] = [
{ value: "inquiry", label: "Inquiry" },
{ value: "contacted", label: "Contacted" },
{ value: "consult_scheduled", label: "Consult scheduled" },
{ value: "consult_completed", label: "Consult completed" },
{ value: "treatment_planned", label: "Treatment planned" },
{ value: "patient", label: "Became a patient" },
{ value: "lost", label: "Lost" }];


const STAGE_CLASS: Record<Patient["lifecycleStage"], string> = {
  inquiry: "bg-sand-100 text-ink-soft",
  contacted: "bg-accent-500/10 text-accent-700",
  consult_scheduled: "bg-accent-500/10 text-accent-700",
  consult_completed: "bg-teal-600/10 text-teal-600",
  treatment_planned: "bg-teal-600/10 text-teal-600",
  patient: "bg-success/10 text-success",
  lost: "bg-danger/10 text-danger"
};

// Editable funnel-stage badge — lets Owner/Receptionist move a patient
// through the CRM pipeline (or mark them lost, with a reason) directly from
// their detail page, since that's the only place this endpoint is reachable
// from today.
export function FunnelStageBadge({
  patientId,
  stage,
  lostReason,
  onUpdated



}: {patientId: string;stage: Patient["lifecycleStage"];lostReason: string | null;onUpdated: (stage: Patient["lifecycleStage"], lostReason: string | null) => void;}) {
  const { authedFetch, role } = usePlan();
  const [editing, setEditing] = useState(false);
  const [pendingLostReason, setPendingLostReason] = useState("");
  const [choosingLostReason, setChoosingLostReason] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canManage = role === "owner" || role === "receptionist";
  const current = STAGE_OPTIONS.find((s) => s.value === stage) ?? STAGE_OPTIONS[0];

  async function applyStage(next: Patient["lifecycleStage"], reason: string | null) {
    if (!authedFetch) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePatientStage(authedFetch, patientId, next, reason);
      onUpdated(next, updated.lost_reason);
      setEditing(false);
      setChoosingLostReason(false);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't update stage — try again.");
    } finally {
      setSaving(false);
    }
  }

  function handlePick(next: Patient["lifecycleStage"]) {
    if (next === "lost") {
      setPendingLostReason("");
      setChoosingLostReason(true);
      return;
    }
    applyStage(next, null);
  }

  if (!canManage) {
    return (
      <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${STAGE_CLASS[stage]}`}>
        {current.label}
      </span>);

  }

  if (choosingLostReason) {
    return (
      <div className="flex items-center gap-1.5">
        <input
          autoFocus
          value={pendingLostReason}
          onChange={(e) => setPendingLostReason(e.target.value)}
          placeholder="Reason (optional)"
          className="w-40 rounded-lg border border-sand-200 px-2 py-1 text-xs outline-none focus:border-danger/40" />

        <button type="button" disabled={saving} onClick={() => applyStage("lost", pendingLostReason.trim() || null)} className="flex h-6 w-6 items-center justify-center rounded-lg bg-danger text-white disabled:opacity-50">
          <CheckIcon className="h-3 w-3" />
        </button>
        <button type="button" onClick={() => setChoosingLostReason(false)} className="flex h-6 w-6 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100">
          <XIcon className="h-3 w-3" />
        </button>
      </div>);

  }

  if (editing) {
    return (
      <div className="relative">
        <select
          autoFocus
          value={stage}
          disabled={saving}
          onChange={(e) => handlePick(e.target.value as Patient["lifecycleStage"])}
          onBlur={() => setEditing(false)}
          className="rounded-full border border-sand-200 bg-white px-2.5 py-1 text-xs font-semibold text-ink outline-none focus:border-teal-600/40">

          {STAGE_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>);

  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => setEditing(true)}
        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition-opacity hover:opacity-80 ${STAGE_CLASS[stage]}`}>

        {current.label} <ChevronDownIcon className="h-3 w-3" />
      </button>
      {stage === "lost" && lostReason && <span className="text-[11px] text-ink-muted">{lostReason}</span>}
      {error && <span className="text-[11px] font-medium text-danger">{error}</span>}
    </div>);

}
