import { useState } from "react";
import { Link } from "react-router-dom";
import { ScissorsIcon, PlusIcon, ClockIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { useSurgeries } from "./useSurgeries";
import { DASHBOARD_ROUTES } from "../constants/routes";

const STATUS_STYLES: Record<string, string> = {
  planned: "bg-accent-500/10 text-accent-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-ink-muted/10 text-ink-muted"
};

function formatDateTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export function SurgeryListPage() {
  const { authedFetch, role } = usePlan();
  const isDoctor = role === "doctor";
  const canManage = role === "owner" || role === "doctor";
  // Doctors default to "Mine" (their own surgeries as surgeon); "All" stays
  // available when they have practice-wide visibility. Owner/Receptionist
  // always see the whole practice's list.
  const [scope, setScope] = useState<"all" | "mine">(isDoctor ? "mine" : "all");
  const { surgeries, loading } = useSurgeries(authedFetch, undefined, isDoctor ? scope : undefined);

  const upcoming = surgeries.filter((s) => s.status === "planned");
  const past = surgeries.filter((s) => s.status !== "planned");

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title="Surgery"
          subtitle={isDoctor ? "Your surgeries across the practice." : "Every planned, completed, and cancelled surgery across the practice."}
        />
        {canManage &&
        <Link
          to={DASHBOARD_ROUTES.surgeryNew()}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
          <PlusIcon className="h-4 w-4" /> Schedule surgery
        </Link>
        }
      </div>

      {isDoctor &&
      <div className="mb-6 inline-flex rounded-xl border border-sand-200 bg-white p-1">
        <button
          type="button"
          onClick={() => setScope("mine")}
          className={`rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-colors ${scope === "mine" ? "bg-accent-500 text-white" : "text-ink-soft hover:text-ink"}`}>
          Mine
        </button>
        <button
          type="button"
          onClick={() => setScope("all")}
          className={`rounded-lg px-3.5 py-1.5 text-sm font-semibold transition-colors ${scope === "all" ? "bg-accent-500 text-white" : "text-ink-soft hover:text-ink"}`}>
          All
        </button>
      </div>
      }

      {loading ?
      <p className="text-sm text-ink-muted">Loading…</p> :
      surgeries.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={ScissorsIcon} title="No surgeries yet" body="Schedule a surgery from a patient's treatment plan, or start one directly here." />
        </div> :

      <div className="space-y-6">
          {upcoming.length > 0 &&
        <SurgerySection title={`Upcoming (${upcoming.length})`} surgeries={upcoming} />
        }
          {past.length > 0 &&
        <SurgerySection title={`Past (${past.length})`} surgeries={past} />
        }
        </div>
      }
    </>);

}

function SurgerySection({ title, surgeries }: { title: string; surgeries: ReturnType<typeof useSurgeries>["surgeries"] }) {
  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="border-b border-sand-100 px-5 py-4">
        <p className="text-sm font-bold text-ink">{title}</p>
      </div>
      <div className="divide-y divide-sand-100">
        {surgeries.map((s) =>
        <Link
          key={s.id}
          to={DASHBOARD_ROUTES.surgeryDetail(s.id)}
          className="flex flex-wrap items-center gap-3 px-5 py-4 transition-colors hover:bg-sand-50">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-teal-600">
              <ScissorsIcon className="h-4.5 w-4.5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-ink">{s.procedure_name || "Surgery"} — {s.patient_name || "Patient"}</p>
              <p className="flex items-center gap-1 text-xs text-ink-muted">
                <ClockIcon className="h-3 w-3" /> {formatDateTime(s.scheduled_date)}
                {" · "}{s.doctor_name || "Doctor"}
                {s.assistant_doctor_name && <> + {s.assistant_doctor_name}</>}
              </p>
            </div>
            <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_STYLES[s.status] || "bg-sand-100 text-ink-soft"}`}>
              {s.status}
            </span>
          </Link>
        )}
      </div>
    </div>);

}