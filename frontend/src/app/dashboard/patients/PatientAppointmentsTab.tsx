import React, { useEffect, useState } from "react";
import { CalendarIcon, ClockIcon, CalendarClockIcon, XCircleIcon, XIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import {
  listPatientAppointments,
  rescheduleAppointment,
  cancelAppointment,
  type AppointmentResponse
} from "../../../api/entities";
import { EmptyState } from "../components/EmptyState";

const STATUS_CLASS: Record<string, string> = {
  scheduled: "bg-accent-500/10 text-accent-700",
  checked_in: "bg-warning/10 text-warning",
  with_doctor: "bg-warning/10 text-warning",
  ready_for_checkout: "bg-warning/10 text-warning",
  completed: "bg-success/10 text-success",
  cancelled: "bg-ink-muted/10 text-ink-muted",
  no_show: "bg-danger/10 text-danger"
};

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}

function toLocalInputValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Doctor sees only their own schedule with this patient (listMyAppointments,
// server-scoped); Owner/Receptionist see every appointment this patient has
// at the clinic (listPracticeAppointments) — matches the same visibility
// split already established for the rest of the dashboard. Both scopes now
// filter by patient_id on the server so a large practice never ships its
// entire appointment table to a single-patient view.
export function PatientAppointmentsTab({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const [appointments, setAppointments] = useState<AppointmentResponse[] | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editing, setEditing] = useState<AppointmentResponse | null>(null);
  const [cancelling, setCancelling] = useState<AppointmentResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!authedFetch) {
      setAppointments([]);
      return;
    }
    const scope = role === "doctor" ? "me" : "practice";
    listPatientAppointments(authedFetch, patientId, scope)
      .then((data) => { if (!cancelled) setAppointments(data); })
      .catch(() => { if (!cancelled) setAppointments([]); });
    return () => { cancelled = true; };
  }, [authedFetch, role, patientId]);

  async function refresh() {
    if (!authedFetch) return;
    const scope = role === "doctor" ? "me" : "practice";
    try {
      setAppointments(await listPatientAppointments(authedFetch, patientId, scope));
    } catch {
      setAppointments([]);
    }
  }

  if (appointments === null) {
    return <p className="rounded-3xl border border-sand-200 bg-white p-8 text-center text-sm text-ink-muted">Loading…</p>;
  }
  if (appointments.length === 0) {
    return <EmptyState icon={CalendarIcon} title="No appointments" body="No appointments on file for this patient yet." />;
  }

  const sorted = [...appointments].sort((a, b) => +new Date(b.start_time) - +new Date(a.start_time));

  return (
    <>
      <div className="space-y-3">
        {sorted.map((a) => {
          const actionable = !["cancelled", "completed", "no_show"].includes(a.status) && +new Date(a.end_time) > Date.now();
          return (
            <div key={a.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-sand-200 bg-white p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)]">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-600/10 text-teal-600">
                  <ClockIcon className="h-5 w-5" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-ink">{a.appointment_type}</p>
                  <p className="text-xs text-ink-muted">{formatDateTime(a.start_time)}</p>
                  {a.notes && <p className="mt-0.5 text-xs text-ink-muted">{a.notes}</p>}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {actionable && (
                  <>
                    <button
                      type="button"
                      onClick={() => setEditing(a)}
                      disabled={busyId === a.id}
                      className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                      <CalendarClockIcon className="h-3.5 w-3.5" /> Reschedule
                    </button>
                    <button
                      type="button"
                      onClick={() => setCancelling(a)}
                      disabled={busyId === a.id}
                      className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">
                      <XCircleIcon className="h-3.5 w-3.5" /> Cancel
                    </button>
                  </>
                )}
                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${STATUS_CLASS[a.status] || "bg-ink-muted/10 text-ink-muted"}`}>
                  {a.status.replace(/_/g, " ")}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {editing &&
        <RescheduleModal
          appointment={editing}
          onClose={() => setEditing(null)}
          onSubmit={async (start, end) => {
            if (!authedFetch) return;
            setBusyId(editing.id);
            try {
              await rescheduleAppointment(authedFetch, editing.id, { start_time: start, end_time: end });
              setEditing(null);
              await refresh();
            } finally {
              setBusyId(null);
            }
          }} />
      }
      {cancelling &&
        <CancelModal
          appointment={cancelling}
          onClose={() => setCancelling(null)}
          onSubmit={async (reason) => {
            if (!authedFetch) return;
            setBusyId(cancelling.id);
            try {
              await cancelAppointment(authedFetch, cancelling.id, { reason: reason || null });
              setCancelling(null);
              await refresh();
            } finally {
              setBusyId(null);
            }
          }} />
      }
    </>
  );
}

function Modal({ title, subtitle, onClose, children }: { title: string; subtitle: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-ink">{title}</h3>
            <p className="mt-0.5 text-sm text-ink-muted">{subtitle}</p>
          </div>
          <button type="button" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100">
            <XIcon className="h-4 w-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function RescheduleModal({ appointment, onClose, onSubmit }: {
  appointment: AppointmentResponse;
  onClose: () => void;
  onSubmit: (start: string, end: string) => Promise<void>;
}) {
  const start = new Date(appointment.start_time);
  const end = new Date(appointment.end_time);
  const [startTime, setStartTime] = useState(toLocalInputValue(start));
  const [endTime, setEndTime] = useState(toLocalInputValue(end));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const valid = Boolean(startTime && endTime) && +new Date(endTime) > +new Date(startTime) && !saving;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await onSubmit(new Date(startTime).toISOString(), new Date(endTime).toISOString());
    } catch {
      setError("Couldn't reschedule this appointment — check the times and try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Reschedule appointment" subtitle={`${appointment.appointment_type} · ${formatDateTime(appointment.start_time)}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Start *</span>
            <input
              required
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">End *</span>
            <input
              required
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
          </label>
        </div>
        {error && <p className="text-sm font-medium text-danger">{error}</p>}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!valid}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
            {saving ? "Saving…" : "Reschedule"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function CancelModal({ appointment, onClose, onSubmit }: {
  appointment: AppointmentResponse;
  onClose: () => void;
  onSubmit: (reason: string | null) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSubmit(reason.trim() || null);
    } catch {
      setError("Couldn't cancel this appointment — try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Cancel appointment" subtitle={`${appointment.appointment_type} · ${formatDateTime(appointment.start_time)}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Reason (optional)</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder="Why is this being cancelled?"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <p className="text-sm text-ink-muted">The patient will be notified of this cancellation automatically.</p>
        {error && <p className="text-sm font-medium text-danger">{error}</p>}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
            Keep
          </button>
          <button
            type="submit"
            disabled={saving}
            className="rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-40">
            {saving ? "Cancelling…" : "Cancel appointment"}
          </button>
        </div>
      </form>
    </Modal>
  );
}