import { useEffect, useState } from "react";
import { Loader2Icon, CheckIcon, XIcon, Building2Icon } from "lucide-react";
import { listOrgRequests, approveOrgRequest, rejectOrgRequest, type OrgRequestListItem } from "../../../api/admin";

// The Super Admin's new-organization approval queue — every free /sign-up
// (no invite/apply code) files a PendingSignup here (see
// backend/src/services/practice/org_request_service.py) instead of getting
// any practice/dashboard access. Approving provisions a real, isolated
// Practice + Owner account; rejecting just records the decision.
export function OrgRequestsListPage() {
  const [rows, setRows] = useState<OrgRequestListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [selectedPlan, setSelectedPlan] = useState<Record<string, "practice" | "enterprise">>({});

  async function load() {
    try {
      const list = await listOrgRequests();
      setRows(list);
    } catch {
      setError("Couldn't load organization requests.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleApprove(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await approveOrgRequest(id, selectedPlan[id] ?? null);
      await load();
    } catch {
      setError("Couldn't approve — try again.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await rejectOrgRequest(id, reason || undefined);
      setRejectingId(null);
      setReason("");
      await load();
    } catch {
      setError("Couldn't reject — try again.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">New organizations</p>
        <h1 className="font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">Pending approval</h1>
        <p className="text-sm text-ink-muted">
          Every brand-new signup (no invite, no plan chosen) lands here first — nothing gets a dashboard until you
          approve it.
        </p>
      </div>

      <div className="mt-6 overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        {error && <p className="p-6 text-sm text-danger">{error}</p>}
        {!rows && !error && (
          <div className="flex justify-center py-16">
            <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
          </div>
        )}
        {rows && rows.length === 0 && (
          <div className="flex flex-col items-center gap-2 p-16 text-center">
            <Building2Icon className="h-8 w-8 text-ink-muted" />
            <p className="text-sm text-ink-muted">No pending requests right now.</p>
          </div>
        )}
        {rows && rows.length > 0 && (
          <div className="divide-y divide-sand-100">
            {rows.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-ink">{r.org_name || "(no name yet)"}</p>
                  <p className="truncate text-xs text-ink-muted">
                    {r.email} · requested {new Date(r.created_at).toLocaleDateString()}
                  </p>
                </div>

                {rejectingId === r.id ? (
                  <div className="flex flex-1 min-w-[240px] items-center gap-2">
                    <input
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Reason (optional)"
                      className="flex-1 rounded-lg border border-sand-200 bg-canvas px-3 py-1.5 text-xs text-ink outline-none focus:border-accent-500/50 focus:bg-white"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setRejectingId(null);
                        setReason("");
                      }}
                      className="rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:bg-sand-100">
                      Cancel
                    </button>
                    <button
                      type="button"
                      disabled={busyId === r.id}
                      onClick={() => handleReject(r.id)}
                      className="flex items-center gap-1 rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50">
                      <XIcon className="h-3.5 w-3.5" /> {busyId === r.id ? "Rejecting…" : "Confirm reject"}
                    </button>
                  </div>
                ) : (
                  <div className="flex shrink-0 items-center gap-2">
                    <select
                      value={selectedPlan[r.id] ?? "practice"}
                      onChange={(e) => setSelectedPlan((m) => ({ ...m, [r.id]: e.target.value as "practice" | "enterprise" }))}
                      title="Plan the approved clinic starts on"
                      className="rounded-xl border border-sand-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-ink outline-none focus:border-accent-500/50">
                      <option value="practice">Practice plan</option>
                      <option value="enterprise">Enterprise plan</option>
                    </select>
                    <button
                      type="button"
                      onClick={() => setRejectingId(r.id)}
                      disabled={busyId === r.id}
                      className="flex items-center gap-1.5 rounded-xl border border-danger/25 px-3 py-1.5 text-xs font-semibold text-danger transition-colors hover:bg-danger/5 disabled:opacity-50">
                      <XIcon className="h-3.5 w-3.5" /> Reject
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApprove(r.id)}
                      disabled={busyId === r.id}
                      className="flex items-center gap-1.5 rounded-xl bg-accent-500 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-accent-600 disabled:opacity-50">
                      <CheckIcon className="h-3.5 w-3.5" /> {busyId === r.id ? "Approving…" : "Approve"}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
