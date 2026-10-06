import { UsersIcon, StethoscopeIcon } from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { useDoctors } from "../doctors/useDoctors";
import type { FrontDeskAppointment } from "./useFrontDesk";

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

interface Props {
  appointments: FrontDeskAppointment[];
  loading: boolean;
}

// Owner doesn't operate Front Desk — a Receptionist does that. What Owner
// needs is visibility: is the clinic running on schedule right now, and
// where is each doctor in their day. Same real appointment data as the
// Receptionist's view, deliberately read-only (no check-in/complete/etc.
// buttons) and grouped by doctor instead of by status, since "how's a
// specific doctor doing today" is the question an owner actually walks in with.
export function OwnerFrontDeskOverview({ appointments, loading }: Props) {
  const { authedFetch } = usePlan();
  const { doctors } = useDoctors(authedFetch);

  const today = appointments.filter((a) => isToday(a.start_time));

  const counts = {
    total: today.length,
    checked_in: today.filter((a) => a.status === "checked_in").length,
    with_doctor: today.filter((a) => a.status === "with_doctor").length,
    completed: today.filter((a) => a.status === "completed").length,
    no_show: today.filter((a) => a.status === "no_show").length,
  };

  if (loading) {
    return <p className="text-sm text-ink-muted">Loading…</p>;
  }

  return (
    <>
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
        <StatTile label="Appointments" value={counts.total} />
        <StatTile label="Checked in" value={counts.checked_in} accent="text-teal-600" />
        <StatTile label="With doctor" value={counts.with_doctor} accent="text-warning" />
        <StatTile label="Completed" value={counts.completed} accent="text-success" />
        <StatTile label="No-show" value={counts.no_show} accent="text-danger" />
      </div>

      {today.length === 0 ? (
        <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={UsersIcon} title="Nothing scheduled today" body="Today's practice-wide activity will show up here as appointments come in." />
        </div>
      ) : (
        <div className="space-y-5">
          {doctors.map((doctor) => {
            const forDoctor = today
              .filter((a) => a.doctor_id === doctor.id)
              .sort((a, b) => +new Date(a.start_time) - +new Date(b.start_time));
            if (forDoctor.length === 0) return null;
            return (
              <div key={doctor.id} className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
                <div className="flex items-center gap-2.5 border-b border-sand-100 px-5 py-3.5">
                  <StethoscopeIcon className="h-4 w-4 text-ink-muted" />
                  <p className="text-sm font-bold text-ink">{doctor.name}</p>
                  <span className="text-xs text-ink-muted">{forDoctor.length} today</span>
                </div>
                <div className="divide-y divide-sand-100">
                  {forDoctor.map((a) => (
                    <div key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-sand-200 text-xs font-bold text-ink-soft">
                        {a.patientInitial}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold text-ink">{a.patientName}</p>
                        <p className="truncate text-xs text-ink-muted">
                          {new Date(a.start_time).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })} · {a.appointment_type}
                        </p>
                      </div>
                      <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[a.status] || "bg-sand-100 text-ink-soft"}`}>
                        {a.status.replace(/_/g, " ")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}

function StatTile({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="rounded-2xl border border-sand-200 bg-white p-4">
      <p className={`font-display text-2xl font-600 ${accent || "text-ink"}`}>{value}</p>
      <p className="mt-0.5 text-xs text-ink-muted">{label}</p>
    </div>
  );
}
