import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, ClockIcon, CheckIcon, XCircleIcon, ScissorsIcon, PlusIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { useSurgery } from "./useSurgeries";
import { DASHBOARD_ROUTES } from "../constants/routes";

const STATUS_STYLES: Record<string, string> = {
  planned: "bg-accent-500/10 text-accent-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-ink-muted/10 text-ink-muted"
};

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export function SurgeryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch, role } = usePlan();
  const { surgery, loading, error, update, complete, cancel } = useSurgery(authedFetch, id);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const canManage = role === "owner" || role === "doctor";

  async function toggleChecklistItem(idx: number) {
    if (!surgery) return;
    setBusy(true);
    setActionError(null);
    try {
      const next = surgery.pre_op_checklist.map((item, i) => (i === idx ? { ...item, checked: !item.checked } : item));
      await update({ pre_op_checklist: next });
    } catch (err: unknown) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn't update the checklist.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    setBusy(true);
    setActionError(null);
    try {
      await cancel();
    } catch (err: unknown) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn't cancel this surgery.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-ink-muted">Loading…</p>;
  if (error || !surgery) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center">
        <p className="text-sm font-medium text-danger">{error || "Surgery not found."}</p>
      </div>);
  }

  return (
    <>
      <Link to={DASHBOARD_ROUTES.surgeries} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        <ArrowLeftIcon className="h-4 w-4" /> Back to Surgery
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <PageHeader title={surgery.procedure_name || "Surgery"} subtitle={`${surgery.patient_name || "Patient"} · ${surgery.doctor_name || "Surgeon"}${surgery.assistant_doctor_name ? ` + ${surgery.assistant_doctor_name}` : ""}`} />
        </div>
        <span className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold capitalize ${STATUS_STYLES[surgery.status]}`}>
          {surgery.status}
        </span>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Scheduled</p>
                <p className="mt-1 flex items-center gap-1.5 text-sm text-ink"><ClockIcon className="h-3.5 w-3.5 text-ink-muted" /> {formatDateTime(surgery.scheduled_date)}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Estimated duration</p>
                <p className="mt-1 text-sm text-ink">{surgery.duration_estimate_minutes ? `${surgery.duration_estimate_minutes} minutes` : "Not specified"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Anesthesia</p>
                <p className="mt-1 text-sm text-ink">{surgery.anesthesia_type || "Not specified"}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Facility / OT</p>
                <p className="mt-1 text-sm text-ink">{surgery.facility_note || "Not specified"}</p>
              </div>
            </div>
          </div>

          <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <div className="border-b border-sand-100 px-5 py-4">
              <p className="text-sm font-bold text-ink">Pre-op checklist</p>
            </div>
            {surgery.pre_op_checklist.length === 0 ?
            <p className="px-5 py-6 text-sm text-ink-muted">No checklist items.</p> :
            <div className="divide-y divide-sand-100">
                {surgery.pre_op_checklist.map((item, i) =>
              <button
                key={i}
                type="button"
                disabled={busy || surgery.status !== "planned" || !canManage}
                onClick={() => toggleChecklistItem(i)}
                title={canManage ? undefined : "Read-only"}
                className="flex w-full items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-sand-50 disabled:cursor-default disabled:hover:bg-transparent">
                    <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border ${item.checked ? "border-teal-600 bg-teal-600 text-white" : "border-sand-300"}`}>
                      {item.checked && <CheckIcon className="h-3.5 w-3.5" />}
                    </span>
                    <span className={`text-sm ${item.checked ? "text-ink-muted line-through" : "text-ink"}`}>{item.item}</span>
                  </button>
              )}
              </div>
            }
          </div>

          {surgery.status === "completed" &&
          <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
              <div className="border-b border-sand-100 px-5 py-4">
                <p className="text-sm font-bold text-ink">Operative note</p>
              </div>
              <p className="px-5 py-4 text-sm leading-relaxed text-ink-soft whitespace-pre-wrap">{surgery.operative_note}</p>
              {surgery.implants_used.length > 0 &&
            <div className="border-t border-sand-100 px-5 py-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Implants used</p>
                  <div className="space-y-1.5">
                    {surgery.implants_used.map((im, i) =>
                <p key={i} className="text-sm text-ink-soft">
                        {im.type} — {im.manufacturer} {im.lot_number && `· Lot ${im.lot_number}`} {im.size && `· ${im.size}`}
                      </p>
                )}
                  </div>
                </div>
            }
            </div>
          }
        </div>

        <div className="space-y-4">
          {surgery.status === "planned" && canManage &&
          <CompleteCard onComplete={complete} onCancel={handleCancel} busy={busy} />
          }
          {actionError && <p className="text-sm font-medium text-danger">{actionError}</p>}
        </div>
      </div>
    </>);

}

function CompleteCard({
  onComplete,
  onCancel,
  busy
}: {
  onComplete: (data: { operative_note: string; implants_used: Array<{ type?: string; manufacturer?: string; lot_number?: string; size?: string }> }) => Promise<unknown>;
  onCancel: () => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [implants, setImplants] = useState<Array<{ type: string; manufacturer: string; lot_number: string; size: string }>>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addImplant() {
    setImplants((prev) => [...prev, { type: "", manufacturer: "", lot_number: "", size: "" }]);
  }

  function updateImplant(i: number, field: string, value: string) {
    setImplants((prev) => prev.map((im, idx) => (idx === i ? { ...im, [field]: value } : im)));
  }

  function removeImplant(i: number) {
    setImplants((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!note.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onComplete({ operative_note: note.trim(), implants_used: implants });
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't complete this surgery.");
      setSaving(false);
    }
  }

  if (!open) {
    return (
      <div className="space-y-2 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
          <ScissorsIcon className="h-4 w-4" /> Complete surgery
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onCancel}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">
          <XCircleIcon className="h-4 w-4" /> Cancel surgery
        </button>
      </div>);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <p className="text-sm font-bold text-ink">Complete surgery</p>
      <label className="block">
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Operative note *</span>
        <textarea
          required
          rows={4}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Procedure performed, findings, any complications…"
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
      </label>

      <div>
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Implants used</span>
        <div className="space-y-2">
          {implants.map((im, i) =>
          <div key={i} className="grid grid-cols-2 gap-1.5 rounded-xl border border-sand-200 p-2.5">
              <input value={im.type} onChange={(e) => updateImplant(i, "type", e.target.value)} placeholder="Type" className="rounded-lg border border-sand-200 px-2 py-1 text-xs" />
              <input value={im.manufacturer} onChange={(e) => updateImplant(i, "manufacturer", e.target.value)} placeholder="Manufacturer" className="rounded-lg border border-sand-200 px-2 py-1 text-xs" />
              <input value={im.lot_number} onChange={(e) => updateImplant(i, "lot_number", e.target.value)} placeholder="Lot #" className="rounded-lg border border-sand-200 px-2 py-1 text-xs" />
              <div className="flex items-center gap-1">
                <input value={im.size} onChange={(e) => updateImplant(i, "size", e.target.value)} placeholder="Size" className="min-w-0 flex-1 rounded-lg border border-sand-200 px-2 py-1 text-xs" />
                <button type="button" onClick={() => removeImplant(i)} className="text-ink-muted hover:text-danger"><XIcon className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          )}
        </div>
        <button type="button" onClick={addImplant} className="mt-2 flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
          <PlusIcon className="h-3 w-3" /> Add implant
        </button>
      </div>

      {error && <p className="text-sm font-medium text-danger">{error}</p>}

      <div className="flex items-center gap-2">
        <button type="button" onClick={() => setOpen(false)} className="flex-1 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !note.trim()}
          className="flex-1 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Mark completed"}
        </button>
      </div>
    </form>);

}
