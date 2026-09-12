import { useEffect, useState } from "react";
import { AlertCircleIcon, CalendarIcon, CheckIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon, LogInIcon, LogOutIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { checkIn, checkOut, listMyAttendance, type AttendanceRecordResponse } from "../../../api/entities";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

function toKey(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function ymKey(y: number, m: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}

function fmtTime(iso: string | null) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function fmtDuration(minutes: number | null) {
  if (minutes == null) return "";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

// Daily check-in/check-out calendar. A checked-in day is clickable today only
// (one record per calendar day, enforced backend-side); once you check out,
// the day is sealed with its worked time. Browsing other months shows that
// month's own records (the backend returns the month asked for).
export function AttendanceCalendar() {
  const { authedFetch } = usePlan();
  const [records, setRecords] = useState<AttendanceRecordResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());

  const todayKey = toKey(now.getFullYear(), now.getMonth(), now.getDate());

  async function refresh() {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const rows = await listMyAttendance(authedFetch, ymKey(year, month));
      setRecords(rows);
      setError(null);
    } catch {
      setRecords([]);
      setError("Couldn't load attendance.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch, year, month]);

  const byDay = new Map(records.map((r) => [r.work_date, r]));
  const todayRecord = byDay.get(todayKey) ?? null;

  async function runAction(fn: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch {
      setError("Couldn't update attendance — try again.");
    } finally {
      setBusy(false);
    }
  }

  function isToday(y: number, m: number, d: number) {
    return y === now.getFullYear() && m === now.getMonth() && d === now.getDate();
  }

  function firstDow() {
    // Show the selected month's grid starting Monday.
    const dow = new Date(year, month, 1).getDay();
    return (dow + 6) % 7;
  }

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const monthRecords = records;
  const monthCheckedCount = monthRecords.length > 0
    ? monthRecords.filter((r) => r.status === "checked_out").length
    : 0;

  function shiftMonth(delta: number) {
    const d = new Date(year, month + delta, 1);
    setYear(d.getFullYear());
    setMonth(d.getMonth());
  }

  const monthLabel = new Date(year, month, 1).toLocaleString(undefined, { month: "long", year: "numeric" });

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-bold text-ink">
          <CalendarIcon className="h-4 w-4 text-accent-500" /> Attendance
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => shiftMonth(-1)}
            disabled={busy}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-sand-100"
            aria-label="Previous month">
            <ChevronLeftIcon className="h-4 w-4" />
          </button>
          <span className="w-28 text-center text-sm font-semibold text-ink">{monthLabel}</span>
          <button
            type="button"
            onClick={() => shiftMonth(1)}
            disabled={busy}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-sand-100"
            aria-label="Next month">
            <ChevronRightIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Today's action strip */}
      <div className="mb-4 mt-3 rounded-2xl bg-sand-50 p-3">
        {todayRecord ?
          todayRecord.status === "checked_in" ?
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-xs">
              <LogInIcon className="h-3.5 w-3.5 text-teal-600" />
              <span className="font-semibold text-ink">Checked in at {fmtTime(todayRecord.check_in_at)}</span>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-700">On duty</span>
            </div>
            <button
              type="button"
              onClick={() => runAction(async () => { if (authedFetch) await checkOut(authedFetch); })}
              disabled={busy || !authedFetch}
              className="flex items-center gap-1.5 rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-ink/90 disabled:cursor-not-allowed disabled:opacity-50">
              <LogOutIcon className="h-3.5 w-3.5" /> Check out
            </button>
          </div> :
          <div className="flex items-center gap-2 text-xs">
            <CheckIcon className="h-3.5 w-3.5 text-teal-600" />
            <span className="font-semibold text-ink">Checked out at {fmtTime(todayRecord.check_out_at)}</span>
            {todayRecord.worked_minutes != null &&
            <span className="ml-auto rounded-full bg-teal-100 px-2 py-0.5 text-[11px] font-bold text-teal-700">
              <ClockIcon className="mr-0.5 inline h-3 w-3" />{fmtDuration(todayRecord.worked_minutes)} worked
            </span>
            }
          </div> :
          <button
            type="button"
            onClick={() => runAction(async () => { if (authedFetch) await checkIn(authedFetch); })}
            disabled={busy || !authedFetch}
            className="flex items-center gap-1.5 rounded-lg bg-accent-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-50">
            <LogInIcon className="h-3.5 w-3.5" /> Check in
          </button>
        }
        {!authedFetch && <p className="mt-2 text-xs text-ink-muted">Demo mode — actions disabled.</p>}
      </div>

      {loading ?
        <p className="mt-6 text-sm text-ink-muted">Loading…</p> :
        <div className="mt-3 grid grid-cols-7 gap-1.5">
          {WEEKDAYS.map((wd) => <span key={wd} className="text-center text-[11px] font-bold text-ink-soft">{wd}</span>)}
          {Array.from({ length: firstDow() }).map((_, i) => <span key={`pad-${i}`} />)}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const d = i + 1;
            const key = toKey(year, month, d);
            const rec = byDay.get(key);
            const today = isToday(year, month, d);
            const future = new Date(year, month, d).getTime() > new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
            const knockedOut = rec?.status === "checked_out";
            return (
              <button
                key={key}
                type="button"
                disabled
                title={rec ? `Checked ${rec.status === "checked_out" ? "out" : "in"} ${rec.work_date}` : today ? "Today" : future ? "Not yet available" : "Not marked"}
                className={`flex aspect-square items-center justify-center rounded-lg text-sm font-bold tabular-nums disabled:cursor-default ${
                  knockedOut ?
                  "bg-teal-600 text-white ring-2 ring-teal-600/30" :
                  rec ?
                  "bg-teal-100 text-teal-700 ring-1 ring-teal-600/30" :
                  today ?
                  "bg-accent-500 text-white ring-2 ring-accent-500/30" :
                  future ?
                  "bg-white text-ink-soft/50" :
                  "bg-sand-100 text-ink-soft/70"
                }`}>
                <span className="flex flex-col items-center leading-none">
                  <span>{d}</span>
                  {knockedOut && <span className="mt-0.5 text-[9px] font-semibold">{fmtDuration(rec.worked_minutes)}</span>}
                  {rec?.status === "checked_in" && <span className="mt-0.5 text-[9px] font-semibold">in</span>}
                  {today && !rec && <span className="mt-0.5 h-1 w-1 rounded-full bg-current opacity-70" />}
                </span>
              </button>
            );
          })}
        </div>
      }

      {error && <p className="mt-2 flex items-center gap-1 text-xs font-medium text-danger"><AlertCircleIcon className="h-3.5 w-3.5" />{error}</p>}
      <p className="mt-2 text-xs text-ink-muted">
        {monthCheckedCount} day{monthCheckedCount === 1 ? "" : "s"} worked this month.
      </p>
    </div>);
}