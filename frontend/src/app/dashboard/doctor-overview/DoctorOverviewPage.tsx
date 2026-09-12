import React, { useEffect, useMemo, useState } from "react";
import {
  CalendarCheckIcon,
  ScissorsIcon,
  UsersIcon,
  ClockIcon,
  PlusIcon,
  UserPlusIcon,
  CalendarDaysIcon,
  FileTextIcon,
  StethoscopeIcon,
  ShieldAlertIcon,
  AlertTriangleIcon
} from "lucide-react";
import { Link } from "react-router-dom";
import { KpiCard } from "../components/KpiCard";
import { useUser } from "@clerk/clerk-react";
import { usePlan } from "../plan/PlanContext";
import {
  getMyDoctor,
  listMyAppointments,
  getMyToday,
  type AppointmentResponse,
  type DoctorTodayResponse,
  type WaitingRoomEntry,
  type PendingNoteEntry,
  type DoctorAlertEntry
} from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { TodayAgenda } from "./TodayAgenda";
import { PatientQuickSearch } from "./PatientQuickSearch";
import { AttendanceCalendar } from "../attendance/AttendanceCalendar";
import { useSurgeries } from "../surgery/useSurgeries";

function isToday(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  return d.toDateString() === now.toDateString();
}

function isUpcoming(iso: string) {
  return new Date(iso).getTime() >= Date.now();
}

function isSurgery(type: string) {
  return /surg|plasty|lift|implant|augment|reduc|rhino|facelift|botox|filler/i.test(type);
}

export function DoctorOverviewPage() {
  const { authedFetch } = usePlan();
  const { user } = useUser();
  const clerkName = `${user?.firstName || ""} ${user?.lastName || ""}`.trim();
  const [doctorName, setDoctorName] = useState<string | null>(null);
  const [appointments, setAppointments] = useState<AppointmentResponse[]>([]);
  const [today, setToday] = useState<DoctorTodayResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        // Demo / signed-out: an honest view — no fabricated roster. The
        // schedule stays empty until a real API session provides it.
        setDoctorName(null);
        setAppointments([]);
        setLoading(false);
        return;
      }
      try {
        const [doctor, appts, snapshot] = await Promise.all([
          getMyDoctor(authedFetch).catch(() => null),
          listMyAppointments(authedFetch).catch(() => []),
          getMyToday(authedFetch).catch(() => null)
        ]);
        if (!cancelled) {
          setDoctorName(doctor?.name ?? null);
          setAppointments(appts);
          setToday(snapshot);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const appointmentsToday = appointments.filter((a) => isToday(a.start_time));
  const appointmentsTodayCount = useMemo(() => appointmentsToday.length, [appointmentsToday]);
  const surgeriesCount = useMemo(
    () => appointmentsToday.filter((a) => isSurgery(a.appointment_type)).length,
    [appointmentsToday]
  );
  const patientsUnderCare = useMemo(
    () => new Set(appointmentsToday.map((a) => a.patient_id)).size,
    [appointmentsToday]
  );

  const upcoming = appointments
    .filter((a) => isUpcoming(a.start_time))
    .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time))
    .slice(0, 5);

  // "Meri Surgeries" — the doctor's own surgeries as surgeon (scope=mine).
  const mySurgeries = useSurgeries(authedFetch, undefined, "mine");
  const myUpcomingSurgeries = useMemo(
    () =>
      mySurgeries.surgeries
        .filter((s) => s.status === "planned" && isUpcoming(s.scheduled_date))
        .sort((a, b) => +new Date(a.scheduled_date) - +new Date(b.scheduled_date))
        .slice(0, 5),
    [mySurgeries.surgeries]
  );

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">My day</p>
          <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">
            {doctorName ? `Welcome doctor ${doctorName}` : clerkName ? `Welcome, ${clerkName}` : "Welcome"}
          </h1>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">
            {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
            {" · "}
            {appointmentsTodayCount > 0
              ? `${appointmentsTodayCount} appointment${appointmentsTodayCount === 1 ? "" : "s"} on your schedule`
              : "A clear day — use the time however you need."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Link
            to={DASHBOARD_ROUTES.myBook}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
            <PlusIcon className="h-4 w-4" /> Book
          </Link>
          <Link
            to={DASHBOARD_ROUTES.patientNew}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
            <UserPlusIcon className="h-4 w-4" /> Patient
          </Link>
          <Link
            to={DASHBOARD_ROUTES.myCalendar}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            <CalendarDaysIcon className="h-4 w-4" /> My calendar
          </Link>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard icon={CalendarCheckIcon} label="Appointments today" value={String(appointmentsTodayCount)} />
        <KpiCard icon={ScissorsIcon} label="Surgeries today" value={String(surgeriesCount)} color="#10B981" />
        <KpiCard icon={UsersIcon} label="Patients today" value={String(patientsUnderCare)} color="#06B6D4" />
      </div>

      <div className="mt-6 max-w-xl">
        <PatientQuickSearch />
      </div>

      {today && today.waiting_room.length > 0 &&
      <div className="mt-6">
          <WaitingRoomWidget entries={today.waiting_room} />
        </div>
      }

      <div className="mt-6">
        <TodayAgenda appointments={appointments} loading={loading} />
      </div>

      {today && (today.pending_notes.length > 0 || today.pending_consent_count > 0 || today.alerts.length > 0) &&
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <PendingPaperworkWidget pendingNotes={today.pending_notes} pendingConsentCount={today.pending_consent_count} />
          <AlertsWidget alerts={today.alerts} />
        </div>
      }

      <div className="mt-6">
        <AttendanceCalendar />
      </div>

      {myUpcomingSurgeries.length > 0 &&
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between border-b border-sand-100 px-5 py-4">
            <p className="text-sm font-bold text-ink">Meri Surgeries</p>
            <Link to={DASHBOARD_ROUTES.surgeries} className="text-xs font-semibold text-teal-600 hover:underline">
              All surgeries
            </Link>
          </div>
          <div className="divide-y divide-sand-100">
            {myUpcomingSurgeries.map((s) =>
          <Link
            key={s.id}
            to={DASHBOARD_ROUTES.surgeryDetail(s.id)}
            className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-sand-50">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-teal-600">
                <ScissorsIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{s.procedure_name || "Surgery"} — {s.patient_name || "Patient"}</p>
                <p className="truncate text-xs text-ink-muted">
                  {new Date(s.scheduled_date).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                  {" · "}{s.assistant_doctor_name ? `+ ${s.assistant_doctor_name}` : "No assistant"}
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11px] font-semibold capitalize text-accent-700">{s.status}</span>
            </Link>
        )}
          </div>
        </div>
      }

      {upcoming.length > 0 && !isToday(upcoming[0].start_time) &&
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
            <p className="text-sm font-bold text-ink">Coming up</p>
            <Link to={DASHBOARD_ROUTES.myCalendar} className="text-xs font-semibold text-teal-600 hover:underline">
              View calendar
            </Link>
          </div>
          <div className="divide-y divide-sand-100">
            {upcoming.map((a) =>
          <div key={a.id} className="flex items-center gap-3 px-5 py-3.5">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-500/10 text-accent-500">
                  <ClockIcon className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{a.appointment_type}</p>
                  <p className="truncate text-xs text-ink-muted">
                    {a.patient_name || "Patient"}
                    {" · "}
                    {new Date(a.start_time).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                  </p>
                </div>
                <Link
                  to={`${DASHBOARD_ROUTES.consultationNoteNew(a.patient_id)}?appointmentId=${a.id}`}
                  className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
                  <FileTextIcon className="h-3.5 w-3.5" /> Document visit
                </Link>
              </div>
          )}
          </div>
        </div>
      }
    </>);
}

function elapsedMinutes(iso: string) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function WaitingRoomWidget({ entries }: { entries: WaitingRoomEntry[] }) {
  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2.5 border-b border-sand-100 px-5 py-4">
        <StethoscopeIcon className="h-4 w-4 text-teal-600" />
        <p className="text-sm font-bold text-ink">Waiting on you ({entries.length})</p>
      </div>
      <div className="divide-y divide-sand-100">
        {entries.map((e) =>
        <Link
          key={e.appointment_id}
          to={`${DASHBOARD_ROUTES.consultationNoteNew(e.patient_id)}?appointmentId=${e.appointment_id}`}
          className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-sand-50">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sand-200 text-sm font-bold text-ink-soft">
              {e.patient_name[0]?.toUpperCase() || "?"}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{e.patient_name}</p>
              <p className="truncate text-xs text-ink-muted">{e.appointment_type}</p>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${e.status === "with_doctor" ? "bg-warning/10 text-warning" : "bg-teal-600/10 text-teal-600"}`}>
              {e.status === "with_doctor" ? "With you" : `Waiting ${elapsedMinutes(e.checked_in_at!)}`}
            </span>
          </Link>
        )}
      </div>
    </div>);

}

function PendingPaperworkWidget({ pendingNotes, pendingConsentCount }: { pendingNotes: PendingNoteEntry[]; pendingConsentCount: number }) {
  const empty = pendingNotes.length === 0 && pendingConsentCount === 0;
  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2.5 border-b border-sand-100 px-5 py-4">
        <FileTextIcon className="h-4 w-4 text-ink-muted" />
        <p className="text-sm font-bold text-ink">Pending paperwork</p>
      </div>
      {empty ?
      <p className="px-5 py-6 text-sm text-ink-muted">Nothing outstanding — all caught up.</p> :

      <div className="divide-y divide-sand-100">
          {pendingConsentCount > 0 &&
        <div className="flex items-center gap-3 px-5 py-3.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
                <ShieldAlertIcon className="h-4 w-4" />
              </span>
              <p className="text-sm text-ink">
                <span className="font-semibold">{pendingConsentCount}</span> consent{pendingConsentCount === 1 ? "" : "s"} still unsigned across your patients
              </p>
            </div>
        }
          {pendingNotes.map((n) =>
        <Link
          key={n.note_id}
          to={n.appointment_id ? `${DASHBOARD_ROUTES.consultationNoteNew(n.patient_id)}?appointmentId=${n.appointment_id}` : DASHBOARD_ROUTES.patientDetail(n.patient_id)}
          className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-sand-50">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sand-100 text-ink-muted">
                <FileTextIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{n.patient_name}</p>
                <p className="truncate text-xs text-ink-muted">Consultation note still in draft</p>
              </div>
            </Link>
        )}
        </div>
      }
    </div>);

}

function AlertsWidget({ alerts }: { alerts: DoctorAlertEntry[] }) {
  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2.5 border-b border-sand-100 px-5 py-4">
        <AlertTriangleIcon className="h-4 w-4 text-danger" />
        <p className="text-sm font-bold text-ink">Alerts</p>
      </div>
      {alerts.length === 0 ?
      <p className="px-5 py-6 text-sm text-ink-muted">Nothing overdue right now.</p> :

      <div className="divide-y divide-sand-100">
          {alerts.map((a, i) =>
        <Link
          key={i}
          to={DASHBOARD_ROUTES.patientDetail(a.patient_id)}
          className="flex items-center gap-3 px-5 py-3.5 transition-colors hover:bg-sand-50">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
                <AlertTriangleIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{a.patient_name}</p>
                <p className="truncate text-xs text-ink-muted">{a.message} · {elapsedMinutes(a.since)} ago</p>
              </div>
            </Link>
        )}
        </div>
      }
    </div>);

}