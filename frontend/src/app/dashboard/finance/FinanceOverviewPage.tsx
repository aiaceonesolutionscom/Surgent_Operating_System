import React, { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  WalletIcon, ReceiptIcon, PlusIcon, CreditCardIcon,
  BanknoteIcon, UserPlusIcon, XIcon, SettingsIcon,
  TrashIcon, ScaleIcon, TrendingDownIcon, DollarSignIcon,
  ArrowUpRightIcon, CoinsIcon
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { KpiCard } from "../components/KpiCard";
import { EmptyState } from "../components/EmptyState";
import { FinanceAgentCard } from "./FinanceAgentCard";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useInvoices } from "../billing-invoices/useInvoices";
import { useExpenses } from "./useExpenses";
import { formatMoney, formatDate } from "./money";
import {
  listStaff, getFinanceOverview, getFinanceSettings, updateFinanceSettings,
  getWalletBalance, listWalletTransactions, createWalletCheckoutSession, confirmWalletCheckoutSession,
  type FinanceOverviewResponse, type ExpenseResponse, type InvoiceResponse, type StaffResponse,
  type FinanceSettingsResponse, type WalletBalanceResponse, type WalletTransactionResponse
} from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

type Tab = "overview" | "invoices" | "payments" | "wallet";
type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

const TYPE_META: Record<string, { label: string; className: string }> = {
  expense: { label: "Expense", className: "bg-sand-100 text-ink-soft" },
  refund: { label: "Refund", className: "bg-warning/10 text-warning" },
  salary: { label: "Salary", className: "bg-[#7C3AED]/10 text-[#7C3AED]" }
};

const INVOICE_STATUS_CLASS: Record<string, string> = {
  pending: "bg-sand-100 text-ink-soft",
  partially_paid: "bg-[#7C3AED]/10 text-[#7C3AED]",
  paid: "bg-success/10 text-success",
  overdue: "bg-danger/10 text-danger",
  cancelled: "bg-ink-muted/10 text-ink-muted",
  refunded: "bg-warning/10 text-warning"
};

const INVOICE_STATUS_LABEL: Record<string, string> = { partially_paid: "Partially paid" };

const TYPE_OPTIONS = ["expense", "refund", "salary"];

function TypeBadge({ type }: { type: string }) {
  const meta = TYPE_META[type] ?? TYPE_META.expense;
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${meta.className}`}>{meta.label}</span>;
}

function StatusBadge({ status }: { status: string }) {
  const paid = status === "paid";
  return (
    <span className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${paid ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${paid ? "bg-success" : "bg-warning"}`} /> {paid ? "Paid" : "Pending"}
    </span>
  );
}

// One finance hub: KPIs, invoices, payments (expenses/refunds/salaries), and
// the practice's Stripe-funded credits wallet, all in one screen. An owner
// can run the whole money side without leaving this page. A receptionist
// sees invoices/payments read-only; Wallet + Finance Settings are Owner-only.
export function FinanceOverviewPage() {
  const { authedFetch, role, loading: roleLoading } = usePlan();
  // usePlanTier() seeds `role` with a placeholder "owner" before the real
  // /practice/me response resolves — trusting it before `loading` clears
  // fires Owner-only calls (finance/settings, staff) for every role for one
  // render, each a real (if harmless) 403. Same fix as MessagesBell.tsx.
  const isOwner = !roleLoading && role === "owner";
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = (searchParams.get("tab") as Tab) || "overview";
  const [tab, setTab] = useState<Tab>(["overview", "invoices", "payments", "wallet"].includes(initialTab) ? initialTab : "overview");

  const [overview, setOverview] = useState<FinanceOverviewResponse | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [staff, setStaff] = useState<StaffResponse[]>([]);
  const [financeSettings, setFinanceSettings] = useState<FinanceSettingsResponse | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const { patients } = usePatients(authedFetch);
  const { invoices, loading: invoicesLoading } = useInvoices(authedFetch);
  const { expenses, loading: expensesLoading, create: createExpense, update: updateExpense, remove: removeExpense } = useExpenses(authedFetch);

  const [showAddExpense, setShowAddExpense] = useState(false);
  const [showPaySalary, setShowPaySalary] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) { setOverviewLoading(false); return; }
      try { const d = await getFinanceOverview(authedFetch); if (!cancelled) setOverview(d); }
      catch { if (!cancelled) setOverview(null); }
      finally { if (!cancelled) setOverviewLoading(false); }
    })();
    if (isOwner && authedFetch) {
      listStaff(authedFetch).then(setStaff).catch(() => undefined);
      getFinanceSettings(authedFetch).then(setFinanceSettings).catch(() => undefined);
    }
    return () => { cancelled = true; };
  }, [authedFetch, isOwner]);

  function switchTab(t: Tab) {
    setTab(t);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("tab", t);
      return next;
    }, { replace: true });
  }

  const patientName = (patientId: string) => patients.find((p) => p.id === patientId)?.name || "Unknown patient";
  const loading = overviewLoading || invoicesLoading || expensesLoading;
  const hasData = overview ? overview.invoice_count > 0 || overview.expense_count > 0 : false;

  const pendingInvoices = useMemo(() => invoices.filter((i) => i.status === "pending" || i.status === "partially_paid" || i.status === "overdue"), [invoices]);
  const recentInvoices = useMemo(() => invoices.slice(0, 5), [invoices]);
  const recentExpenses = useMemo(() => expenses.slice(0, 5), [expenses]);

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Finance"
          subtitle={isOwner
            ? "Everything money, in one place — invoices, payments, salaries & expenses, and practice credits."
            : "A read-only view of the practice's finances."} />
        {isOwner &&
        <button
          type="button"
          onClick={() => setShowSettings(true)}
          className="flex shrink-0 items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
            <SettingsIcon className="h-4 w-4" /> Finance settings
          </button>
        }
      </div>

      {isOwner &&
      <div className="mb-6 flex flex-wrap items-center gap-2.5">
          <Link
          to={DASHBOARD_ROUTES.invoiceNew()}
          className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(13,148,136,0.25)] transition-colors hover:bg-teal-700">
            <PlusIcon className="h-4 w-4" /> New invoice
          </Link>
          <button
          type="button"
          onClick={() => setShowPaySalary(true)}
          className="flex items-center gap-1.5 rounded-xl bg-[#7C3AED] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_6px_18px_rgba(124,58,237,0.25)] transition-colors hover:bg-[#6D28D9]">
            <UserPlusIcon className="h-4 w-4" /> Pay salary
          </button>
          <button
          type="button"
          onClick={() => setShowAddExpense(true)}
          className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
            <BanknoteIcon className="h-4 w-4" /> Record payment
          </button>
        </div>
      }

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard icon={DollarSignIcon} label="Revenue (paid)" value={formatMoney(overview?.total_revenue ?? 0)} changePercent={Math.min(100, Math.max(1, (overview?.total_revenue ?? 0) * 0.02))} color="#16A34A" />
        <KpiCard icon={TrendingDownIcon} label="Spending" value={formatMoney(overview?.total_expenses ?? 0)} color="#DC2626" />
        <KpiCard icon={ScaleIcon} label="Net" value={formatMoney(overview?.net ?? 0)} color={(overview?.net ?? 0) >= 0 ? "#2563EB" : "#DC2626"} />
        <KpiCard icon={ReceiptIcon} label="Open invoices" value={String(pendingInvoices.length)} color="#F59E0B" />
      </div>

      {authedFetch && <FinanceAgentCard authedFetch={authedFetch} />}

      {/* Quick money actions (owner) */}
      {isOwner && pendingInvoices.length > 0 &&
      <div className="mt-6 overflow-hidden rounded-3xl border border-teal-600/15 bg-gradient-to-r from-teal-600/8 to-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="flex items-center gap-2 text-sm font-bold text-ink"><CreditCardIcon className="h-4 w-4 text-teal-600" /> Outstanding invoices</p>
              <p className="mt-0.5 text-xs text-ink-muted">{pendingInvoices.length} invoice{pendingInvoices.length > 1 ? "s" : ""} awaiting payment</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {pendingInvoices.slice(0, 3).map((inv) =>
            <Link key={inv.id} to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700">
                  <CreditCardIcon className="h-3.5 w-3.5" /> {patientName(inv.patient_id)} · {formatMoney(inv.balance_due, inv.currency)}
                </Link>
            )}
            </div>
          </div>
        </div>
      }

      {/* Tabs */}
      <div className="mt-8 flex gap-1 border-b border-sand-200">
        {(["overview", "invoices", "payments", ...(isOwner ? ["wallet" as Tab] : [])] as Tab[]).map((t) =>
      <button
        key={t}
        type="button"
        onClick={() => switchTab(t)}
        className={`flex items-center gap-1.5 rounded-t-xl px-4 py-2.5 text-sm font-semibold capitalize transition-colors ${tab === t ? "border-b-2 border-teal-600 text-teal-600" : "text-ink-muted hover:text-ink"}`}>
          {t === "wallet" && <CoinsIcon className="h-3.5 w-3.5" />} {t}
        </button>
      )}
      </div>

      <div className="mt-6">
        {tab === "wallet" ?
        <WalletTab authedFetch={authedFetch} baseCurrency={financeSettings?.base_currency ?? "USD"} /> :

        loading && !hasData ? <p className="text-sm text-ink-muted">Loading…</p> :
        !hasData && tab === "overview" ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState icon={WalletIcon} title="Not enough data yet" body="Raise an invoice and record a payment — this page will assemble a real picture of your practice's money." />
          </div> :

        tab === "overview" ?
        <OverviewTab
          isOwner={isOwner}
          recentInvoices={recentInvoices}
          recentExpenses={recentExpenses}
          patientName={patientName}
          onGoInvoices={() => switchTab("invoices")}
          onGoPayments={() => switchTab("payments")} /> :

        tab === "invoices" ?
        <InvoicesTab
          invoices={invoices}
          patientName={patientName} /> :

        <PaymentsTab
          isOwner={isOwner}
          expenses={expenses}
          onAdd={() => setShowAddExpense(true)}
          onPaySalary={() => setShowPaySalary(true)}
          onUpdate={updateExpense}
          onDelete={removeExpense} />
        }
      </div>

      {showAddExpense &&
      <AddExpenseModal
        staff={staff}
        onCreate={createExpense}
        onRefresh={async () => { setOverview(await getFinanceOverview(authedFetch!)); }}
        onClose={() => setShowAddExpense(false)} />}

      {showPaySalary &&
      <PaySalaryModal
        staff={staff}
        onCreate={createExpense}
        onRefresh={async () => { setOverview(await getFinanceOverview(authedFetch!)); }}
        onClose={() => setShowPaySalary(false)} />}

      {showSettings && financeSettings &&
      <FinanceSettingsModal
        settings={financeSettings}
        authedFetch={authedFetch}
        onSaved={(s) => { setFinanceSettings(s); setShowSettings(false); }}
        onClose={() => setShowSettings(false)} />}
    </>);

}

function OverviewTab({
  isOwner, recentInvoices, recentExpenses, patientName, onGoInvoices, onGoPayments
}: {
  isOwner: boolean; recentInvoices: InvoiceResponse[]; recentExpenses: ExpenseResponse[];
  patientName: (id: string) => string; onGoInvoices: () => void; onGoPayments: () => void;
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-3xl border border-sand-200 bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold text-ink">Recent invoices</h3>
          <button type="button" onClick={onGoInvoices} className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">View all <ArrowUpRightIcon className="h-3 w-3" /></button>
        </div>
        {recentInvoices.length === 0 ?
        <p className="text-sm text-ink-muted">No invoices yet.</p> :
        <div className="divide-y divide-sand-100">
            {recentInvoices.map((inv) =>
          <Link key={inv.id} to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="flex items-center gap-3 py-2.5 transition-colors hover:opacity-80">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-600/10 text-teal-600"><ReceiptIcon className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{patientName(inv.patient_id)}</p>
              <p className="text-xs text-ink-muted">{formatDate(inv.due_date)}</p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${INVOICE_STATUS_CLASS[inv.status]}`}>{INVOICE_STATUS_LABEL[inv.status] || inv.status}</span>
            <span className="text-sm font-semibold text-ink tabular-nums">{formatMoney(inv.total_amount, inv.currency)}</span>
          </Link>
        )}
          </div>
        }
      </section>

      <section className="rounded-3xl border border-sand-200 bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-bold text-ink">Recent payments</h3>
          <button type="button" onClick={onGoPayments} className="flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">View all <ArrowUpRightIcon className="h-3 w-3" /></button>
        </div>
        {recentExpenses.length === 0 ?
        <p className="text-sm text-ink-muted">No payments recorded yet.</p> :
        <div className="divide-y divide-sand-100">
            {recentExpenses.map((e) =>
          <div key={e.id} className="flex items-center gap-3 py-2.5">
            <span className={`flex h-9 w-9 items-center justify-center rounded-xl ${TYPE_META[e.expense_type]?.className ?? "bg-sand-100 text-ink-soft"}`}><BanknoteIcon className="h-4 w-4" /></span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{e.payee_name || e.vendor || e.category}</p>
              <p className="text-xs text-ink-muted">{formatDate(e.expense_date)} · {TYPE_META[e.expense_type]?.label ?? "Expense"}</p>
            </div>
            <StatusBadge status={e.status} />
            <span className="text-sm font-semibold text-ink tabular-nums">{formatMoney(e.amount)}</span>
          </div>
        )}
          </div>
        }
        {isOwner &&
      <button type="button" onClick={onGoPayments} className="mt-3 w-full rounded-xl border border-dashed border-sand-300 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
          + Manage payments
        </button>
        }
      </section>
    </div>);

}

function InvoicesTab({
  invoices, patientName
}: {
  invoices: InvoiceResponse[]; patientName: (id: string) => string;
}) {
  if (invoices.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState icon={ReceiptIcon} title="No invoices yet" body="Raise one to start tracking revenue." />
      </div>);
  }
  return (
    <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_6px_24px_rgba(15,23,42,0.06)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead>
            <tr className="border-b border-sand-200 bg-sand-50/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
              <th className="px-5 py-3.5">Patient</th>
              <th className="px-5 py-3.5">Total</th>
              <th className="px-5 py-3.5">Balance due</th>
              <th className="px-5 py-3.5">Status</th>
              <th className="px-5 py-3.5">Due</th>
              <th className="px-5 py-3.5 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-sand-100">
            {invoices.map((inv) =>
          <tr key={inv.id} className="transition-colors hover:bg-sand-50">
            <td className="px-5 py-3.5 font-medium text-ink">
              <Link to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="hover:underline">{patientName(inv.patient_id)}</Link>
            </td>
            <td className="px-5 py-3.5 font-semibold text-ink tabular-nums">{formatMoney(inv.total_amount, inv.currency)}</td>
            <td className="px-5 py-3.5 text-ink-soft tabular-nums">{inv.balance_due > 0 ? formatMoney(inv.balance_due, inv.currency) : "—"}</td>
            <td className="px-5 py-3.5"><span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${INVOICE_STATUS_CLASS[inv.status]}`}>{INVOICE_STATUS_LABEL[inv.status] || inv.status}</span></td>
            <td className="px-5 py-3.5 text-ink-soft">{formatDate(inv.due_date)}</td>
            <td className="px-5 py-3.5 text-right">
              <Link to={DASHBOARD_ROUTES.invoiceDetail(inv.id)} className="inline-flex items-center gap-1.5 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-teal-700">
                <CreditCardIcon className="h-3.5 w-3.5" /> {inv.balance_due > 0 ? "Collect" : "View"}
              </Link>
            </td>
          </tr>
        )}
          </tbody>
        </table>
      </div>
    </div>);

}

function PaymentsTab({
  isOwner, expenses, onAdd, onPaySalary, onUpdate, onDelete
}: {
  isOwner: boolean; expenses: ExpenseResponse[];
  onAdd: () => void; onPaySalary: () => void;
  onUpdate: (id: string, data: Partial<CreateExpenseData>) => Promise<unknown>;
  onDelete: (id: string) => Promise<void>;
}) {
  const readOnly = !isOwner;
  if (expenses.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState icon={BanknoteIcon} title="No payments recorded" body="Record an expense, refund, or pay a salary to see money going out." />
      </div>);
  }
  return (
    <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_6px_24px_rgba(15,23,42,0.06)]">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[800px] text-left text-sm">
          <thead>
            <tr className="border-b border-sand-200 bg-sand-50/60 text-xs font-semibold uppercase tracking-wide text-ink-muted">
              <th className="px-5 py-3.5">Type</th>
              <th className="px-5 py-3.5">To / Description</th>
              <th className="px-5 py-3.5">Date</th>
              <th className="px-5 py-3.5">Status</th>
              <th className="px-5 py-3.5">Amount</th>
              {isOwner && <th className="px-5 py-3.5 text-right">Action</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-sand-100">
            {expenses.map((e) => readOnly ?
        <tr key={e.id} className="hover:bg-sand-50">
          <td className="px-5 py-3.5"><TypeBadge type={e.expense_type} /></td>
          <td className="px-5 py-3.5">
            <p className="font-medium text-ink">{e.payee_name || e.vendor || e.category}</p>
            <p className="text-xs text-ink-muted">{e.notes || e.category}</p>
          </td>
          <td className="px-5 py-3.5 text-ink-soft">{formatDate(e.expense_date)}</td>
          <td className="px-5 py-3.5"><StatusBadge status={e.status} /></td>
          <td className="px-5 py-3.5 font-semibold text-ink tabular-nums">{formatMoney(e.amount)}</td>
        </tr> :

        <ExpenseRow key={e.id} expense={e} onUpdate={onUpdate} onDelete={onDelete} />
        )}
          </tbody>
        </table>
      </div>
      {isOwner &&
      <div className="flex flex-wrap gap-2.5 border-t border-sand-200 bg-sand-50/50 px-5 py-3.5">
          <button type="button" onClick={onAdd} className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600"><PlusIcon className="h-3.5 w-3.5" /> Record payment</button>
          <button type="button" onClick={onPaySalary} className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-soft hover:border-[#7C3AED]/40 hover:text-[#7C3AED]"><UserPlusIcon className="h-3.5 w-3.5" /> Pay salary</button>
        </div>
      }
    </div>);

}

// In the payments table we don't need inline edit-row complexity from before;
// keep it simple here with paid-toggle + delete (owner).
function ExpenseRow({
  expense, onUpdate, onDelete
}: {
  expense: ExpenseResponse;
  onUpdate: (id: string, data: Partial<CreateExpenseData>) => Promise<unknown>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  async function togglePaid() {
    await onUpdate(expense.id, { status: expense.status === "paid" ? "pending" : "paid", paid_at: expense.status === "paid" ? null : new Date().toISOString() });
  }

  return (
    <tr className="hover:bg-sand-50">
      <td className="px-5 py-3.5"><TypeBadge type={expense.expense_type} /></td>
      <td className="px-5 py-3.5">
        <p className="font-medium text-ink">{expense.payee_name || expense.vendor || expense.category}</p>
        <p className="text-xs text-ink-muted">{expense.notes || expense.category}</p>
      </td>
      <td className="px-5 py-3.5 text-ink-soft">{formatDate(expense.expense_date)}</td>
      <td className="px-5 py-3.5">
        <button type="button" onClick={togglePaid} title="Toggle paid"><StatusBadge status={expense.status} /></button>
      </td>
      <td className="px-5 py-3.5 font-semibold text-ink tabular-nums">{formatMoney(expense.amount)}</td>
      <td className="px-5 py-3.5 text-right">
        {confirmingDelete ?
        <button type="button" onClick={() => onDelete(expense.id)} className="rounded-lg bg-danger px-2.5 py-1.5 text-[11px] font-semibold text-white">Confirm</button> :
        <button type="button" onClick={() => setConfirmingDelete(true)} className="ml-auto flex h-7 w-7 items-center justify-center rounded-lg text-ink-muted hover:bg-danger/10 hover:text-danger"><TrashIcon className="h-3.5 w-3.5" /></button>
        }
      </td>
    </tr>);

}

/* ---------------- Wallet / practice credits ---------------- */

function WalletTab({ authedFetch, baseCurrency }: { authedFetch: AuthedFetch; baseCurrency: string }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [balance, setBalance] = useState<WalletBalanceResponse | null>(null);
  const [transactions, setTransactions] = useState<WalletTransactionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTopup, setShowTopup] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!authedFetch) return;
    try {
      const [b, t] = await Promise.all([getWalletBalance(authedFetch), listWalletTransactions(authedFetch)]);
      setBalance(b);
      setTransactions(t);
    } catch {
      setBalance(null);
      setTransactions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, [authedFetch]);

  useEffect(() => {
    const checkout = searchParams.get("checkout");
    const sessionId = searchParams.get("session_id");
    if (checkout !== "success" || !sessionId || !authedFetch) return;
    setConfirming(true);
    confirmWalletCheckoutSession(authedFetch, sessionId)
      .then(async () => { await refresh(); })
      .catch((err: unknown) => setError(err instanceof Error && err.message ? err.message : "Couldn't confirm top-up."))
      .finally(() => {
        setConfirming(false);
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.delete("checkout");
          next.delete("session_id");
          return next;
        }, { replace: true });
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return <p className="text-sm text-ink-muted">Loading…</p>;

  return (
    <div className="space-y-6">
      {confirming && <p className="rounded-2xl border border-teal-600/20 bg-teal-600/5 px-4 py-3 text-sm font-medium text-teal-700">Confirming your top-up…</p>}
      {error && <p className="text-sm font-medium text-danger">{error}</p>}

      <div className="overflow-hidden rounded-3xl border border-teal-600/15 bg-gradient-to-br from-[#0D9488] to-[#0F766E] p-6 text-white shadow-[0_10px_30px_rgba(13,148,136,0.25)]">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-white/70"><CoinsIcon className="h-3.5 w-3.5" /> Practice credits</p>
            <p className="mt-1.5 font-display text-4xl font-bold tabular-nums">{formatMoney(balance?.balance ?? 0, balance?.currency ?? baseCurrency)}</p>
            <p className="mt-1 text-xs text-white/70">Top up your account with a real card — funded via Stripe.</p>
          </div>
          <button
          type="button"
          onClick={() => setShowTopup(true)}
          className="flex items-center gap-1.5 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-teal-700 shadow-lg transition-transform hover:-translate-y-0.5">
            <PlusIcon className="h-4 w-4" /> Add credits
          </button>
        </div>
      </div>

      <div className="rounded-3xl border border-sand-200 bg-white p-5">
        <p className="mb-3 text-sm font-bold text-ink">Top-up history</p>
        {transactions.length === 0 ?
        <p className="text-sm text-ink-muted">No top-ups yet.</p> :
        <div className="divide-y divide-sand-100">
            {transactions.map((t) =>
          <div key={t.id} className="flex items-center justify-between gap-3 py-2.5">
              <div>
                <p className="text-sm font-medium text-ink">{t.description || "Top-up"}</p>
                <p className="text-xs text-ink-muted">{formatDate(t.created_at)}</p>
              </div>
              <div className="flex items-center gap-2.5">
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${t.status === "completed" ? "bg-success/10 text-success" : t.status === "failed" ? "bg-danger/10 text-danger" : "bg-sand-100 text-ink-soft"}`}>{t.status}</span>
                <span className="text-sm font-semibold text-ink tabular-nums">+{formatMoney(t.amount, t.currency)}</span>
              </div>
            </div>
          )}
          </div>
        }
      </div>

      {showTopup &&
      <TopupModal authedFetch={authedFetch} currency={balance?.currency ?? baseCurrency} onClose={() => setShowTopup(false)} />}
    </div>);

}

function TopupModal({ authedFetch, currency, onClose }: { authedFetch: AuthedFetch; currency: string; onClose: () => void }) {
  const [amount, setAmount] = useState("50");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch || !amount) return;
    setSaving(true);
    setError(null);
    try {
      const session = await createWalletCheckoutSession(authedFetch, Number(amount));
      window.location.href = session.url;
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't start checkout — try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Add credits" subtitle="Top up your practice's account via Stripe" onClose={onClose}>
      <form onSubmit={submit}>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Amount ({currency}) *</span>
          <input required type="number" min="1" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
        <div className="mt-3 flex gap-2">
          {[25, 50, 100, 250].map((v) =>
        <button key={v} type="button" onClick={() => setAmount(String(v))} className="flex-1 rounded-xl border border-sand-200 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
              {formatMoney(v, currency)}
            </button>
        )}
        </div>
        {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
        <button type="submit" disabled={saving || !amount} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-40">
          <CreditCardIcon className="h-4 w-4" /> {saving ? "Starting…" : "Continue to Stripe"}
        </button>
      </form>
    </Modal>);

}

/* ---------------- Finance settings (owner) ---------------- */

function FinanceSettingsModal({
  settings, authedFetch, onSaved, onClose
}: {
  settings: FinanceSettingsResponse; authedFetch: AuthedFetch; onSaved: (s: FinanceSettingsResponse) => void; onClose: () => void;
}) {
  const [baseCurrency, setBaseCurrency] = useState(settings.base_currency);
  const [rate, setRate] = useState(settings.usd_to_pkr_rate != null ? String(settings.usd_to_pkr_rate) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateFinanceSettings(authedFetch, {
        base_currency: baseCurrency,
        ...(rate ? { usd_to_pkr_rate: Number(rate) } : {})
      });
      onSaved(updated);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Finance settings" subtitle="Base currency and manual exchange rate for multi-currency billing" onClose={onClose}>
      <form onSubmit={submit}>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Base currency</span>
          <select value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40">
            <option value="USD">USD</option>
            <option value="PKR">PKR</option>
          </select>
        </label>
        <label className="mt-3 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">1 USD = ? PKR</span>
          <input type="number" min="0" step="0.01" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="e.g. 280" className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          <p className="mt-1.5 text-xs text-ink-muted">Set manually — no external rate feed. Invoices in the non-base currency use this rate at the moment they're raised.</p>
        </label>
        {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
        <button type="submit" disabled={saving} className="mt-5 w-full rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-40">
          {saving ? "Saving…" : "Save settings"}
        </button>
      </form>
    </Modal>);

}

/* ---------------- Modal wrapper ---------------- */

function Modal({ title, subtitle, onClose, children }: { title: string; subtitle?: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-ink">{title}</h3>
            {subtitle && <p className="mt-0.5 text-sm text-ink-muted">{subtitle}</p>}
          </div>
          <button type="button" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100"><XIcon className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>);

}

/* ---------------- Record payment modal (expense/refund) ---------------- */

interface CreateExpenseData {
  expense_type?: string; status?: string; category: string; amount: number;
  vendor?: string | null; payee_name?: string | null; expense_date: string; notes?: string | null;
  paid_at?: string | null;
}

function AddExpenseModal({
  staff, onCreate, onRefresh, onClose
}: {
  staff: StaffResponse[]; onCreate: (d: CreateExpenseData) => Promise<unknown>;
  onRefresh: () => Promise<void>; onClose: () => void;
}) {
  const [type, setType] = useState("expense");
  const [category, setCategory] = useState("Supplies");
  const [payeeName, setPayeeName] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!amount || !category.trim()) return;
    setSaving(true); setError(null);
    try {
      await onCreate({ expense_type: type, status: "paid", category: category.trim(), amount: Number(amount), payee_name: payeeName.trim() || null, expense_date: date, notes: notes.trim() || null });
      await onRefresh();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Record payment" subtitle="Log money going out — a cost, a refund, or something else" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="grid grid-cols-3 gap-2.5">
          {TYPE_OPTIONS.map((t) =>
        <button key={t} type="button" onClick={() => setType(t)} className={`rounded-xl border px-3 py-2.5 text-sm font-semibold capitalize transition-colors ${type === t ? "border-teal-600 bg-teal-600/8 text-teal-600" : "border-sand-200 text-ink-soft hover:border-teal-600/40"}`}>
          {TYPE_META[t].label}
        </button>
        )}
        </div>

        <label className="mt-4 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Category *</span>
          <input required value={category} onChange={(e) => setCategory(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>

        {type === "refund" &&
      <label className="mt-3 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Refund to (patient / vendor)</span>
          <input value={payeeName} onChange={(e) => setPayeeName(e.target.value)} placeholder="Patient name" className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
        }
        {type === "salary" &&
      <label className="mt-3 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Staff member</span>
          <select value={payeeName} onChange={(e) => setPayeeName(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40">
            <option value="">Select…</option>
            {staff.map((s) => <option key={s.id} value={s.name || s.email}>{s.name || s.email} ({s.role})</option>)}
          </select>
        </label>
        }
        {type === "expense" &&
      <label className="mt-3 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Vendor</span>
          <input value={payeeName} onChange={(e) => setPayeeName(e.target.value)} placeholder="Supplier name" className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
        }

        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Amount ($) *</span>
            <input required type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Date *</span>
            <input required type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
        </div>

        <label className="mt-3 block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Notes</span>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>

        {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

        <button type="submit" disabled={saving || !amount || !category.trim()} className="mt-5 w-full rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-40">
          {saving ? "Saving…" : "Record payment"}
        </button>
      </form>
    </Modal>);

}

/* ---------------- Pay salary modal ---------------- */

function PaySalaryModal({
  staff, onCreate, onRefresh, onClose
}: {
  staff: StaffResponse[]; onCreate: (d: CreateExpenseData) => Promise<unknown>;
  onRefresh: () => Promise<void>; onClose: () => void;
}) {
  const [payeeName, setPayeeName] = useState("");
  const [amount, setAmount] = useState("");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!payeeName || !amount) return;
    setSaving(true); setError(null);
    try {
      await onCreate({ expense_type: "salary", status: "paid", category: "Salary", amount: Number(amount), payee_name: payeeName, expense_date: `${month}-01`, notes: `Salary for ${month}` });
      await onRefresh();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't pay salary — try again.");
      setSaving(false);
    }
  }

  return (
    <Modal title="Pay salary" subtitle="Record a salary payment for a doctor or staff member" onClose={onClose}>
      <form onSubmit={submit}>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Staff member *</span>
          <select required value={payeeName} onChange={(e) => setPayeeName(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-[#7C3AED]/40">
            <option value="">Select doctor / staff…</option>
            {staff.map((s) => <option key={s.id} value={s.name || s.email}>{s.name || s.email} ({s.role})</option>)}
          </select>
        </label>
        <div className="mt-3 grid grid-cols-2 gap-3">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Salary ($) *</span>
            <input required type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-[#7C3AED]/40" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Month *</span>
            <input required type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-[#7C3AED]/40" />
          </label>
        </div>
        {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
        <button type="submit" disabled={saving || !payeeName || !amount} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#7C3AED] px-4 py-3 text-sm font-semibold text-white hover:bg-[#6D28D9] disabled:opacity-40">
          <UserPlusIcon className="h-4 w-4" /> {saving ? "Paying…" : "Pay salary"}
        </button>
      </form>
    </Modal>);

}
