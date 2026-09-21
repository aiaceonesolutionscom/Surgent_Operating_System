import { useEffect, useMemo, useState } from "react";
import { RotateCcwIcon, CheckIcon, XIcon, BanknoteIcon, ClockIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import {
  listRefundRequests, approveRefundRequest, rejectRefundRequest, completeRefundRequest,
  type RefundRequestResponse
} from "../../../api/entities";
import { formatMoney, formatDate } from "./money";

const STATUS_CLASS: Record<string, string> = {
  requested: "bg-warning/10 text-warning",
  approved: "bg-[#7C3AED]/10 text-[#7C3AED]",
  rejected: "bg-danger/10 text-danger",
  completed: "bg-success/10 text-success",
  cancelled: "bg-ink-muted/10 text-ink-muted"
};

const SOURCE_LABEL: Record<string, string> = {
  ai_receptionist: "AI receptionist",
  patient_portal: "Patient portal",
  staff: "Front desk"
};

type Tab = "pending" | "history";

// Owner/Receptionist-only queue for refund/cancellation requests — the AI
// receptionist can only FILE one of these (see inbound_service.py's
// request_refund_or_cancellation tool), never approve or complete it.
// REQUESTED -> APPROVED (decision, money not moved) -> COMPLETED (a real
// reversing payment recorded) are deliberately separate steps.
export function RefundRequestsPage() {
  const { authedFetch } = usePlan();
  const { patients } = usePatients(authedFetch);
  const [requests, setRequests] = useState<RefundRequestResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("pending");

  async function load() {
    if (!authedFetch) { setLoading(false); return; }
    try {
      setLoading(true);
      const data = await listRefundRequests(authedFetch);
      setRequests(data);
    } catch {
      setRequests([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  const patientName = (id: string) => patients.find((p) => p.id === id)?.name || "Unknown patient";

  const pending = useMemo(() => requests.filter((r) => r.status === "requested" || r.status === "approved"), [requests]);
  const history = useMemo(() => requests.filter((r) => r.status === "rejected" || r.status === "completed" || r.status === "cancelled"), [requests]);
  const shown = tab === "pending" ? pending : history;

  async function refresh() {
    await load();
  }

  return (
    <>
      <PageHeader
        title="Refund requests"
        subtitle="Every cancellation/refund a patient asked for — through the AI receptionist, the portal, or front desk — lands here for a real decision. Nothing is approved automatically." />

      <div className="mt-6 flex gap-1 border-b border-sand-200">
        {(["pending", "history"] as Tab[]).map((t) =>
        <button
          key={t}
          type="button"
          onClick={() => setTab(t)}
          className={`flex items-center gap-1.5 rounded-t-xl px-4 py-2.5 text-sm font-semibold capitalize transition-colors ${tab === t ? "border-b-2 border-teal-600 text-teal-600" : "text-ink-muted hover:text-ink"}`}>
            {t === "pending" ? `Pending${pending.length ? ` (${pending.length})` : ""}` : "History"}
          </button>
        )}
      </div>

      <div className="mt-6">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        shown.length === 0 ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState
            icon={RotateCcwIcon}
            title={tab === "pending" ? "Nothing waiting for review" : "No history yet"}
            body={tab === "pending" ? "Refund/cancellation requests from the AI receptionist, portal, or front desk will show up here." : "Reviewed requests will show up here."} />
          </div> :

        <div className="space-y-4">
            {shown.map((r) =>
          <RequestCard key={r.id} request={r} patientName={patientName(r.patient_id)} onChanged={refresh} />
          )}
          </div>
        }
      </div>
    </>);

}

function CalculationBasis({ basis }: { basis: Record<string, unknown> | null }) {
  if (!basis) return null;
  if (basis.formula === "pro_rata") {
    return (
      <p className="mt-1.5 text-xs text-ink-muted">
        Pro-rata suggestion: {String(basis.sessions_completed)}/{String(basis.sessions_total)} sessions completed,{" "}
        {String(basis.sessions_remaining)} remaining, of {formatMoney(Number(basis.item_total ?? 0))} for this item
        {basis.amount_paid != null ? ` (capped at ${formatMoney(Number(basis.amount_paid))} actually paid)` : ""}.
      </p>);

  }
  if (basis.formula === "manual" && basis.amount_paid != null) {
    return <p className="mt-1.5 text-xs text-ink-muted">{formatMoney(Number(basis.amount_paid))} paid on the linked invoice so far.</p>;
  }
  if (basis.note) {
    return <p className="mt-1.5 text-xs text-ink-muted">{String(basis.note)}</p>;
  }
  return null;
}

function RequestCard({
  request, patientName, onChanged
}: {
  request: RefundRequestResponse; patientName: string; onChanged: () => Promise<void>;
}) {
  const { authedFetch } = usePlan();
  const [amount, setAmount] = useState(String(request.approved_amount ?? request.requested_amount ?? ""));
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approve() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await approveRefundRequest(authedFetch, request.id, amount ? Number(amount) : null, notes.trim() || null);
      await onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't approve — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await rejectRefundRequest(authedFetch, request.id, notes.trim() || null);
      await onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't reject — try again.");
    } finally {
      setBusy(false);
    }
  }

  async function complete() {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      await completeRefundRequest(authedFetch, request.id);
      await onChanged();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't mark as processed — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-sm font-bold text-ink">
            {patientName}
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[request.status]}`}>{request.status}</span>
          </p>
          <p className="mt-1 text-xs text-ink-muted">
            Filed via {SOURCE_LABEL[request.requested_by_type] || request.requested_by_type} · {formatDate(request.created_at)}
          </p>
          {request.reason && <p className="mt-2 max-w-xl text-sm text-ink-soft">"{request.reason}"</p>}
          <CalculationBasis basis={request.calculation_basis} />
          {request.review_notes && <p className="mt-1.5 text-xs text-ink-muted">Reviewer note: {request.review_notes}</p>}
        </div>
        <div className="text-right">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
            {request.status === "requested" ? "Suggested amount" : request.status === "approved" ? "Approved amount" : "Amount"}
          </p>
          <p className="font-display text-xl font-bold text-ink tabular-nums">
            {formatMoney(request.approved_amount ?? request.requested_amount ?? 0)}
          </p>
        </div>
      </div>

      {request.status === "requested" &&
      <div className="mt-4 rounded-2xl border border-sand-200 bg-sand-50/50 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Amount to approve</span>
              <input
              type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
              placeholder={request.requested_amount == null ? "No auto-calculated figure — enter one" : undefined}
              className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Note (optional)</span>
              <input value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40" />
            </label>
          </div>
          {error && <p className="mt-2 text-sm font-medium text-danger">{error}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={reject} disabled={busy} className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-muted hover:text-danger disabled:opacity-50">
              <XIcon className="h-3.5 w-3.5" /> Reject
            </button>
            <button type="button" onClick={approve} disabled={busy || !amount} className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
              <CheckIcon className="h-3.5 w-3.5" /> {busy ? "Saving…" : "Approve"}
            </button>
          </div>
        </div>
      }

      {request.status === "approved" &&
      <div className="mt-4 rounded-2xl border border-[#7C3AED]/20 bg-[#7C3AED]/[0.04] p-4">
          <p className="flex items-center gap-1.5 text-xs text-ink-soft"><ClockIcon className="h-3.5 w-3.5" /> Approved — money hasn't actually moved yet. Mark it processed once the refund is really paid out (cash, transfer, POS reversal).</p>
          {error && <p className="mt-2 text-sm font-medium text-danger">{error}</p>}
          <div className="mt-3 flex justify-end">
            <button type="button" onClick={complete} disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-[#7C3AED] px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-[#6D28D9] disabled:opacity-50">
              <BanknoteIcon className="h-3.5 w-3.5" /> {busy ? "Processing…" : "Mark refund as processed"}
            </button>
          </div>
        </div>
      }
    </div>);

}
