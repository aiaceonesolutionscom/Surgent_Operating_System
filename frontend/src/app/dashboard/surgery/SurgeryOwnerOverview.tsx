import { Link } from "react-router-dom";
import { ScissorsIcon, ClockIcon, ActivityIcon, CheckCircleIcon, CalendarClockIcon } from "lucide-react";
import { DASHBOARD_ROUTES } from "../constants/routes";
import type { SurgeryOverviewResponse } from "../../../api/entities";

// Owner-only "kya chal raha hai" widget — a five-second glance at the whole
// practice's OR without opening any surgery. Who's on the table today, who's
// coming up, each doctor's load, and the per-status breakdown. The Owner stays
// hands-off (no manual booking); this is purely the what's-happening surface.
export function SurgeryOwnerOverview({
  overview,
  loading
}: {
  overview: SurgeryOverviewResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="mb-6 grid gap-4 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) =>
        <div key={i} className="h-14 animate-pulse rounded-xl bg-sand-100" />
        )}
      </div>);
  }

  if (!overview) return null;

  const statusCards = [
    { label: "Scheduled", value: overview.by_status["scheduled"] || 0, cls: "bg-accent-500/10 text-accent-700" },
    { label: "Confirmed", value: overview.by_status["confirmed"] || 0, cls: "bg-teal-500/10 text-teal-700" },
    { label: "In progress", value: overview.by_status["in_progress"] || 0, cls: "bg-amber-500/15 text-amber-700" },
    { label: "Completed", value: overview.by_status["completed"] || 0, cls: "bg-success/10 text-success" }
  ];

  return (
    <div className="mb-6 space-y-4 rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <ScissorsIcon className="h-4 w-4 text-teal-600" /> Surgery overview
        </p>
        <span className="text-xs font-medium text-ink-muted">
          {overview.completed_this_week} completed this week
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        {statusCards.map((c) =>
        <div key={c.label} className={`rounded-2xl px-4 py-3 ${c.cls}`}>
            <p className="text-2xl font-bold">{c.value}</p>
            <p className="text-xs font-semibold opacity-80">{c.label}</p>
          </div>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Today's operations" icon={ClockIcon}>
          {overview.today.length === 0 ?
          <p className="px-4 py-5 text-sm text-ink-muted">No surgeries on the table today.</p> :
          <ol className="divide-y divide-sand-100">
              {overview.today.map((s) =>
            <li key={s.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className={`h-2 w-2 shrink-0 rounded-full ${s.status === "in_progress" ? "bg-amber-500" : s.status === "confirmed" ? "bg-teal-500" : "bg-accent-500"}`} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{s.patient_name || "Patient"} — {s.procedure_name || "Surgery"}</p>
                  <p className="text-xs text-ink-muted">{s.doctor_name} · {new Date(s.scheduled_date).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</p>
                </div>
                <Link to={DASHBOARD_ROUTES.surgeryDetail(s.id)} className="text-xs font-semibold text-teal-600 hover:underline">View</Link>
              </li>
            )}
            </ol>
          }
        </Section>

        <Section title="Coming up (next 7 days)" icon={CalendarClockIcon}>
          {overview.upcoming.length === 0 ?
          <p className="px-4 py-5 text-sm text-ink-muted">Nothing booked ahead.</p> :
          <ol className="divide-y divide-sand-100">
              {overview.upcoming.map((s) =>
            <li key={s.id} className="flex items-center gap-3 px-4 py-2.5">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{s.patient_name || "Patient"} — {s.procedure_name || "Surgery"}</p>
                  <p className="text-xs text-ink-muted">{s.doctor_name} · {new Date(s.scheduled_date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</p>
                </div>
                <Link to={DASHBOARD_ROUTES.surgeryDetail(s.id)} className="text-xs font-semibold text-teal-600 hover:underline">View</Link>
              </li>
            )}
            </ol>
          }
        </Section>
      </div>

      {overview.in_progress.length > 0 &&
      <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold text-amber-700"><ActivityIcon className="h-3.5 w-3.5" /> In the OR now</span>
          {overview.in_progress.map((s) =>
        <Link
          key={s.id}
          to={DASHBOARD_ROUTES.surgeryDetail(s.id)}
          className="rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-700 transition-colors hover:bg-amber-500/20">
            {s.patient_name || "Patient"} — {s.doctor_name}
          </Link>
        )}
        </div>
      }

      {overview.per_doctor.length > 0 &&
      <div className="border-t border-sand-100 pt-4">
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
            <CheckCircleIcon className="h-3.5 w-3.5" /> Per-doctor load
          </p>
          <div className="space-y-1.5">
            {overview.per_doctor.map((d) =>
          <div key={d.doctor_id} className="flex flex-wrap items-center gap-2 text-sm">
              <span className="min-w-32 font-semibold text-ink">{d.doctor_name}</span>
              <span className="flex flex-wrap gap-1.5 text-xs text-ink-muted">
                <Pill value={d.scheduled} label="scheduled" tone="bg-accent-500/10 text-accent-700" />
                <Pill value={d.confirmed} label="confirmed" tone="bg-teal-500/10 text-teal-700" />
                <Pill value={d.in_progress} label="in OR" tone="bg-amber-500/15 text-amber-700" />
                <Pill value={d.completed} label="done" tone="bg-success/10 text-success" />
                {d.cancelled > 0 && <Pill value={d.cancelled} label="cancelled" tone="bg-ink-muted/10 text-ink-muted" />}
              </span>
            </div>
          )}
          </div>
        </div>
      }
    </div>);

}

function Section({
  title,
  icon: Icon,
  children
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-sand-100">
      <div className="flex items-center gap-1.5 border-b border-sand-100 px-4 py-2.5">
        <Icon className="h-3.5 w-3.5 text-teal-600" />
        <p className="text-xs font-bold text-ink">{title}</p>
      </div>
      {children}
    </div>);

}

function Pill({ value, label, tone }: { value: number; label: string; tone: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 font-semibold ${tone}`}>{value} {label}</span>
  );
}