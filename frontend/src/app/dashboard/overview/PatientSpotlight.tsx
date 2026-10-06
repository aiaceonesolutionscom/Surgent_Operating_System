import { ArrowRightIcon, UsersIcon, SparklesIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePatients } from "../patients/usePatients";
import { EmptyState } from "../components/EmptyState";
import type { Patient } from "../patients/types";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import { usePlan } from "../plan/PlanContext";

const STATUS_CLASS: Record<Patient["status"], string> = {
  active: "bg-success/10 text-success",
  lead: "bg-warning/10 text-warning",
  inactive: "bg-ink-muted/10 text-ink-muted"
};

const STATUS_LABEL: Record<Patient["status"], string> = {
  active: "Active",
  lead: "Lead",
  inactive: "Inactive"
};

// Real patient records, most-recently-added first — replaces an earlier
// version of this panel that showed 3 hardcoded names/stock photos regardless
// of which practice was signed in. No photo field exists on Patient yet, so
// this uses the same initial-avatar convention as PatientsPage/DoctorsPage
// rather than a placeholder image.
export function PatientSpotlight() {
  const { authedFetch } = usePlan();
  const { patients, loading } = usePatients(authedFetch);
  const recent = [...patients].reverse().slice(0, 3);

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-display text-lg font-600 text-ink">Patient Case Spotlight</h2>
        <Link to={DASHBOARD_ROUTES.patients} className="flex items-center gap-1 text-xs font-semibold text-accent-500 hover:underline">
          Browse all patients <ArrowRightIcon className="h-3 w-3" />
        </Link>
      </div>

      {loading ?
      <p className="text-sm text-ink-muted">Loading…</p> :
      recent.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={UsersIcon} title="No patients yet" body="Add your first patient to see them spotlighted here." />
        </div> :

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {recent.map((p) => {
          const agent = p.assignedAgentSlug ? AGENTS_BY_SLUG[p.assignedAgentSlug] : null;
          return (
            <Link
              key={p.id}
              to={DASHBOARD_ROUTES.patientDetail(p.id)}
              className="group overflow-hidden rounded-[22px] border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] transition-shadow hover:shadow-[0_12px_35px_rgba(15,23,42,0.12)]">

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-sm font-bold text-teal-600">
                    {p.initial}
                  </span>
                  <div className="min-w-0">
                    <h4 className="truncate font-display text-[15px] font-600 text-ink">{p.name}</h4>
                    <span className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLASS[p.status]}`}>
                      {STATUS_LABEL[p.status]}
                    </span>
                  </div>
                </div>
              </div>
              <p className="mt-3.5 line-clamp-2 text-xs text-ink-muted">
                {p.chiefComplaint || "No chief complaint on file."}
              </p>
              {agent &&
              <p className="mt-2.5 flex items-center gap-1.5 text-[11px] font-semibold text-teal-600">
                  <SparklesIcon className="h-3 w-3" /> {agent.name}
                </p>
              }
            </Link>);

        })}
        </div>
      }
    </section>);

}
