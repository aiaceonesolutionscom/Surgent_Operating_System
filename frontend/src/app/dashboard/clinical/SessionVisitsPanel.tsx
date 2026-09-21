import { useState } from "react";
import {
  CalendarPlusIcon, CheckIcon, PlayIcon, XIcon, ClipboardCheckIcon, CheckCircle2Icon
} from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useDoctors } from "../doctors/useDoctors";
import {
  scheduleSession, confirmSession, startSession, completeSession, cancelSession, updateSessionChecklist,
  type SessionVisitResponse, type TreatmentPlanItemResponse
} from "../../../api/entities";

const STATUS_CLASS: Record<string, string> = {
  planned: "bg-sand-100 text-ink-soft",
  scheduled: "bg-accent-500/10 text-accent-700",
  confirmed: "bg-[#7C3AED]/10 text-[#7C3AED]",
  in_progress: "bg-warning/10 text-warning",
  completed: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger",
  no_show: "bg-danger/10 text-danger"
};

function formatDateTime(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

// Session-by-session management for a multi-visit TreatmentPlanItem
// (sessions_total > 1) — front desk schedules each visit, the doctor works
// through its checklist and completes it, generalizing Surgery's own
// pre-op-checklist + status-machine pattern to every procedure. Only shown
// for items that actually have more than one session; a single-visit item
// keeps TreatmentPlanPage's existing "mark completed" / "schedule surgery"
// behavior untouched.
export function SessionVisitsPanel({
  item, onChanged
}: {
  item: TreatmentPlanItemResponse; onChanged: () => Promise<void> | void;
}) {
  const { role } = usePlan();
  const canSchedule = role === "owner" || role === "receptionist";
  const canDoClinical = role === "owner" || role === "doctor";
  const sessions = [...item.session_visits].sort((a, b) => a.session_index - b.session_index);
  const completedCount = sessions.filter((s) => s.status === "completed").length;

  return (
    <div className="mt-2 rounded-2xl border border-sand-200 bg-sand-50/40 p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {completedCount} of {item.sessions_total} sessions completed
      </p>
      <div className="space-y-2.5">
        {sessions.map((session) =>
        <SessionRow
          key={session.id}
          session={session}
          canSchedule={canSchedule}
          canDoClinical={canDoClinical}
          onChanged={onChanged} />

        )}
      </div>
    </div>);

}

function SessionRow({
  session, canSchedule, canDoClinical, onChanged
}: {
  session: SessionVisitResponse; canSchedule: boolean; canDoClinical: boolean; onChanged: () => Promise<void> | void;
}) {
  const { authedFetch } = usePlan();
  const { doctors } = useDoctors(authedFetch);
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [doctorId, setDoctorId] = useState(session.doctor_id || doctors[0]?.id || "");
  const [startTime, setStartTime] = useState("");
  const [checklist, setChecklist] = useState(session.checklist);
  const [sessionNote, setSessionNote] = useState(session.session_note || "");

  async function run(fn: () => Promise<unknown>) {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function doSchedule() {
    if (!authedFetch || !doctorId || !startTime) return;
    await run(() => scheduleSession(authedFetch, session.id, { doctor_id: doctorId, start_time: new Date(startTime).toISOString() }));
    setExpanded(false);
  }

  async function doConfirm() {
    if (!authedFetch) return;
    await run(() => confirmSession(authedFetch, session.id));
  }

  async function doStart() {
    if (!authedFetch) return;
    await run(() => startSession(authedFetch, session.id));
  }

  async function saveChecklist() {
    if (!authedFetch) return;
    await run(() => updateSessionChecklist(authedFetch, session.id, checklist));
  }

  async function doComplete() {
    if (!authedFetch) return;
    await run(() => completeSession(authedFetch, session.id, { session_note: sessionNote.trim() || null, products_used: [] }));
    setExpanded(false);
  }

  async function doCancel() {
    if (!authedFetch) return;
    await run(() => cancelSession(authedFetch, session.id, "Cancelled by staff"));
  }

  const isTerminal = session.status === "completed" || session.status === "cancelled" || session.status === "no_show";

  return (
    <div className="rounded-xl border border-sand-200 bg-white">
      <div className="flex items-center justify-between gap-3 px-3.5 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">Session {session.session_index}</p>
          <p className="text-xs text-ink-muted">
            {session.scheduled_date ? formatDateTime(session.scheduled_date) : "Not scheduled yet"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[session.status]}`}>
            {session.status.replace("_", " ")}
          </span>
          {!isTerminal &&
          <button type="button" onClick={() => setExpanded((v) => !v)} className="rounded-lg border border-sand-200 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600">
              {expanded ? "Close" : "Manage"}
            </button>
          }
        </div>
      </div>

      {expanded && !isTerminal &&
      <div className="border-t border-sand-100 px-3.5 py-3">
          {error && <p className="mb-2 text-xs font-medium text-danger">{error}</p>}

          {canSchedule && (session.status === "planned" || session.status === "scheduled") &&
        <div className="mb-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <select value={doctorId} onChange={(e) => setDoctorId(e.target.value)} className="rounded-lg border border-sand-200 px-3 py-2 text-xs text-ink outline-none focus:border-teal-600/40">
                {doctors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <input type="datetime-local" value={startTime} onChange={(e) => setStartTime(e.target.value)} className="rounded-lg border border-sand-200 px-3 py-2 text-xs text-ink outline-none focus:border-teal-600/40" />
              <button type="button" onClick={doSchedule} disabled={busy || !doctorId || !startTime} className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-2 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-40">
                <CalendarPlusIcon className="h-3.5 w-3.5" /> Book
              </button>
            </div>
        }

          {canSchedule && session.status === "scheduled" &&
        <button type="button" onClick={doConfirm} disabled={busy} className="mb-3 flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
              <CheckIcon className="h-3.5 w-3.5" /> Confirm
            </button>
        }

          {canDoClinical && (session.status === "confirmed" || session.status === "scheduled") &&
        <button type="button" onClick={doStart} disabled={busy} className="mb-3 flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
              <PlayIcon className="h-3.5 w-3.5" /> Start
            </button>
        }

          {canDoClinical && checklist.length > 0 &&
        <div className="mb-3">
              <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-ink"><ClipboardCheckIcon className="h-3.5 w-3.5" /> Pre-visit checklist</p>
              <div className="space-y-1.5">
                {checklist.map((c, i) =>
            <label key={i} className="flex items-center gap-2 text-xs text-ink-soft">
                    <input
                type="checkbox"
                checked={c.checked}
                onChange={(e) => {
                  const next = [...checklist];
                  next[i] = { ...c, checked: e.target.checked };
                  setChecklist(next);
                }}
                className="h-3.5 w-3.5 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
                    {c.item}
                  </label>
            )}
              </div>
              <button type="button" onClick={saveChecklist} disabled={busy} className="mt-2 rounded-lg border border-sand-200 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                Save checklist
              </button>
            </div>
        }

          {canDoClinical && session.status === "in_progress" &&
        <div className="mb-3">
              <textarea
            value={sessionNote}
            onChange={(e) => setSessionNote(e.target.value)}
            rows={2}
            placeholder="Session note (what was done, how it went)"
            className="w-full rounded-lg border border-sand-200 px-3 py-2 text-xs text-ink outline-none focus:border-teal-600/40" />
              <button type="button" onClick={doComplete} disabled={busy} className="mt-2 flex items-center gap-1.5 rounded-lg bg-success px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50">
                <CheckCircle2Icon className="h-3.5 w-3.5" /> Complete session
              </button>
            </div>
        }

          <button type="button" onClick={doCancel} disabled={busy} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[11px] font-semibold text-ink-muted hover:text-danger disabled:opacity-50">
            <XIcon className="h-3 w-3" /> Cancel this session
          </button>
        </div>
      }
    </div>);

}
