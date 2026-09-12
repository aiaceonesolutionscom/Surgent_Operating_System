import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ReceiptIcon, PlusIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useInvoices } from "./useInvoices";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { formatMoney, formatDate } from "../finance/money";
import type { InvoiceResponse } from "../../../api/entities";

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-sand-100 text-ink-soft",
  partially_paid: "bg-[#7C3AED]/10 text-[#7C3AED]",
  paid: "bg-success/10 text-success",
  overdue: "bg-danger/10 text-danger",
  cancelled: "bg-ink-muted/10 text-ink-muted",
  refunded: "bg-warning/10 text-warning"
};

const STATUS_LABEL: Record<string, string> = { partially_paid: "Partially paid" };

const STATUS_FILTERS: Array<InvoiceResponse["status"] | "all"> = ["all", "pending", "partially_paid", "paid", "overdue", "cancelled", "refunded"];

export function InvoicesPage() {
  const { authedFetch, role } = usePlan();
  const { patients } = usePatients(authedFetch);
  const { invoices, loading } = useInvoices(authedFetch);
  const [statusFilter, setStatusFilter] = useState<InvoiceResponse["status"] | "all">("all");

  const canManage = role === "owner" || role === "receptionist";
  const patientName = (patientId: string) => patients.find((p) => p.id === patientId)?.name || "Unknown patient";

  const filtered = useMemo(
    () => (statusFilter === "all" ? invoices : invoices.filter((i) => i.status === statusFilter)),
    [invoices, statusFilter]
  );

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader title="Invoices" subtitle="Every invoice raised across the practice, ad-hoc or from a treatment plan." />
        {canManage &&
        <Link
          to={DASHBOARD_ROUTES.invoiceNew()}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

            <PlusIcon className="h-4 w-4" /> New invoice
          </Link>
        }
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((s) =>
        <button
          key={s}
          type="button"
          onClick={() => setStatusFilter(s)}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition-colors ${
          statusFilter === s ? "bg-teal-600 text-white" : "bg-sand-100 text-ink-soft hover:bg-sand-200"}`
          }>

            {STATUS_LABEL[s] || s}
          </button>
        )}
      </div>

      {loading ?
      <p className="text-sm text-ink-muted">Loading…</p> :
      filtered.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState
          icon={ReceiptIcon}
          title={invoices.length === 0 ? "No invoices yet" : "No invoices match this filter"}
          body={invoices.length === 0 ? "Raise an invoice ad-hoc or generate one from a patient's treatment plan." : "Try a different status filter."} />

        </div> :

      <div className="overflow-x-auto rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-5 py-3">Patient</th>
                <th className="px-5 py-3">Total</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Due</th>
                <th className="px-5 py-3">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand-100">
              {filtered.map((inv) =>
            <tr key={inv.id} className="transition-colors hover:bg-sand-50">
                  <td className="px-5 py-3 font-medium text-ink">
                    <Link to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="hover:underline">{patientName(inv.patient_id)}</Link>
                  </td>
                  <td className="px-5 py-3 text-ink-soft tabular-nums">{formatMoney(inv.total_amount, inv.currency)}</td>
                  <td className="px-5 py-3">
                    <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_CLASS[inv.status]}`}>{STATUS_LABEL[inv.status] || inv.status}</span>
                  </td>
                  <td className="px-5 py-3 text-ink-soft">{formatDate(inv.due_date)}</td>
                  <td className="px-5 py-3 text-ink-soft">{formatDate(inv.created_at)}</td>
                </tr>
            )}
            </tbody>
          </table>
        </div>
      }
    </>);

}
