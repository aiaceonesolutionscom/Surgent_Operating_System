import React from "react";
import { Link } from "react-router-dom";
import { ReceiptIcon, PlusIcon, ArrowRightIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useInvoices } from "./useInvoices";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { formatMoney } from "../finance/money";

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-sand-100 text-ink-soft",
  partially_paid: "bg-[#7C3AED]/10 text-[#7C3AED]",
  paid: "bg-success/10 text-success",
  overdue: "bg-danger/10 text-danger",
  cancelled: "bg-ink-muted/10 text-ink-muted",
  refunded: "bg-warning/10 text-warning"
};

const STATUS_LABEL: Record<string, string> = { partially_paid: "Partially paid" };

// Only rendered on Owner/Receptionist patient-detail views (Doctor's own
// detail page has no billing tab) — matches billing_router.py's _VIEW_ROLES
// exactly (Owner + Receptionist only, Doctor excluded even from viewing).
export function InvoicesSection({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const { invoices, loading } = useInvoices(authedFetch, patientId);
  const canManage = role === "owner" || role === "receptionist";

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <ReceiptIcon className="h-4 w-4 text-teal-600" /> Invoices
        </p>
        {canManage &&
        <Link to={DASHBOARD_ROUTES.invoiceNew(patientId)} className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
            <PlusIcon className="h-3 w-3" /> New invoice
          </Link>
        }
      </div>
      {loading ?
      <p className="px-5 py-6 text-sm text-ink-muted">Loading…</p> :
      invoices.length === 0 ?
      <p className="px-5 py-6 text-sm text-ink-muted">No invoices yet.</p> :

      <div className="divide-y divide-sand-100">
          {invoices.map((inv) =>
        <Link key={inv.id} to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="flex items-center justify-between gap-2 px-5 py-3.5 transition-colors hover:bg-sand-50">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{formatMoney(inv.total_amount, inv.currency)}</p>
                <p className="mt-0.5 text-xs text-ink-muted">{inv.line_items.length} item{inv.line_items.length === 1 ? "" : "s"}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS_CLASS[inv.status]}`}>{STATUS_LABEL[inv.status] || inv.status}</span>
              <ArrowRightIcon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
            </Link>
        )}
        </div>
      }
    </div>);

}
