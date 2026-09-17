import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, ClockIcon, CheckIcon, XCircleIcon, ScissorsIcon, PlusIcon, XIcon, PlayIcon, BadgeCheckIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { useSurgery } from "./useSurgeries";
import { DASHBOARD_ROUTES } from "../constants/routes";
import type { SurgeryResponse } from "../../../api/entities";

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-accent-500/10 text-accent-700",
  confirmed: "bg-teal-500/10 text-teal-700",
  in_progress: "bg-amber-500/15 text-amber-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-ink-muted/10 text-ink-muted"
};

const STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  confirmed: "Confirmed",
  in_progress: "In progress",
  completed: "Completed",
  cancelled: "Cancelled"
};

// The end-to-end path: booked at the front desk -> confirmed with patient +
// doctor -> doctor starts the case -> doctor completes it with the operative
// note. "Cancelled" (with a reason) can branch off from any pre-procedure step.
const FLOW = ["scheduled", "confirmed", "in_progress", "completed"] as const;

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: "long", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

export function SurgeryDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch, role } = usePlan();
  const { surgery, loading, error, update, updateClinical, confirm, start, complete, cancel } = useSurgery(authedFetch, id);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // Front-desk surface: Receptionist + Owner reschedule, confirm, cancel.
  const canSchedule = role === "owner" || role === "receptionist";
  // Clinical surface: Doctor + Owner tick the pre-op checklist, start, complete.
  const canManage = role === "owner" || role === "doctor";
  // Cancelling is open to all three practice roles.
  const canCancel = role === "owner" || role === "receptionist" || role === "doctor";

  async function toggleChecklistItem(idx: number) {
    if (!surgery) return;
    setBusy(true);
    setActionError(null);
    try {
      const next = surgery.pre_op_checklist.map((item, i) => (i === idx ? { ...item, checked: !item.checked } : item));
      await updateClinical({ pre_op_checklist: next });
    } catch (err: unknown) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn't update the checklist.");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm() {
    setBusy(true);
    setActionError(null);
    try {
      await confirm();
    } catch (err: unknown) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn't confirm this surgery.");
    } finally {
      setBusy(false);
    }
  }

  async function handleStart() {
    setBusy(true);
    setActionError(null);
    try {
      await start();
    } catch (err: unknown) {
      setActionError(err instanceof Error && err.message ? err.message : "Couldn't start this surgery.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel(reason: string) {
    setBusy(true);
    setActionError(null);
    try {
      await cancel(reason);
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

  const cancelled = surgery.status === "cancelled";
  const completed = surgery.status === "completed";

  return (
    <>
      <Link to={DASHBOARD_ROUTES.surgeries} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        <ArrowLeftIcon className="h-4 w-4" /> Back to Surgery
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <PageHeader title={surgery.procedure_name || "Surgery"} subtitle={`${surgery.patient_name || "Patient"} · ${surgery.doctor_name || "Surgeon"}${surgery.assistant_doctor_name ? ` + ${surgery.assistant_doctor_name}` : ""}`} />
        </div>
        <span className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold ${STATUS_STYLES[surgery.status]}`}>
          {STATUS_LABELS[surgery.status] || surgery.status}
        </span>
      </div>

      <StatusStepper status={surgery.status} cancelledReason={surgery.cancelled_reason} />

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
            <div className="flex items-center justify-between border-b border-sand-100 px-5 py-4">
              <p className="text-sm font-bold text-ink">Pre-op checklist</p>
              <span className="text-xs font-medium text-ink-muted">
                {surgery.pre_op_checklist.filter((x) => x.checked).length}/{surgery.pre_op_checklist.length} done
              </span>
            </div>
            {surgery.pre_op_checklist.length === 0 ?
            <p className="px-5 py-6 text-sm text-ink-muted">No checklist items.</p> :
            <div className="divide-y divide-sand-100">
                {surgery.pre_op_checklist.map((item, i) =>
              <button
                key={i}
                type="button"
                disabled={busy || completed || cancelled || !canManage}
                onClick={() => toggleChecklistItem(i)}
                title={canManage && !completed && !cancelled ? undefined : "Read-only"}
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

          {completed &&
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
          <div className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <p className="mb-3 text-sm font-bold text-ink">Actions</p>
            <div className="space-y-2">
              {/* Front desk: confirm a booked (scheduled) surgery — the step that
                  moves it into the Doctor's pre-op view. */}
              {canSchedule && surgery.status === "scheduled" &&
              <button
                type="button"
                disabled={busy}
                onClick={handleConfirm}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50">
                  <BadgeCheckIcon className="h-4 w-4" /> Confirm surgery
                </button>
              }

              {/* Doctor walks in: confirmed -> in_progress */}
              {canManage && surgery.status === "confirmed" &&
              <button
                type="button"
                disabled={busy}
                onClick={handleStart}
                className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-amber-600 disabled:opacity-50">
                  <PlayIcon className="h-4 w-4" /> Start surgery
                </button>
              }

              {/* Doctor finishes: in_progress -> completed with the operative note */}
              {canManage && surgery.status === "in_progress" &&
              <CompleteCard onComplete={complete} busy={busy} />
              }

              {!cancelled && !completed && canCancel &&
              <CancelCard onCancel={handleCancel} busy={busy} />
              }

              {completed &&
              <p className="rounded-xl bg-success/5 px-4 py-3 text-sm text-success">
                This surgery is complete. The operative note is saved on this record.
              </p>
              }

              {cancelled &&
              <p className="rounded-xl bg-ink-muted/5 px-4 py-3 text-sm text-ink-muted">
                {surgery.cancelled_reason ? `Cancelled: ${surgery.cancelled_reason}` : "Cancelled."}
              </p>
              }
            </div>

            {/* Reschedule is a front-desk action and only available while the case
                is still scheduled/confirmed — never once it's been started. */}
            {canSchedule && (surgery.status === "scheduled" || surgery.status === "confirmed") &&
            <RescheduleCard
              surgery={surgery}
              onReschedule={update}
              busy={busy}
            />
            }
          </div>

          {actionError && <p className="text-sm font-medium text-danger">{actionError}</p>}
        </div>
      </div>
    </>);

}

function StatusStepper({ status, cancelledReason }: { status: string; cancelledReason: string | null }) {
  const cancelled = status === "cancelled";
  const currentIndex = FLOW.indexOf(status as (typeof FLOW)[number]);
  const doneUpTo = cancelled ? -1 : currentIndex;

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center">
        {FLOW.map((step, i) => {
          const reached = i <= doneUpTo;
          const isCurrent = i === currentIndex;
          return (
            <React.Fragment key={step}>
              {i > 0 && <div className={`h-0.5 flex-1 rounded ${reached ? "bg-teal-600" : "bg-sand-200"}`} />}
              <div className="flex flex-col items-center gap-1">
                <span className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold ${cancelled ? "bg-sand-100 text-ink-muted" : reached ? "bg-teal-600 text-white" : "border-2 border-sand-200 text-ink-muted"}`}>
                  {cancelled ? <XIcon className="h-4 w-4" /> : reached ? <CheckIcon className="h-4 w-4" /> : i + 1}
                </span>
                <span className={`text-[11px] font-semibold ${isCurrent ? "text-ink" : "text-ink-muted"}`}>{STATUS_LABELS[step]}</span>
              </div>
            </React.Fragment>);
        })}
      </div>
      {cancelled &&
      <p className="mt-4 rounded-xl bg-ink-muted/5 px-4 py-3 text-sm text-ink-muted">
        This surgery was cancelled. {cancelledReason ? `Reason: ${cancelledReason}` : "No reason recorded."}
      </p>
      }
    </div>);

}

function CompleteCard({
  onComplete,
  busy
}: {
  onComplete: (data: { operative_note: string; implants_used: Array<{ type?: string; manufacturer?: string; lot_number?: string; size?: string }> }) => Promise<unknown>;
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
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
        <ScissorsIcon className="h-4 w-4" /> Complete surgery
      </button>);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-sand-200 p-4">
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
          disabled={saving || !note.trim() || busy}
          className="flex-1 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Mark completed"}
        </button>
      </div>
    </form>);

}

function CancelCard({
  onCancel,
  busy
}: {
  onCancel: (reason: string) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  if (!open) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => setOpen(true)}
        className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">
        <XCircleIcon className="h-4 w-4" /> Cancel surgery
      </button>);
  }

  return (
    <div className="space-y-2 rounded-xl border border-danger/30 bg-danger/5 p-4">
      <p className="text-sm font-bold text-danger">Cancel this surgery?</p>
      <input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason (optional)"
        className="w-full rounded-xl border border-danger/30 bg-white px-3.5 py-2 text-sm text-ink outline-none focus:border-danger/50" />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="flex-1 rounded-xl border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Keep
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onCancel(reason)}
          className="flex-1 rounded-xl bg-danger px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-danger/90 disabled:opacity-50">
          Cancel surgery
        </button>
      </div>
    </div>);

}

function RescheduleCard({
  surgery,
  onReschedule,
  busy
}: {
  surgery: SurgeryResponse;
  onReschedule: (data: { scheduled_date?: string | null; duration_estimate_minutes?: number | null; anesthesia_type?: string | null; facility_note?: string | null; assistant_doctor_id?: string | null }) => Promise<unknown>;
  busy: boolean;
}) {
  const initial = {
    date: "",
    time: "",
    duration: surgery.duration_estimate_minutes ? String(surgery.duration_estimate_minutes) : "",
    anesthesia: surgery.anesthesia_type || "",
    facility: surgery.facility_note || ""
  };
  const d = new Date(surgery.scheduled_date);
  initial.date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  initial.time = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;

  const [date, setDate] = useState(initial.date);
  const [time, setTime] = useState(initial.time);
  const [duration, setDuration] = useState(initial.duration);
  const [anesthesia, setAnesthesia] = useState(initial.anesthesia);
  const [facility, setFacility] = useState(initial.facility);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const [y, mo, dd] = date.split("-").map(Number);
    const [hh, mm] = time.split(":").map(Number);
    if (!y || !mo || !dd) return;
    setSaving(true);
    setError(null);
    try {
      await onReschedule({
        scheduled_date: new Date(y, mo - 1, dd, hh, mm).toISOString(),
        duration_estimate_minutes: duration ? Number(duration) : null,
        anesthesia_type: anesthesia.trim() || null,
        facility_note: facility.trim() || null
      });
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't reschedule.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-3 border-t border-sand-100 pt-4">
      <p className="text-xs font-bold uppercase tracking-wide text-ink-muted">Reschedule</p>
      <div className="grid grid-cols-2 gap-2">
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input type="number" min="15" value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="Duration (min)" className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        <input value={anesthesia} onChange={(e) => setAnesthesia(e.target.value)} placeholder="Anesthesia" className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
      </div>
      <input value={facility} onChange={(e) => setFacility(e.target.value)} placeholder="Facility / OT note" className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
      {error && <p className="text-sm font-medium text-danger">{error}</p>}
      <button
        type="submit"
        disabled={saving || busy}
        className="flex w-full items-center justify-center rounded-xl bg-teal-600/10 px-4 py-2 text-sm font-semibold text-teal-700 transition-colors hover:bg-teal-600/20 disabled:opacity-50">
        {saving ? "Saving…" : "Save new time"}
      </button>
    </form>);

}