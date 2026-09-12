import { useEffect, useMemo, useState } from "react";
import { CalendarDaysIcon, ChevronLeftIcon, ChevronRightIcon, ClockIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import {
  listTeamAttendance,
  listTeamMonthRecords,
  type TeamMonthResponse,
  type TeamPresenceItem,
} from "../../../api/entities";

function toKey(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

function ymKey(y: number, m: number) {
  return `${y}-${String(m + 1).padStart(2, "0")}`;
}

function daysInMonth(y: number, m: number) {
  return new Date(y, m + 1, 0).getDate();
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

function RoleBadge({ role }: { role: "doctor" | "receptionist" }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${role === "doctor" ? "bg-accent-500/10 text-accent-600" : "bg-sky-500/10 text-sky-600"}`}>
      {role === "doctor" ? "Doctor" : "Reception"}
    </span>
  );
}

// Owner-only daily + monthly attendance view for the whole practice team.
// Backed by GET /attendance/team (presence for one date) and
// GET /attendance/team/records (per-member day grid for a month) —
// see backend/src/router/attendance/attendance_router.py.
export function TeamAttendancePage() {
  const { authedFetch } = usePlan();
  const now = new Date();

  // --- today presence ---
  const [presenceDate, setPresenceDate] = useState(() => toKey(now.getFullYear(), now.getMonth(), now.getDate()));
  const [presence, setPresence] = useState<TeamPresenceItem[] | null>(null);
  const [presenceLoading, setPresenceLoading] = useState(true);
  const [presenceError, setPresenceError] = useState<string | null>(null);

  // --- monthly records ---
  const [myear, setMyear] = useState(now.getFullYear());
  const [mmonth, setMmonth] = useState(now.getMonth());
  const [monthData, setMonthData] = useState<TeamMonthResponse | null>(null);
  const [monthLoading, setMonthLoading] = useState(true);
  const [monthError, setMonthError] = useState<string | null>(null);

  useEffect(() => {
    if (!authedFetch) {
      setPresenceLoading(false);
      return;
    }
    let cancelled = false;
    setPresenceLoading(true);
    listTeamAttendance(authedFetch, presenceDate)
      .then((rows) => { if (!cancelled) { setPresence(rows); setPresenceError(null); } })
      .catch(() => { if (!cancelled) setPresenceError("Couldn't load today's presence."); })
      .finally(() => { if (!cancelled) setPresenceLoading(false); });
    return () => { cancelled = true; };
  }, [authedFetch, presenceDate]);

  useEffect(() => {
    if (!authedFetch) {
      setMonthLoading(false);
      return;
    }
    let cancelled = false;
    setMonthLoading(true);
    listTeamMonthRecords(authedFetch, ymKey(myear, mmonth))
      .then((data) => { if (!cancelled) { setMonthData(data); setMonthError(null); } })
      .catch(() => { if (!cancelled) setMonthError("Couldn't load monthly records."); })
      .finally(() => { if (!cancelled) setMonthLoading(false); });
    return () => { cancelled = true; };
  }, [authedFetch, myear, mmonth]);

  const present = useMemo(() => (presence ?? []).filter((p) => p.status !== "absent"), [presence]);
  const checkedInNow = useMemo(() => present.filter((p) => p.status === "checked_in").length, [present]);
  const lateCount = useMemo(() => present.filter((p) => p.status === "checked_in" && (p.late_minutes ?? 0) > 0).length, [present]);
  const workedTodayMinutes = useMemo(() => present.reduce((sum, p) => sum + (p.worked_minutes ?? 0), 0), [present]);

  const totalPresenceDays = useMemo(
    () => (monthData?.members ?? []).reduce((sum, m) => sum + m.present_days, 0),
    [monthData]
  );
  const totalMinutes = useMemo(
    () => (monthData?.members ?? []).reduce((sum, m) => sum + m.total_minutes, 0),
    [monthData]
  );

  const dayCount = daysInMonth(myear, mmonth);

  function shiftMonth(delta: number) {
    const d = new Date(myear, mmonth + delta, 1);
    setMyear(d.getFullYear());
    setMmonth(d.getMonth());
  }

  const monthLabel = new Date(myear, mmonth, 1).toLocaleString(undefined, { month: "long", year: "numeric" });

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Team operations</p>
          <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">
            Team attendance
          </h1>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">
            Who is in the clinic today, and each member&apos;s full daily record by month.
          </p>
        </div>
      </div>

      {/* Today's presence */}
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold text-ink">
            <CalendarDaysIcon className="h-4 w-4 text-accent-500" /> Today&apos;s presence
          </div>
          <input
            type="date"
            value={presenceDate}
            onChange={(e) => setPresenceDate(e.target.value || presenceDate)}
            className="rounded-xl border border-sand-200 px-3 py-1.5 text-sm font-medium text-ink outline-none focus:border-teal-500"
          />
        </div>

        {!presenceLoading && presence && presence.length > 0 &&
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="rounded-xl bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700">
            {present.length} present · {checkedInNow} still on duty
          </span>
          {lateCount > 0 &&
          <span className="rounded-xl bg-warning/10 px-3 py-1.5 text-xs font-semibold text-warning">
            {lateCount} late
          </span>
          }
          <span className="rounded-xl bg-ink/5 px-3 py-1.5 text-xs font-semibold text-ink-soft">
            {workedTodayMinutes >= 0 && fmtDuration(workedTodayMinutes)} worked so far
          </span>
        </div>
        }

        <div className="mt-4 divide-y divide-sand-100">
          {presenceLoading ?
            <p className="py-6 text-sm text-ink-muted">Loading…</p> :
            presenceError ?
            <p className="py-6 text-sm font-medium text-danger">{presenceError}</p> :
            (presence ?? []).map((p) => (
              <div key={`${p.role}-${p.user_id ?? p.doctor_id ?? p.name}`} className="flex items-center gap-3 py-3.5">
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
                  p.status === "absent" ? "bg-sand-100 text-ink-muted" : p.role === "doctor" ? "bg-accent-500/10 text-accent-600" : "bg-sky-500/10 text-sky-600"
                }`}>
                  {p.name.trim().split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{p.name}</p>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2">
                    <RoleBadge role={p.role} />
                    {p.status === "checked_in" && <span className="text-xs text-teal-600">In at {fmtTime(p.check_in_at)}</span>}
                    {p.status === "checked_out" && <span className="text-xs text-ink-muted">Out at {fmtTime(p.check_out_at)} · {fmtDuration(p.worked_minutes)} worked</span>}
                    {p.status === "absent" && (p.scheduled_today ? <span className="text-xs text-ink-muted">Absent</span> : <span className="text-xs text-ink-soft">Off day</span>)}
                    {p.scheduled_start && <span className="text-xs text-ink-soft">Expected {p.scheduled_start}{p.scheduled_end ? `–${p.scheduled_end}` : ""}</span>}
                    {p.status === "checked_in" && (p.late_minutes ?? 0) > 0 &&
                    <span className="rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-bold text-danger">Late by {p.late_minutes}m</span>
                    }
                  </div>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                  p.status === "checked_in" ? "bg-amber-100 text-amber-700" :
                  p.status === "checked_out" ? "bg-teal-100 text-teal-700" : "bg-sand-200 text-ink-muted"
                }`}>
                  {p.status === "checked_in" ? "On duty" : p.status === "checked_out" ? "Done" : "Out"}
                </span>
              </div>
            ))}
        </div>
      </div>

      {/* Monthly records */}
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold text-ink">
            <CalendarDaysIcon className="h-4 w-4 text-accent-500" /> Monthly records
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => shiftMonth(-1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-sand-100"
              aria-label="Previous month">
              <ChevronLeftIcon className="h-4 w-4" />
            </button>
            <span className="w-32 text-center text-sm font-semibold text-ink">{monthLabel}</span>
            <button
              type="button"
              onClick={() => shiftMonth(1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-sand-100"
              aria-label="Next month">
              <ChevronRightIcon className="h-4 w-4" />
            </button>
          </div>
        </div>

        {!monthLoading && monthData && monthData.members.length > 0 &&
        <div className="mt-4 flex flex-wrap gap-2">
          <span className="rounded-xl bg-teal-50 px-3 py-1.5 text-xs font-semibold text-teal-700">
            {totalPresenceDays} member-day{totalPresenceDays === 1 ? "" : "s"} on duty
          </span>
          <span className="rounded-xl bg-ink/5 px-3 py-1.5 text-xs font-semibold text-ink-soft">
            {fmtDuration(totalMinutes)} total worked
          </span>
        </div>
        }

        <div className="mt-4 overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="flex items-center gap-0.5 border-b border-sand-200 pb-2">
              <span className="w-44 shrink-0 text-[11px] font-bold uppercase tracking-wide text-ink-muted">Team member</span>
              <div className="flex flex-1 items-center justify-between gap-0.5">
                {Array.from({ length: dayCount }).map((_, i) => (
                  <span key={i} className="w-7 shrink-0 text-center text-[10px] font-bold text-ink-muted">{i + 1}</span>
                ))}
              </div>
              <span className="ml-3 w-24 shrink-0 text-right text-[11px] font-bold uppercase tracking-wide text-ink-muted">Total</span>
            </div>

            {monthLoading ?
              <p className="py-6 text-sm text-ink-muted">Loading…</p> :
              monthError ?
              <p className="py-6 text-sm font-medium text-danger">{monthError}</p> :
              (monthData?.members ?? []).map((m) => {
                const byDay = new Map(m.records.map((r) => [r.work_date, r]));
                return (
                  <div key={`${m.role}-${m.user_id ?? m.doctor_id ?? m.name}`} className="flex items-center gap-0.5 border-b border-sand-100 py-2.5">
                    <div className="flex w-44 shrink-0 items-center gap-2 pr-2">
                      <span className="truncate text-sm font-semibold text-ink">{m.name}</span>
                      <RoleBadge role={m.role} />
                    </div>
                    <div className="flex flex-1 items-center justify-between">
                      {Array.from({ length: dayCount }).map((_, i) => {
                        const dayKey = `${ymKey(myear, mmonth)}-${String(i + 1).padStart(2, "0")}`;
                        const rec = byDay.get(dayKey);
                        return (
                          <span
                            key={i}
                            title={rec
                              ? `${dayKey}\nIn ${fmtTime(rec.check_in_at)} · ${rec.check_out_at ? `Out ${fmtTime(rec.check_out_at)} · ${fmtDuration(rec.worked_minutes)} worked` : "still on duty"}${rec.late_minutes != null && rec.late_minutes > 0 ? `\nLate by ${rec.late_minutes}m` : ""}`
                              : `${dayKey} — not in`}
                            className={`mx-auto h-6 w-6 rounded-md text-center text-[10px] font-bold leading-6 ${
                              rec ? (rec.late_minutes != null && rec.late_minutes > 0 ? "bg-warning text-white" : "bg-teal-600 text-white") : "bg-sand-100 text-ink-soft/60"
                            }`}>
                            {rec ? <ClockIcon className="mx-auto h-3 w-3" /> : ""}
                          </span>
                        );
                      })}
                    </div>
                    <div className="ml-3 w-24 shrink-0 text-right">
                      <p className="text-sm font-bold tabular-nums text-ink">{m.present_days}d</p>
                      <p className="text-[11px] font-medium text-ink-muted">{fmtDuration(m.total_minutes)}</p>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </>);
}