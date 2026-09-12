import React, { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon, CheckIcon, DownloadIcon, CreditCardIcon, PlusIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import {
  getInvoice, updateInvoice, recordInvoicePayment, createInvoiceCheckoutSession, confirmInvoiceCheckoutSession,
  fetchInvoicePdfBlob, type InvoiceResponse, type RecordPaymentRequest
} from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { formatMoney, formatDate } from "../finance/money";

const STATUS_CLASS: Record<string, string> = {
  pending: "bg-sand-100 text-ink-soft",
  partially_paid: "bg-[#7C3AED]/10 text-[#7C3AED]",
  paid: "bg-success/10 text-success",
  overdue: "bg-danger/10 text-danger",
  cancelled: "bg-ink-muted/10 text-ink-muted",
  refunded: "bg-warning/10 text-warning"
};

const STATUS_LABEL: Record<string, string> = { partially_paid: "Partially paid" };

// "paid" is deliberately not a manual target here — it's only ever reached
// by an actual recorded payment covering the balance (see record_payment's
// auto status recompute), never a button click that skips the ledger.
const NEXT_STATUSES: Record<string, InvoiceResponse["status"][]> = {
  pending: ["overdue", "cancelled"],
  partially_paid: ["cancelled"],
  overdue: ["cancelled"],
  paid: ["refunded"],
  cancelled: [],
  refunded: []
};

const METHOD_LABEL: Record<string, string> = {
  cash: "Cash", card_manual: "Card (in person)", bank_transfer: "Bank transfer", stripe: "Stripe", other: "Other"
};

export function InvoiceDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { authedFetch, authedFetchBlob, role } = usePlan();
  const { patients } = usePatients(authedFetch);
  const [invoice, setInvoice] = useState<InvoiceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingStatus, setSavingStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [showRecordPayment, setShowRecordPayment] = useState(false);
  const [payingOnline, setPayingOnline] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const canManage = role === "owner" || role === "receptionist";

  async function refetch() {
    if (!authedFetch || !id) return;
    const data = await getInvoice(authedFetch, id);
    setInvoice(data);
    return data;
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || !id) {
        setLoading(false);
        return;
      }
      try {
        const data = await getInvoice(authedFetch, id);
        if (!cancelled) setInvoice(data);
      } catch {
        if (!cancelled) setInvoice(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, id]);

  // After Stripe Checkout redirects back with ?checkout=success&session_id=...
  // (see BillingController.create_checkout_session's success_url) — confirm
  // it against the backend so the payment shows up even if the webhook
  // hasn't fired yet (local dev has no public URL for Stripe to call).
  useEffect(() => {
    const checkout = searchParams.get("checkout");
    const sessionId = searchParams.get("session_id");
    if (checkout !== "success" || !sessionId || !authedFetch || !id) return;
    setConfirming(true);
    confirmInvoiceCheckoutSession(authedFetch, id, sessionId)
      .then(setInvoice)
      .catch((err: unknown) => setError(err instanceof Error && err.message ? err.message : "Couldn't confirm payment."))
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

  async function transitionTo(status: InvoiceResponse["status"]) {
    if (!invoice || !authedFetch) return;
    setSavingStatus(status);
    setError(null);
    try {
      const updated = await updateInvoice(authedFetch, invoice.id, { status });
      setInvoice(updated);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't update this invoice — try again.");
    } finally {
      setSavingStatus(null);
    }
  }

  async function payOnline() {
    if (!invoice || !authedFetch) return;
    setPayingOnline(true);
    setError(null);
    try {
      const session = await createInvoiceCheckoutSession(authedFetch, invoice.id);
      window.location.href = session.url;
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't start online payment.");
      setPayingOnline(false);
    }
  }

  async function downloadPdf() {
    if (!invoice || !authedFetchBlob) return;
    setDownloadingPdf(true);
    try {
      const blob = await fetchInvoicePdfBlob(authedFetchBlob, invoice.id);
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      setError("Couldn't generate the PDF — try again.");
    } finally {
      setDownloadingPdf(false);
    }
  }

  if (loading) return null;

  if (!invoice) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center">
        <p className="text-sm font-semibold text-ink">Invoice not found</p>
      </div>);

  }

  const patient = patients.find((p) => p.id === invoice.patient_id);
  const nextStatuses = NEXT_STATUSES[invoice.status] || [];
  const isSettled = invoice.status === "cancelled" || invoice.status === "refunded";

  return (
    <>
      <Link
        to={patient ? DASHBOARD_ROUTES.patientDetail(patient.id) : DASHBOARD_ROUTES.invoices}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <PageHeader title={patient ? `Invoice — ${patient.name}` : "Invoice"} subtitle={`Created ${formatDate(invoice.created_at)} · #${invoice.id.slice(0, 8).toUpperCase()}`} />
        <div className="flex shrink-0 items-center gap-2.5">
          <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${STATUS_CLASS[invoice.status]}`}>
            {STATUS_LABEL[invoice.status] || invoice.status}
          </span>
          <button
            type="button"
            onClick={downloadPdf}
            disabled={downloadingPdf}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
            <DownloadIcon className="h-3.5 w-3.5" /> {downloadingPdf ? "Generating…" : "Download PDF"}
          </button>
        </div>
      </div>

      {confirming && <p className="mb-4 rounded-2xl border border-teal-600/20 bg-teal-600/5 px-4 py-3 text-sm font-medium text-teal-700">Confirming your payment…</p>}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="divide-y divide-sand-100">
            {invoice.line_items.map((line) =>
            <div key={line.id} className="flex items-center justify-between gap-3 px-5 py-3.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{line.description}</p>
                  <p className="text-xs text-ink-muted">{line.quantity} × {formatMoney(line.unit_price, invoice.currency)}</p>
                </div>
                <p className="shrink-0 text-sm font-semibold text-ink">{formatMoney(line.quantity * line.unit_price, invoice.currency)}</p>
              </div>
            )}
          </div>
          <div className="space-y-1.5 border-t border-sand-200 px-5 py-4">
            <div className="flex items-center justify-between text-sm text-ink-soft">
              <span>Subtotal</span><span>{formatMoney(invoice.subtotal_amount, invoice.currency)}</span>
            </div>
            <div className="flex items-center justify-between text-sm text-ink-soft">
              <span>Tax</span><span>{formatMoney(invoice.tax_amount, invoice.currency)}</span>
            </div>
            <div className="flex items-center justify-between text-sm text-ink-soft">
              <span>Discount</span><span>-{formatMoney(invoice.discount_amount, invoice.currency)}</span>
            </div>
            <div className="flex items-center justify-between border-t border-sand-100 pt-1.5 text-sm font-bold text-ink">
              <span>Total</span><span>{formatMoney(invoice.total_amount, invoice.currency)}</span>
            </div>
            {invoice.amount_paid > 0 &&
            <div className="flex items-center justify-between text-sm font-semibold text-success">
                <span>Paid</span><span>{formatMoney(invoice.amount_paid, invoice.currency)}</span>
              </div>
            }
            {!isSettled &&
            <div className="flex items-center justify-between border-t border-sand-100 pt-1.5 text-sm font-bold text-ink">
                <span>Balance due</span><span>{formatMoney(invoice.balance_due, invoice.currency)}</span>
              </div>
            }
            {invoice.exchange_rate_to_base &&
            <p className="pt-1 text-xs text-ink-muted">Exchange rate at time of billing: 1 = {invoice.exchange_rate_to_base.toLocaleString(undefined, { maximumFractionDigits: 4 })} {invoice.currency}</p>
            }
            {invoice.due_date && <p className="pt-1 text-xs text-ink-muted">Due {formatDate(invoice.due_date)}</p>}
            {invoice.paid_at && <p className="pt-1 text-xs text-ink-muted">Fully paid {formatDate(invoice.paid_at)}</p>}
          </div>
        </div>

        <div className="space-y-4">
          {canManage && !isSettled && invoice.balance_due > 0 &&
          <div className="rounded-3xl border border-teal-600/15 bg-gradient-to-br from-teal-600/8 to-white p-5">
              <p className="text-sm font-bold text-ink">Collect payment</p>
              <p className="mt-0.5 text-xs text-ink-muted">{formatMoney(invoice.balance_due, invoice.currency)} outstanding</p>
              <button
              type="button"
              onClick={payOnline}
              disabled={payingOnline}
              className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-50">
                <CreditCardIcon className="h-4 w-4" /> {payingOnline ? "Starting…" : "Pay online (Stripe)"}
              </button>
              <button
              type="button"
              onClick={() => setShowRecordPayment(true)}
              className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-xl border border-sand-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
                <PlusIcon className="h-4 w-4" /> Record a payment
              </button>
            </div>
          }

          <div className="rounded-3xl border border-sand-200 bg-white p-5">
            <p className="mb-3 text-sm font-bold text-ink">Payment history</p>
            {invoice.payments.length === 0 ?
            <p className="text-sm text-ink-muted">No payments recorded yet.</p> :
            <div className="space-y-2.5">
                {invoice.payments.map((p) =>
              <div key={p.id} className="flex items-center justify-between gap-2 border-b border-sand-100 pb-2.5 last:border-0 last:pb-0">
                    <div>
                      <p className="text-sm font-medium text-ink">{formatMoney(p.amount, p.currency)}</p>
                      <p className="text-xs text-ink-muted">{METHOD_LABEL[p.method] || p.method} · {formatDate(p.paid_at)}</p>
                    </div>
                  </div>
              )}
              </div>
            }
          </div>
        </div>
      </div>

      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

      {canManage && nextStatuses.length > 0 &&
      <div className="mt-5 flex flex-wrap items-center justify-end gap-2.5">
          {nextStatuses.map((status) =>
        <button
          key={status}
          type="button"
          onClick={() => transitionTo(status)}
          disabled={savingStatus !== null}
          className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40 disabled:cursor-not-allowed disabled:opacity-40">
              {savingStatus === status ? "Saving…" : `Mark ${STATUS_LABEL[status] || status}`}
            </button>
        )}
        </div>
      }

      {showRecordPayment && invoice &&
      <RecordPaymentModal
        invoice={invoice}
        authedFetch={authedFetch}
        onClose={() => setShowRecordPayment(false)}
        onRecorded={async () => { await refetch(); setShowRecordPayment(false); }} />
      }
    </>);

}

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

function RecordPaymentModal({
  invoice, authedFetch, onClose, onRecorded
}: {
  invoice: InvoiceResponse; authedFetch: AuthedFetch; onClose: () => void; onRecorded: () => Promise<void>;
}) {
  const [amount, setAmount] = useState(String(invoice.balance_due));
  const [method, setMethod] = useState<RecordPaymentRequest["method"]>("cash");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch || !amount) return;
    setSaving(true);
    setError(null);
    try {
      await recordInvoicePayment(authedFetch, invoice.id, { amount: Number(amount), method, notes: notes.trim() || undefined });
      await onRecorded();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't record this payment — try again.");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold text-ink">Record a payment</h3>
            <p className="mt-0.5 text-sm text-ink-muted">{formatMoney(invoice.balance_due, invoice.currency)} outstanding</p>
          </div>
          <button type="button" onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100"><XIcon className="h-4 w-4" /></button>
        </div>
        <form onSubmit={submit}>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Amount ({invoice.currency}) *</span>
            <input required type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="mt-3 block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Method</span>
            <select value={method} onChange={(e) => setMethod(e.target.value as RecordPaymentRequest["method"])} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40">
              <option value="cash">Cash</option>
              <option value="card_manual">Card (in person)</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label className="mt-3 block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Notes</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
          <button type="submit" disabled={saving || !amount} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-teal-600 px-4 py-3 text-sm font-semibold text-white hover:bg-teal-700 disabled:opacity-40">
            <CheckIcon className="h-4 w-4" /> {saving ? "Recording…" : "Record payment"}
          </button>
        </form>
      </div>
    </div>);

}
