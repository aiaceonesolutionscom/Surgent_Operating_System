import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, CheckIcon, ScissorsIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useProcedures } from "./useProcedures";
import { getTreatmentPlan, updateTreatmentPlanItem, type TreatmentPlanResponse } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

const ITEM_STATUS_CLASS: Record<string, string> = {
  planned: "bg-sand-100 text-ink-soft",
  scheduled: "bg-accent-500/10 text-accent-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger"
};

const PLAN_STATUS_CLASS: Record<string, string> = {
  draft: "bg-sand-100 text-ink-soft",
  proposed: "bg-warning/10 text-warning",
  accepted: "bg-accent-500/10 text-accent-700",
  completed: "bg-success/10 text-success",
  cancelled: "bg-danger/10 text-danger"
};

export function TreatmentPlanPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch, role } = usePlan();
  const { patients } = usePatients(authedFetch);
  const { procedures } = useProcedures(authedFetch);
  const [plan, setPlan] = useState<TreatmentPlanResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingItemId, setSavingItemId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || !id) {
        setLoading(false);
        return;
      }
      try {
        const data = await getTreatmentPlan(authedFetch, id);
        if (!cancelled) setPlan(data);
      } catch {
        if (!cancelled) setPlan(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, id]);

  async function markCompleted(itemId: string, estimatedPrice: number | null) {
    if (!authedFetch) return;
    setSavingItemId(itemId);
    try {
      const updated = await updateTreatmentPlanItem(authedFetch, itemId, {
        status: "completed",
        actual_price: estimatedPrice
      });
      setPlan((prev) => (prev ? { ...prev, items: prev.items.map((i) => (i.id === itemId ? updated : i)) } : prev));
    } finally {
      setSavingItemId(null);
    }
  }

  if (loading) return null;

  if (!plan) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center">
        <p className="text-sm font-semibold text-ink">Treatment plan not found</p>
      </div>);

  }

  const patient = patients.find((p) => p.id === plan.patient_id);
  const procedureName = (procedureId: string) => procedures.find((p) => p.id === procedureId)?.name || "Unknown procedure";

  return (
    <>
      <Link
        to={patient ? DASHBOARD_ROUTES.patientDetail(patient.id) : DASHBOARD_ROUTES.patients}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to patient
      </Link>

      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader title={plan.title} subtitle={patient ? `For ${patient.name}` : undefined} />
        <span className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-semibold capitalize ${PLAN_STATUS_CLASS[plan.status] || "bg-sand-100 text-ink-soft"}`}>
          {plan.status}
        </span>
      </div>

      <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="divide-y divide-sand-100">
          {plan.items.map((item) =>
          <div key={item.id} className="flex items-center gap-3 px-5 py-4">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{procedureName(item.procedure_id)}</p>
                <p className="text-xs text-ink-muted">
                  {item.status === "completed" && item.actual_price != null ?
                `Charged $${item.actual_price.toLocaleString()}` :
                item.estimated_price != null ?
                `Estimated $${item.estimated_price.toLocaleString()}` :
                "No price set"}
                </p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${ITEM_STATUS_CLASS[item.status] || "bg-sand-100 text-ink-soft"}`}>
                {item.status}
              </span>
              {(role === "owner" || role === "doctor") && item.status !== "completed" && item.status !== "cancelled" &&
            <Link
              to={DASHBOARD_ROUTES.surgeryNew(plan.patient_id, item.procedure_id)}
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

                  <ScissorsIcon className="h-3.5 w-3.5" /> Schedule surgery
                </Link>
            }
              {role === "doctor" && item.status !== "completed" && item.status !== "cancelled" &&
            <button
              type="button"
              onClick={() => markCompleted(item.id, item.estimated_price)}
              disabled={savingItemId === item.id}
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-success/40 hover:text-success disabled:opacity-50">

                  <CheckIcon className="h-3.5 w-3.5" /> {savingItemId === item.id ? "Saving…" : "Mark completed"}
                </button>
            }
            </div>
          )}
        </div>
      </div>
    </>);

}
