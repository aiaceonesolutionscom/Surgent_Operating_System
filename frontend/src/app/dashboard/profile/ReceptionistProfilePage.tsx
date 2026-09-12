import React, { useEffect, useMemo, useState } from "react";
import { CalendarDaysIcon, MailIcon, PhoneIcon, UsersIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import {
  getMyStaff,
  listMyAttendance,
  updateMyStaff,
  type AttendanceRecordResponse,
  type StaffResponse,
} from "../../../api/entities";
import { WeeklyScheduleEditor, type WorkSchedule } from "../components/WeeklyScheduleEditor";
import { AttendanceCalendar } from "../attendance/AttendanceCalendar";

function fmtDuration(minutes: number) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function ymKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ReceptionistProfilePage() {
  const { authedFetch } = usePlan();
  const [staff, setStaff] = useState<StaffResponse | null>(null);
  const [records, setRecords] = useState<AttendanceRecordResponse[]>([]);
  const [schedule, setSchedule] = useState<WorkSchedule>({});
  const [phone, setPhone] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        setLoaded(true);
        return;
      }
      try {
        const [me, rows] = await Promise.all([
          getMyStaff(authedFetch),
          listMyAttendance(authedFetch, ymKey(new Date())),
        ]);
        if (!cancelled) {
          setStaff(me);
          setSchedule((me.work_schedule ?? {}) as WorkSchedule);
          setPhone(me.phone ?? "");
          setRecords(rows);
        }
      } catch {
        if (!cancelled) setLoadError("Your profile couldn't be loaded.");
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const presentDays = useMemo(
    () => records.filter((r) => r.status === "checked_in" || r.status === "checked_out").length,
    [records]
  );
  const workedMinutesThisMonth = useMemo(
    () => records.reduce((sum, r) => sum + (r.worked_minutes ?? 0), 0),
    [records]
  );

  async function saveProfile() {
    if (!authedFetch || busy) return;
    setBusy(true);
    setSaved(false);
    setError(null);
    try {
      const updated = await updateMyStaff(authedFetch, { work_schedule: schedule, phone });
      setStaff(updated);
      setSchedule((updated.work_schedule ?? {}) as WorkSchedule);
      setSaved(true);
    } catch {
      setError("Couldn't save — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="My profile" subtitle="Your details, working schedule, and attendance record." />

      {!authedFetch && (
        <p className="mb-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6 text-sm text-ink-muted">
          Sign in to see your profile.
        </p>
      )}

      {authedFetch && !staff && loaded && (
        <p className="mb-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6 text-sm font-medium text-ink-muted">
          {loadError ?? "Couldn't find your staff profile — ask the clinic owner to add you."}
        </p>
      )}

      {staff && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex flex-wrap items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-sky-500/10 text-sky-600">
              <UsersIcon className="h-6 w-6" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-lg font-bold text-ink">{staff.name || "Receptionist"}</p>
              <p className="text-sm text-ink-muted">Front desk</p>
            </div>
            <span className="rounded-full bg-sky-500/10 px-3 py-1 text-xs font-bold uppercase tracking-wide text-sky-600">
              Receptionist
            </span>
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Field icon={MailIcon} label="Email">
              <p className="py-2 text-sm font-semibold text-ink">{staff.email}</p>
            </Field>
            <Field icon={PhoneIcon} label="Phone number">
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+92 300 0000000"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
              />
            </Field>
            <Field icon={CalendarDaysIcon} label="Member since">
              <p className="py-2 text-sm font-semibold text-ink">
                {new Date(staff.created_at).toLocaleDateString(undefined, { month: "short", year: "numeric" })}
              </p>
            </Field>
          </div>
          <p className="mt-4 text-xs text-ink-muted">
            Your name and email are managed by the clinic owner — you can update your phone number and weekly schedule
            here.
          </p>
        </div>
      )}

      {staff && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-bold text-ink">My working schedule & phone</p>
            <button
              type="button"
              onClick={saveProfile}
              disabled={busy || !authedFetch}
              className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50">
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
          <WeeklyScheduleEditor value={schedule} onChange={setSchedule} />
          {saved && <p className="mt-3 text-xs font-semibold text-teal-600">Saved.</p>}
          {error && <p className="mt-3 text-xs font-medium text-danger">{error}</p>}
        </div>
      )}

      {staff && (
        <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-bold text-ink">This month</p>
            <span className="rounded-xl bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700">{presentDays} day{presentDays === 1 ? "" : "s"} present</span>
            <span className="rounded-xl bg-ink/5 px-3 py-1 text-xs font-semibold text-ink-soft">{fmtDuration(workedMinutesThisMonth)} worked</span>
          </div>
          <div className="mt-4">
            <AttendanceCalendar />
          </div>
        </div>
      )}
    </>
  );
}

function Field({
  icon: Icon,
  label,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </p>
      {children}
    </div>
  );
}