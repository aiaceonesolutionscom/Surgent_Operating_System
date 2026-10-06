import { Link } from "react-router-dom";
import { FileTextIcon, ClipboardListIcon, PlusIcon, ArrowRightIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useConsultationNotes } from "./useConsultationNotes";
import { useTreatmentPlans } from "./useTreatmentPlans";
import { DASHBOARD_ROUTES } from "../constants/routes";

const NOTE_STATUS_CLASS: Record<string, string> = {
  draft: "bg-sand-100 text-ink-soft",
  final: "bg-success/10 text-success"
};

const PLAN_STATUS_CLASS: Record<string, string> = {
  draft: "bg-sand-100 text-ink-soft",
  proposed: "bg-warning/10 text-warning",
  accepted: "bg-accent-500/10 text-accent-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger"
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Doctor and Owner only — clinical.py's own backend gate excludes
// Receptionist, so this section is skipped for that role entirely rather
// than showing an empty/locked panel.
export function ClinicalSection({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const { notes, loading: notesLoading } = useConsultationNotes(authedFetch, patientId);
  const { plans, loading: plansLoading } = useTreatmentPlans(authedFetch, patientId);

  if (role !== "owner" && role !== "doctor") return null;

  return (
    <div className="mb-6 grid gap-6 lg:grid-cols-2">
      <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
          <p className="flex items-center gap-2 text-sm font-bold text-ink">
            <FileTextIcon className="h-4 w-4 text-teal-600" /> Consultation notes
          </p>
          {role === "doctor" &&
          <Link to={DASHBOARD_ROUTES.consultationNoteNew(patientId)} className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
              <PlusIcon className="h-3 w-3" /> New note
            </Link>
          }
        </div>
        {notesLoading ?
        <p className="px-5 py-6 text-sm text-ink-muted">Loading…</p> :
        notes.length === 0 ?
        <p className="px-5 py-6 text-sm text-ink-muted">No consultation notes yet.</p> :

        <div className="divide-y divide-sand-100">
            {notes.map((n) =>
          <div key={n.id} className="px-5 py-3.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-medium text-ink">{n.chief_complaint || "Consultation"}</p>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${NOTE_STATUS_CLASS[n.status]}`}>{n.status}</span>
                </div>
                <p className="mt-0.5 text-xs text-ink-muted">{formatDate(n.created_at)}</p>
              </div>
          )}
          </div>
        }
      </div>

      <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
          <p className="flex items-center gap-2 text-sm font-bold text-ink">
            <ClipboardListIcon className="h-4 w-4 text-teal-600" /> Treatment plans
          </p>
          {role === "doctor" &&
          <Link to={DASHBOARD_ROUTES.treatmentPlanNew(patientId)} className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
              <PlusIcon className="h-3 w-3" /> New plan
            </Link>
          }
        </div>
        {plansLoading ?
        <p className="px-5 py-6 text-sm text-ink-muted">Loading…</p> :
        plans.length === 0 ?
        <p className="px-5 py-6 text-sm text-ink-muted">No treatment plans yet.</p> :

        <div className="divide-y divide-sand-100">
            {plans.map((p) =>
          <Link key={p.id} to={DASHBOARD_ROUTES.treatmentPlanDetail(p.id)} className="flex items-center justify-between gap-2 px-5 py-3.5 transition-colors hover:bg-sand-50">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{p.title}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">{p.items.length} item{p.items.length === 1 ? "" : "s"}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${PLAN_STATUS_CLASS[p.status]}`}>{p.status}</span>
                <ArrowRightIcon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
              </Link>
          )}
          </div>
        }
      </div>
    </div>);

}
