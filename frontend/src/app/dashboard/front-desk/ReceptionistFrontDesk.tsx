import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarIcon, ClockIcon, CheckIcon, PlusIcon, StethoscopeIcon, ReceiptIcon, XCircleIcon, ClipboardListIcon, UsersIcon, CalendarDaysIcon, ScissorsIcon } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import type { FrontDeskAppointment } from "./useFrontDesk";
import { AttendanceCalendar } from "../attendance/AttendanceCalendar";
import { useSurgeries } from "../surgery/useSurgeries";
import { DASHBOARD_ROUTES } from "../constants/routes";
import {
  listWaitlist,
  addToWaitlist,
  fulfillWaitlistEntry,
  cancelWaitlistEntry,
  type WaitlistEntryResponse
} from "../../../api/entities";

const STATUS_CLASS: Record<string, string> = {
  scheduled: "bg-accent-500/10 text-accent-700",
  confirmed: "bg-success/10 text-success",
  checked_in: "bg-teal-600/10 text-teal-600",
  with_doctor: "bg-warning/10 text-warning",
  ready_for_checkout: "bg-[#8B5CF6]/10 text-[#8B5CF6]",
  cancelled: "bg-danger/10 text-danger",
  completed: "bg-ink-muted/10 text-ink-muted",
  no_show: "bg-warning/10 text-warning"
};

function isToday(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

function isCheckedIn(a: FrontDeskAppointment): a is FrontDeskAppointment & { checked_in_at: string } {
  return a.status === "checked_in" && Boolean((a as { checked_in_at?: string }).checked_in_at);
}

function waitTime(checkedInAt: string) {
  const mins = Math.round((Date.now() - new Date(checkedInAt).getTime()) / 60000);
  if (mins < 1) return "just now";
  return `${mins}m waiting`;
}

type Tab = "queue" | "waiting" | "calendar";

interface Props {
  appointments: FrontDeskAppointment[];
  loading: boolean;
  checkIn: (id: string) => Promise<void>;
  startDoctor: (id: string) => Promise<void>;
  readyForCheckout: (id: string) => Promise<void>;
  complete: (id: string) => Promise<void>;
  noShow: (id: string) => Promise<void>;
}

// The Receptionist's actual workspace — one page, three tabs over the same
// real appointment data, instead of "Front Desk" and "Waiting Room" as two
// separate sidebar destinations that were really just two filtered views of
// the same list. Today's Queue = today's full schedule with status actions
// (what used to be the whole page). Waiting Room = who's physically
// checked in right now (what used to be its own page). Calendar = what's
// actually coming up, beyond just today — a real gap neither old page
// covered.
export function ReceptionistFrontDesk({ appointments, loading, checkIn, startDoctor, readyForCheckout, complete, noShow }: Props) {
  const [tab, setTab] = useState<Tab>("queue");
  const [busyId, setBusyId] = useState<string | null>(null);

  const today = appointments
    .filter((a) => isToday(a.start_time))
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));

  const waiting = appointments
    .filter(isCheckedIn)
    .sort((a, b) => +new Date(a.checked_in_at) - +new Date(b.checked_in_at));

  async function run(id: string, action: (id: string) => Promise<void>) {
    setBusyId(id);
    try {
      await action(id);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex rounded-xl border border-sand-200 bg-white p-1">
          <TabButton active={tab === "queue"} onClick={() => setTab("queue")} icon={ClipboardListIcon} label="Today's Queue" />
          <TabButton active={tab === "waiting"} onClick={() => setTab("waiting")} icon={UsersIcon} label={`Waiting Room${waiting.length ? ` (${waiting.length})` : ""}`} />
          <TabButton active={tab === "calendar"} onClick={() => setTab("calendar")} icon={CalendarDaysIcon} label="Calendar" />
        </div>
        <Link
          to={DASHBOARD_ROUTES.bookAppointment}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
          <PlusIcon className="h-4 w-4" /> Book appointment
        </Link>
      </div>

      {loading ? (
        <p className="text-sm text-ink-muted">Loading…</p>
      ) : tab === "queue" ? (
        <TodaysQueueTab appointments={today} busyId={busyId} run={run} checkIn={checkIn} startDoctor={startDoctor} readyForCheckout={readyForCheckout} complete={complete} noShow={noShow} />
      ) : tab === "waiting" ? (
        <WaitingRoomTab waiting={waiting} />
      ) : (
        <CalendarTab appointments={appointments} />
      )}

      <div className="mt-6">
        <UpcomingSurgeriesCard />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <WaitlistSection />
        <div>
          <p className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">My attendance</p>
          <AttendanceCalendar />
        </div>
      </div>
    </>
  );
}

function TabButton({ active, onClick, icon: Icon, label }: { active: boolean; onClick: () => void; icon: React.ComponentType<{ className?: string }>; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors ${
      active ? "bg-teal-600 text-white" : "text-ink-soft hover:bg-sand-100"}`}>
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function TodaysQueueTab({
  appointments, busyId, run, checkIn, startDoctor, readyForCheckout, complete, noShow
}: {
  appointments: FrontDeskAppointment[];
  busyId: string | null;
  run: (id: string, action: (id: string) => Promise<void>) => Promise<void>;
  checkIn: (id: string) => Promise<void>;
  startDoctor: (id: string) => Promise<void>;
  readyForCheckout: (id: string) => Promise<void>;
  complete: (id: string) => Promise<void>;
  noShow: (id: string) => Promise<void>;
}) {
  if (appointments.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState icon={CalendarIcon} title="Nothing on today's schedule" body="Appointments booked for today will appear here." />
      </div>
    );
  }
  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="divide-y divide-sand-100">
        {appointments.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sand-200 text-sm font-bold text-ink-soft">
              {a.patientInitial}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{a.patientName}</p>
              <p className="flex items-center gap-1 text-xs text-ink-muted">
                <ClockIcon className="h-3 w-3" />
                {new Date(a.start_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                {" · "}{a.appointment_type}
                {a.doctorName && <> · {a.doctorName}</>}
              </p>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[a.status] || "bg-sand-100 text-ink-soft"}`}>
              {a.status.replace(/_/g, " ")}
            </span>

            <Link
              to={`${DASHBOARD_ROUTES.surgeryNew()}?appointment_id=${a.id}`}
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
              <ScissorsIcon className="h-3.5 w-3.5" /> Book surgery
            </Link>

            <div className="flex shrink-0 items-center gap-1.5">
              {(a.status === "scheduled" || a.status === "confirmed") && (
                <>
                  <button
                    type="button"
                    onClick={() => run(a.id, checkIn)}
                    disabled={busyId === a.id}
                    className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                    <CheckIcon className="h-3.5 w-3.5" /> {busyId === a.id ? "…" : "Check in"}
                  </button>
                  <button
                    type="button"
                    onClick={() => run(a.id, noShow)}
                    disabled={busyId === a.id}
                    className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-warning/40 hover:text-warning disabled:opacity-50">
                    <XCircleIcon className="h-3.5 w-3.5" /> No-show
                  </button>
                </>
              )}
              {a.status === "checked_in" && (
                <button
                  type="button"
                  onClick={() => run(a.id, startDoctor)}
                  disabled={busyId === a.id}
                  className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                  <StethoscopeIcon className="h-3.5 w-3.5" /> {busyId === a.id ? "…" : "With doctor"}
                </button>
              )}
              {a.status === "with_doctor" && (
                <button
                  type="button"
                  onClick={() => run(a.id, readyForCheckout)}
                  disabled={busyId === a.id}
                  className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                  <ReceiptIcon className="h-3.5 w-3.5" /> {busyId === a.id ? "…" : "Ready for checkout"}
                </button>
              )}
              {a.status === "ready_for_checkout" && (
                <button
                  type="button"
                  onClick={() => run(a.id, complete)}
                  disabled={busyId === a.id}
                  className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50">
                  <CheckIcon className="h-3.5 w-3.5" /> {busyId === a.id ? "…" : "Complete"}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function WaitingRoomTab({ waiting }: { waiting: (FrontDeskAppointment & { checked_in_at: string })[] }) {
  if (waiting.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState icon={UsersIcon} title="Waiting room is empty" body="Patients checked in from Today's Queue will show up here." />
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {waiting.map((a) => (
        <div key={a.id} className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-sm font-bold text-teal-600">
              {a.patientInitial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">{a.patientName}</p>
              <p className="truncate text-xs text-ink-muted">{a.appointment_type}{a.doctorName && ` · ${a.doctorName}`}</p>
            </div>
          </div>
          <p className="mt-3 text-xs font-semibold text-teal-600">{waitTime(a.checked_in_at)}</p>
        </div>
      ))}
    </div>
  );
}

function CalendarTab({ appointments }: { appointments: FrontDeskAppointment[] }) {
  // Real "what's coming up" — grouped by date, next 7 days including today.
  // Not a month-grid widget (that's a bigger feature on its own); this is
  // the same real appointment data Today's Queue uses, just not cut off at
  // today, which neither old page showed.
  const now = new Date();
  const horizon = new Date(now);
  horizon.setDate(horizon.getDate() + 7);
  horizon.setHours(23, 59, 59, 999);

  const upcoming = appointments
    .filter((a) => {
      const d = new Date(a.start_time);
      return d >= new Date(now.getFullYear(), now.getMonth(), now.getDate()) && d <= horizon && a.status !== "cancelled";
    })
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));

  if (upcoming.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState icon={CalendarDaysIcon} title="Nothing scheduled this week" body="Appointments booked for the next 7 days will appear here, grouped by day." />
      </div>
    );
  }

  const groups = new Map<string, FrontDeskAppointment[]>();
  for (const a of upcoming) {
    const key = new Date(a.start_time).toDateString();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(a);
  }

  return (
    <div className="space-y-5">
      {Array.from(groups.entries()).map(([dateKey, items]) => (
        <div key={dateKey} className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="border-b border-sand-100 px-5 py-3">
            <p className="text-sm font-bold text-ink">
              {isToday(items[0].start_time) ? "Today — " : ""}
              {new Date(dateKey).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}
            </p>
          </div>
          <div className="divide-y divide-sand-100">
            {items.map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <span className="w-16 shrink-0 text-xs font-semibold text-ink-muted">
                  {new Date(a.start_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
                </span>
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sand-200 text-xs font-bold text-ink-soft">
                  {a.patientInitial}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{a.patientName}</p>
                  <p className="truncate text-xs text-ink-muted">{a.appointment_type}{a.doctorName && ` · ${a.doctorName}`}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[a.status] || "bg-sand-100 text-ink-soft"}`}>
                  {a.status.replace(/_/g, " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function WaitlistSection() {
  const { authedFetch } = usePlan();
  const [entries, setEntries] = useState<WaitlistEntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await listWaitlist(authedFetch);
      setEntries(data);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch || !name.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await addToWaitlist(authedFetch, { patient_name: name.trim(), phone: phone.trim() || null, notes: notes.trim() || null });
      setName("");
      setPhone("");
      setNotes("");
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't add to the waitlist — try again.");
    } finally {
      setAdding(false);
    }
  }

  async function handleFulfill(id: string) {
    if (!authedFetch) return;
    setBusyId(id);
    try {
      await fulfillWaitlistEntry(authedFetch, id);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function handleCancel(id: string) {
    if (!authedFetch) return;
    setBusyId(id);
    try {
      await cancelWaitlistEntry(authedFetch, id);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2.5 border-b border-sand-100 px-5 py-4">
        <ClipboardListIcon className="h-4 w-4 text-ink-muted" />
        <p className="text-sm font-bold text-ink">Waitlist</p>
      </div>

      <form onSubmit={submit} className="flex flex-wrap items-center gap-2 border-b border-sand-100 px-5 py-4">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Name"
          className="min-w-0 flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="Phone (optional)"
          className="min-w-0 flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="What are they waiting for?"
          className="min-w-0 flex-[2] rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        <button
          type="submit"
          disabled={adding || !name.trim()}
          className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          <PlusIcon className="h-3.5 w-3.5" /> Add
        </button>
      </form>
      {error && <p className="px-5 pt-3 text-sm font-medium text-danger">{error}</p>}

      {loading ? (
        <p className="px-5 py-6 text-sm text-ink-muted">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="px-5 py-6 text-sm text-ink-muted">No one's waiting for a slot right now.</p>
      ) : (
        <div className="divide-y divide-sand-100">
          {entries.map((e) => (
            <div key={e.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{e.patient_name}</p>
                <p className="truncate text-xs text-ink-muted">
                  {[e.phone, e.doctor_name, e.notes].filter(Boolean).join(" · ") || "No details"}
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleFulfill(e.id)}
                disabled={busyId === e.id}
                className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
                <CheckIcon className="h-3.5 w-3.5" /> Booked
              </button>
              <button
                type="button"
                onClick={() => handleCancel(e.id)}
                disabled={busyId === e.id}
                className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger disabled:opacity-50">
                <XCircleIcon className="h-3.5 w-3.5" /> Remove
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function UpcomingSurgeriesCard() {
  const { authedFetch } = usePlan();
  const { surgeries, loading } = useSurgeries(authedFetch);

  const now = new Date();
  const upcoming = surgeries
    .filter((s) => s.status === "planned" && new Date(s.scheduled_date).getTime() >= now.getTime())
    .sort((a, b) => +new Date(a.scheduled_date) - +new Date(b.scheduled_date))
    .slice(0, 6);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-100 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <ScissorsIcon className="h-4 w-4 text-teal-600" /> Upcoming surgeries
        </p>
        <Link to={DASHBOARD_ROUTES.surgeries} className="text-xs font-semibold text-teal-600 hover:underline">
          View all
        </Link>
      </div>
      {loading ?
      <p className="px-5 py-6 text-sm text-ink-muted">Loading…</p> :
      upcoming.length === 0 ?
      <p className="px-5 py-6 text-sm text-ink-muted">No planned surgeries coming up.</p> :
      <div className="divide-y divide-sand-100">
          {upcoming.map((s) =>
        <Link
          key={s.id}
          to={DASHBOARD_ROUTES.surgeryDetail(s.id)}
          className="flex flex-wrap items-center gap-3 px-5 py-3.5 transition-colors hover:bg-sand-50">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-teal-600">
              <ScissorsIcon className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{s.procedure_name || "Surgery"} — {s.patient_name || "Patient"}</p>
              <p className="flex items-center gap-1 truncate text-xs text-ink-muted">
                <ClockIcon className="h-3 w-3" /> {new Date(s.scheduled_date).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                {" · "}{s.doctor_name || "Doctor"}
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11px] font-semibold capitalize text-accent-700">{s.status}</span>
          </Link>
      )}
        </div>
      }
    </div>
  );
}
