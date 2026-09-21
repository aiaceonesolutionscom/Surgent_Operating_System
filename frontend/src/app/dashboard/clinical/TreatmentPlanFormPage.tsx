import React, { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftIcon, PlusIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useProcedures } from "./useProcedures";
import { useTreatmentPlans } from "./useTreatmentPlans";
import { DASHBOARD_ROUTES } from "../constants/routes";

interface DraftItem {
  procedureId: string;
  estimatedPrice: string;
  sessionsTotal: string;
}

export function TreatmentPlanFormPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const navigate = useNavigate();
  const { authedFetch } = usePlan();
  const { getPatient, loading: patientLoading } = usePatients(authedFetch);
  const { procedures, loading: proceduresLoading } = useProcedures(authedFetch);
  const { create } = useTreatmentPlans(authedFetch, patientId);

  const patient = patientId ? getPatient(patientId) : undefined;

  const [title, setTitle] = useState("");
  const [items, setItems] = useState<DraftItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addItem() {
    if (procedures.length === 0) return;
    const proc = procedures.find((p) => p.is_active) || procedures[0];
    setItems((prev) => [...prev, { procedureId: proc.id, estimatedPrice: proc.base_price != null ? String(proc.base_price) : "", sessionsTotal: String(proc.default_session_count || 1) }]);
  }

  function updateItem(index: number, patch: Partial<DraftItem>) {
    setItems((prev) => prev.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }

  function onProcedureChange(index: number, procedureId: string) {
    const proc = procedures.find((p) => p.id === procedureId);
    updateItem(index, {
      procedureId,
      estimatedPrice: proc?.base_price != null ? String(proc.base_price) : "",
      sessionsTotal: String(proc?.default_session_count || 1)
    });
  }

  const canSubmit = Boolean(title.trim() && patientId) && !saving;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !patientId) return;
    setSaving(true);
    setError(null);
    try {
      const plan = await create({
        patient_id: patientId,
        title: title.trim(),
        items: items.map((it, i) => ({
          procedure_id: it.procedureId,
          phase_order: i,
          estimated_price: it.estimatedPrice ? Number(it.estimatedPrice) : null,
          sessions_total: it.sessionsTotal ? Number(it.sessionsTotal) : null
        }))
      });
      if (!plan) throw new Error("no plan");
      navigate(DASHBOARD_ROUTES.patientDetail(patientId));
    } catch {
      setError("Couldn't save this treatment plan — try again.");
      setSaving(false);
    }
  }

  if (patientLoading || proceduresLoading) return null;

  return (
    <>
      <Link
        to={patientId ? DASHBOARD_ROUTES.patientDetail(patientId) : DASHBOARD_ROUTES.patients}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to patient
      </Link>

      <PageHeader
        title={patient ? `Treatment plan — ${patient.name}` : "Treatment plan"}
        subtitle="Build a phased plan from your procedure catalog — each item can be scheduled and tracked through to completion." />


      {procedures.length === 0 ?
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white">
          <EmptyState
          icon={PlusIcon}
          title="No procedures in your catalog yet"
          body="Add procedures and pricing first, from Settings → Procedures, then come back here to build a plan." />

        </div> :

      <form onSubmit={handleSubmit} className="mt-6 max-w-2xl space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Plan title *</span>
            <input
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Rhinoplasty + revision"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

          </label>

          <div className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-bold text-ink">Procedures</p>
              <button
              type="button"
              onClick={addItem}
              className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

                <PlusIcon className="h-3.5 w-3.5" /> Add item
              </button>
            </div>

            {items.length === 0 ?
          <p className="text-sm text-ink-muted">No items yet — add at least one procedure, or save an empty plan to fill in later.</p> :

          <div className="space-y-2.5">
                {items.map((item, i) =>
            <div key={i} className="flex items-center gap-2.5">
                    <select
                value={item.procedureId}
                onChange={(e) => onProcedureChange(i, e.target.value)}
                className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">

                      {procedures.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                    </select>
                    <div className="relative w-32 shrink-0">
                      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted">$</span>
                      <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={item.estimatedPrice}
                  onChange={(e) => updateItem(i, { estimatedPrice: e.target.value })}
                  className="w-full rounded-xl border border-sand-200 bg-canvas py-2 pl-6 pr-3 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />

                    </div>
                    <div className="w-24 shrink-0" title="Number of visits this item takes for this patient">
                      <input
                  type="number"
                  min="1"
                  value={item.sessionsTotal}
                  onChange={(e) => updateItem(i, { sessionsTotal: e.target.value })}
                  className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
                  placeholder="Sessions" />

                    </div>
                    <button type="button" onClick={() => removeItem(i)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-danger">
                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
            )}
              </div>
          }
          </div>

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <div className="flex items-center justify-end gap-3">
            <Link
            to={patientId ? DASHBOARD_ROUTES.patientDetail(patientId) : DASHBOARD_ROUTES.patients}
            className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

              Cancel
            </Link>
            <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

              {saving ? "Saving…" : "Save treatment plan"}
            </button>
          </div>
        </form>
      }
    </>);

}
