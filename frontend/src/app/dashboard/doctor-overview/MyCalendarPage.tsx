import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon, FileTextIcon, PlusIcon, CalendarClockIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { listMyAppointments, listMyTimeBlocks, deleteTimeBlock, type AppointmentResponse, type DoctorTimeBlockResponse } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { TimeBlockForm } from "./TimeBlockForm";

const RECENT_DAYS = 7;
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

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

// Dot color on the month grid — mappable to a solid bg, unlike STATUS_CLASS.
const DOT_CLASS: Record<string, string> = {
  scheduled: "bg-accent-500",
  confirmed: "bg-success",
  checked_in: "bg-teal-600",
  with_doctor: "bg-warning",
  ready_for_checkout: "bg-[#8B5CF6]",
  completed: "bg-ink-muted/60",
  cancelled: "bg-danger/50",
  no_show: "bg-warning"
};

function pad(n: number) {
  return String(n).padStart(2, "0");
}

function toKey(y: number, m: number, d: number) {
  return `${y}-${pad(m + 1)}-${pad(d)}`;
}

function dayLabel(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

function timeRangeRaw(startIso: string, endIso: string) {
  const start = new Date(startIso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const end = new Date(endIso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${start} – ${end}`;
}

function timeRange(a: AppointmentResponse) {
  return timeRangeRaw(a.start_time, a.end_time);
}

export function MyCalendarPage() {
  const { authedFetch } = usePlan();
  const [appointments, setAppointments] = useState<AppointmentResponse[]>([]);
  const [timeBlocks, setTimeBlocks] = useState<DoctorTimeBlockResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [blocking, setBlocking] = useState(false);

  const now = new Date();
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());
  const todayKey = toKey(now.getFullYear(), now.getMonth(), now.getDate());
  const [selectedKey, setSelectedKey] = useState(todayKey);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        setLoading(false);
        return;
      }
      try {
        const [appts, blocks] = await Promise.all([
          listMyAppointments(authedFetch),
          listMyTimeBlocks(authedFetch).catch(() => [])
        ]);
        if (!cancelled) {
          setAppointments(appts);
          setTimeBlocks(blocks);
        }
      } catch {
        if (!cancelled) setAppointments([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const byDay = useMemo(() => {
    const map = new Map<string, AppointmentResponse[]>();
    for (const a of appointments) {
      const key = toKey(new Date(a.start_time).getFullYear(), new Date(a.start_time).getMonth(), new Date(a.start_time).getDate());
      map.set(key, [...(map.get(key) || []), a]);
    }
    return map;
  }, [appointments]);

  const blocksByDay = useMemo(() => {
    const map = new Map<string, DoctorTimeBlockResponse[]>();
    for (const b of timeBlocks) {
      const key = toKey(new Date(b.start_time).getFullYear(), new Date(b.start_time).getMonth(), new Date(b.start_time).getDate());
      map.set(key, [...(map.get(key) || []), b]);
    }
    return map;
  }, [timeBlocks]);

  async function handleDeleteBlock(id: string) {
    if (!authedFetch) return;
    setTimeBlocks((prev) => prev.filter((b) => b.id !== id));
    try {
      await deleteTimeBlock(authedFetch, id);
    } catch {
      // Re-fetch would be more correct than silently leaving it removed
      // client-side, but this is low-stakes personal data — a failed
      // delete just means it reappears on next page load.
    }
  }

  const monthLabel = new Date(viewYear, viewMonth, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });

  const firstDow = new Date(viewYear, viewMonth, 1).getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

  const cells: Array<{ key: string; d: number; today: boolean }> = [];
  for (let i = 0; i < firstDow; i++) cells.push({ key: `pad-${i}`, d: 0, today: false });
  for (let d = 1; d <= daysInMonth; d++) {
    const key = toKey(viewYear, viewMonth, d);
    cells.push({ key, d, today: key === todayKey });
  }

  function shiftMonth(delta: number) {
    const next = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  }

  const selectedAppointments = (byDay.get(selectedKey) || [])
    .filter((a) => a.status !== "cancelled")
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));

  const selectedCount = byDay.get(selectedKey)?.length || 0;

  const recentCompletedCutoff = Date.now() - RECENT_DAYS * 24 * 60 * 60 * 1000;
  const recentlyCompleted = appointments
    .filter((a) => a.status === "completed" && new Date(a.start_time).getTime() >= recentCompletedCutoff)
    .sort((a, b) => +new Date(b.start_time) - +new Date(a.start_time));

  return (
    <>
      <PageHeader title="My Calendar" subtitle="Your upcoming appointments, month by month — plus your own personal time-blocks. “Book” adds a patient straight to your own schedule (e.g. a follow-up mid-consult) without going through Front Desk." />

      <div className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => shiftMonth(-1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-sand-100"
              aria-label="Previous month">
              <ChevronLeftIcon className="h-4 w-4" />
            </button>
            <p className="min-w-[140px] text-center text-sm font-bold text-ink">{monthLabel}</p>
            <button
              type="button"
              onClick={() => shiftMonth(1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-sand-100"
              aria-label="Next month">
              <ChevronRightIcon className="h-4 w-4" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setBlocking((v) => !v)}
              className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
              <CalendarClockIcon className="h-3.5 w-3.5" /> Block time
            </button>
            <Link
              to={DASHBOARD_ROUTES.myBook}
              className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700">
              <PlusIcon className="h-3.5 w-3.5" /> Book
            </Link>
          </div>
        </div>

        {blocking &&
        <TimeBlockForm
          defaultDay={selectedKey}
          onCreated={(block) => { setTimeBlocks((prev) => [...prev, block]); setBlocking(false); }}
          onCancel={() => setBlocking(false)} />
        }

        {loading ?
        <p className="mt-8 text-sm text-ink-muted">Loading…</p> :

        <div className="mt-4">
            <div className="grid grid-cols-7 gap-1.5">
              {WEEKDAYS.map((wd) => <span key={wd} className="text-center text-[11px] font-bold text-ink-soft">{wd}</span>)}
              {cells.map((cell) => {
              if (cell.d === 0) return <span key={cell.key} />;
              const dayAppts = byDay.get(cell.key) || [];
              const dayBlocks = blocksByDay.get(cell.key) || [];
              const selected = cell.key === selectedKey;
              return (
                <button
                  key={cell.key}
                  type="button"
                  onClick={() => setSelectedKey(cell.key)}
                  className={`relative flex aspect-square flex-col items-center justify-center gap-1 rounded-xl border text-sm font-bold tabular-nums transition-colors ${
                    selected ?
                    "border-teal-600 bg-teal-600/10 text-ink" :
                    cell.today ?
                    "border-accent-500 bg-accent-500/10 text-ink" :
                    "border-transparent text-ink-soft hover:bg-sand-100"
                  }`}>
                  {dayBlocks.length > 0 && (
                    <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full border border-white bg-ink-muted" title="Time blocked" />
                  )}
                  <span>{cell.d}</span>
                  <span className="flex h-1.5 items-center gap-0.5">
                    {dayAppts.slice(0, 3).map((a) => (
                      <span key={a.id} className={`h-1.5 w-1.5 rounded-full ${DOT_CLASS[a.status] || "bg-ink-muted/40"}`} />
                    ))}
                    {dayAppts.length > 3 && (
                      <span className="text-[9px] leading-none font-bold text-ink-muted">+{dayAppts.length - 3}</span>
                    )}
                  </span>
                </button>
              );
            })}
            </div>

            <div className="mt-5 border-t border-sand-200 pt-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold text-ink">
                  {dayLabel(new Date(`${selectedKey}T12:00:00`).toISOString())}
                </p>
                {selectedCount > 0 &&
              <span className="rounded-full bg-teal-600/10 px-2.5 py-0.5 text-[11px] font-semibold text-teal-600">
                    {selectedCount} appointment{selectedCount === 1 ? "" : "s"}
                  </span>
              }
              </div>

              {(blocksByDay.get(selectedKey) || []).length > 0 &&
            <div className="mt-3 space-y-1.5">
                  {(blocksByDay.get(selectedKey) || []).map((b) => (
                    <div key={b.id} className="flex items-center gap-3 rounded-xl border border-dashed border-sand-300 bg-sand-50 px-4 py-2.5">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ink-muted/10 text-ink-muted">
                        <CalendarClockIcon className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink-soft">{b.title}</p>
                        <p className="truncate text-xs text-ink-muted">{timeRangeRaw(b.start_time, b.end_time)}{b.note ? ` · ${b.note}` : ""}</p>
                      </div>
                      <button type="button" onClick={() => handleDeleteBlock(b.id)} className="shrink-0 rounded-lg p-1.5 text-ink-muted hover:bg-sand-100 hover:text-danger" aria-label="Remove block">
                        <XIcon className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
            }

              {selectedAppointments.length === 0 ?
            <div className="mt-3 rounded-xl border border-dashed border-sand-200 px-5 py-6">
                  <EmptyState
                  icon={CalendarIcon}
                  title="No appointments this day"
                  body="Nothing scheduled for this date — use the Book button above to add one." />
                </div> :

            <div className="mt-3 divide-y divide-sand-100 rounded-xl border border-sand-200">
                  {selectedAppointments.map((a) =>
            <div key={a.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-500/10 text-accent-500">
                      <ClockIcon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-ink">
                        <Link
                          to={DASHBOARD_ROUTES.patientDetail(a.patient_id)}
                          className="hover:text-teal-600">
                          {a.patient_name || "Patient"}
                        </Link>
                      </p>
                      <p className="truncate text-xs text-ink-muted">
                        {a.appointment_type}
                        {" · "}
                        {timeRange(a)}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[a.status] || "bg-sand-100 text-ink-soft"}`}>
                      {a.status.replace("_", " ")}
                    </span>
                    {a.status === "completed" &&
              <Link
                        to={`${DASHBOARD_ROUTES.consultationNoteNew(a.patient_id)}?appointmentId=${a.id}`}
                        className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
                        <FileTextIcon className="h-3.5 w-3.5" /> Document visit
                      </Link>
              }
                  </div>
            )}
                </div>
              }
            </div>
          </div>
        }
      </div>

      {recentlyCompleted.length > 0 &&
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="border-b border-sand-200 px-5 py-3.5">
            <p className="text-sm font-bold text-ink">Recently completed</p>
          </div>
          <div className="divide-y divide-sand-100">
            {recentlyCompleted.map((a) =>
          <div key={a.id} className="flex items-center gap-3 px-5 py-3.5">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink-muted/10 text-ink-muted">
                  <ClockIcon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">
                    <Link
                      to={DASHBOARD_ROUTES.patientDetail(a.patient_id)}
                      className="hover:text-teal-600">
                      {a.patient_name || "Patient"}
                    </Link>
                  </p>
                  <p className="truncate text-xs text-ink-muted">
                    {a.appointment_type}
                    {" · "}
                    {new Date(a.start_time).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                  </p>
                </div>
                <Link
              to={`${DASHBOARD_ROUTES.consultationNoteNew(a.patient_id)}?appointmentId=${a.id}`}
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

                  <FileTextIcon className="h-3.5 w-3.5" /> Document this visit
                </Link>
              </div>
          )}
          </div>
        </div>
      }
    </>);

}