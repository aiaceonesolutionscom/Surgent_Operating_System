import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon, PlusIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useTreatmentPlans } from "../clinical/useTreatmentPlans";
import { useInvoices } from "./useInvoices";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { getFinanceSettings, type CreateInvoiceLineItemRequest, type FinanceSettingsResponse } from "../../../api/entities";

interface DraftLine {
  description: string;
  quantity: string;
  unitPrice: string;
}

export function InvoiceFormPage() {
  const [searchParams] = useSearchParams();
  const preselectedPatientId = searchParams.get("patient_id") || "";
  const navigate = useNavigate();
  const { authedFetch } = usePlan();
  const { patients, loading: patientsLoading } = usePatients(authedFetch);
  const { create } = useInvoices(authedFetch);

  const [patientId, setPatientId] = useState(preselectedPatientId);
  const { plans, loading: plansLoading } = useTreatmentPlans(authedFetch, patientId || undefined);

  const [treatmentPlanId, setTreatmentPlanId] = useState<string>("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [taxAmount, setTaxAmount] = useState("");
  const [discountAmount, setDiscountAmount] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [financeSettings, setFinanceSettings] = useState<FinanceSettingsResponse | null>(null);
  const [currency, setCurrency] = useState<string>("");
  useEffect(() => {
    if (!authedFetch) return;
    getFinanceSettings(authedFetch)
      .then((s) => { setFinanceSettings(s); setCurrency(s.base_currency); })
      .catch(() => setFinanceSettings(null));
  }, [authedFetch]);

  const otherCurrency = financeSettings?.base_currency === "USD" ? "PKR" : "USD";
  const canBillInOtherCurrency = Boolean(financeSettings?.usd_to_pkr_rate);

  const billableFromPlan = plans.filter((p) => p.items.length > 0);

  function addLine() {
    setLines((prev) => [...prev, { description: "", quantity: "1", unitPrice: "" }]);
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((prev) => prev.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  function removeLine(index: number) {
    setLines((prev) => prev.filter((_, i) => i !== index));
  }

  const usingPlan = Boolean(treatmentPlanId);
  const canSubmit = Boolean(patientId) && (usingPlan || lines.some((l) => l.description.trim() && l.unitPrice)) && !saving;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    try {
      const lineItems: CreateInvoiceLineItemRequest[] | undefined = usingPlan
        ? undefined
        : lines
            .filter((l) => l.description.trim() && l.unitPrice)
            .map((l) => ({ description: l.description.trim(), quantity: Number(l.quantity) || 1, unit_price: Number(l.unitPrice) }));

      const invoice = await create({
        patient_id: patientId,
        treatment_plan_id: usingPlan ? treatmentPlanId : undefined,
        line_items: lineItems,
        tax_amount: taxAmount ? Number(taxAmount) : 0,
        discount_amount: discountAmount ? Number(discountAmount) : 0,
        due_date: dueDate || undefined,
        currency: currency || undefined
      });
      if (!invoice) throw new Error("no invoice");
      navigate(DASHBOARD_ROUTES.invoiceDetail(invoice.id));
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save this invoice — try again.");
      setSaving(false);
    }
  }

  if (patientsLoading) return null;

  return (
    <>
      <Link
        to={preselectedPatientId ? DASHBOARD_ROUTES.patientDetail(preselectedPatientId) : DASHBOARD_ROUTES.invoices}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back
      </Link>

      <PageHeader title="New invoice" subtitle="Raise an invoice ad-hoc, or generate one from a patient's treatment plan." />

      <form onSubmit={handleSubmit} className="mt-6 max-w-2xl space-y-4">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Patient *</span>
          <select
            required
            value={patientId}
            onChange={(e) => {
              setPatientId(e.target.value);
              setTreatmentPlanId("");
            }}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">

            <option value="">Select a patient…</option>
            {patients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </label>

        {patientId &&
        <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Bill from</span>
            <select
            value={treatmentPlanId}
            onChange={(e) => setTreatmentPlanId(e.target.value)}
            disabled={plansLoading}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">

              <option value="">Ad-hoc (enter line items manually)</option>
              {billableFromPlan.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.items.length} item{p.items.length === 1 ? "" : "s"})</option>)}
            </select>
            {usingPlan &&
          <p className="mt-1.5 text-xs text-ink-muted">
                This invoice will include every item on this plan, priced at its actual (or estimated) price.
              </p>
          }
          </label>
        }

        {patientId && !usingPlan &&
        <div className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-bold text-ink">Line items</p>
              <button
              type="button"
              onClick={addLine}
              className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

                <PlusIcon className="h-3.5 w-3.5" /> Add line
              </button>
            </div>

            {lines.length === 0 ?
          <p className="text-sm text-ink-muted">No line items yet — add at least one.</p> :

          <div className="space-y-2.5">
                {lines.map((line, i) =>
            <div key={i} className="flex items-center gap-2.5">
                    <input
                value={line.description}
                onChange={(e) => updateLine(i, { description: e.target.value })}
                placeholder="Description"
                className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />

                    <input
                type="number"
                min="1"
                value={line.quantity}
                onChange={(e) => updateLine(i, { quantity: e.target.value })}
                className="w-16 shrink-0 rounded-xl border border-sand-200 bg-canvas px-2 py-2 text-center text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />

                    <div className="relative w-32 shrink-0">
                      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-ink-muted">$</span>
                      <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={line.unitPrice}
                  onChange={(e) => updateLine(i, { unitPrice: e.target.value })}
                  className="w-full rounded-xl border border-sand-200 bg-canvas py-2 pl-6 pr-3 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />

                    </div>
                    <button type="button" onClick={() => removeLine(i)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-danger">
                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
            )}
              </div>
          }
          </div>
        }

        {patientId && financeSettings &&
        <label className="block max-w-xs">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Currency</span>
            <select
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">

              <option value={financeSettings.base_currency}>{financeSettings.base_currency} (practice base currency)</option>
              {canBillInOtherCurrency && <option value={otherCurrency}>{otherCurrency}</option>}
            </select>
            {!canBillInOtherCurrency &&
          <p className="mt-1.5 text-xs text-ink-muted">
                Set an exchange rate in Finance Settings to bill in {otherCurrency} too.
              </p>
          }
          </label>
        }

        {patientId &&
        <div className="grid gap-4 sm:grid-cols-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Tax ({currency || "$"})</span>
              <input
              type="number"
              min="0"
              step="0.01"
              value={taxAmount}
              onChange={(e) => setTaxAmount(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Discount ({currency || "$"})</span>
              <input
              type="number"
              min="0"
              step="0.01"
              value={discountAmount}
              onChange={(e) => setDiscountAmount(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Due date</span>
              <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
          </div>
        }

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <div className="flex items-center justify-end gap-3">
          <Link
            to={preselectedPatientId ? DASHBOARD_ROUTES.patientDetail(preselectedPatientId) : DASHBOARD_ROUTES.invoices}
            className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

            Cancel
          </Link>
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

            {saving ? "Saving…" : "Create invoice"}
          </button>
        </div>
      </form>
    </>);

}
