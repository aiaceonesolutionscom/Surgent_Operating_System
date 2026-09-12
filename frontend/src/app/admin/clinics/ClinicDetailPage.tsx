import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeftIcon, Loader2Icon, MailIcon, PhoneIcon, MapPinIcon, CheckIcon, ChevronDownIcon, PencilIcon, XIcon } from "lucide-react";
import { getAdminPracticeDetail, updatePracticeSubscription, updateAdminPractice, suspendPractice, reactivatePractice, type AdminPracticeDetailResponse } from "../../../api/admin";
import { ADMIN_ROUTES } from "../constants/routes";

const TIER_LABEL: Record<string, string> = { solo: "Solo", practice: "Practice", enterprise: "Enterprise", custom: "Custom" };
const TIER_ORDER = ["practice", "enterprise"] as const;

const STATUS_LABEL: Record<string, string> = { active: "Active", suspended: "Suspended", pending_approval: "Pending approval" };
const STATUS_CLASS: Record<string, string> = {
  active: "bg-success/10 text-success",
  suspended: "bg-danger/10 text-danger",
  pending_approval: "bg-warning/10 text-warning"
};

function money(n: number) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function ClinicDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<AdminPracticeDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [planMenuOpen, setPlanMenuOpen] = useState(false);
  const [savingPlan, setSavingPlan] = useState(false);
  const [planError, setPlanError] = useState<string | null>(null);
  const [planSaved, setPlanSaved] = useState(false);
  const [confirmingSuspend, setConfirmingSuspend] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({ name: "", email: "" });
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  function openEdit() {
    if (!detail) return;
    setEditForm({ name: detail.name, email: detail.email });
    setEditError(null);
    setEditOpen(true);
  }

  async function handleEditSave() {
    if (!id) return;
    setEditBusy(true);
    setEditError(null);
    try {
      const updated = await updateAdminPractice(id, {
        name: editForm.name.trim() || undefined,
        email: editForm.email.trim() || undefined
      });
      setDetail(updated);
      setEditOpen(false);
    } catch {
      setEditError("Couldn't save changes — try again.");
    } finally {
      setEditBusy(false);
    }
  }

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getAdminPracticeDetail(id)
    .then((d) => {
      if (!cancelled) setDetail(d);
    })
    .catch(() => {
      if (!cancelled) setError("Couldn't load this clinic.");
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function changePlan(tier: string) {
    if (!id || !detail || tier === detail.plan_tier) {
      setPlanMenuOpen(false);
      return;
    }
    setSavingPlan(true);
    setPlanError(null);
    setPlanSaved(false);
    try {
      const updated = await updatePracticeSubscription(id, tier);
      setDetail(updated);
      setPlanMenuOpen(false);
      setPlanSaved(true);
      setTimeout(() => setPlanSaved(false), 3000);
    } catch {
      setPlanError("Couldn't change the plan. Please try again.");
    } finally {
      setSavingPlan(false);
    }
  }

  async function handleSuspend() {
    if (!id) return;
    setSavingStatus(true);
    setStatusError(null);
    try {
      const updated = await suspendPractice(id);
      setDetail(updated);
      setConfirmingSuspend(false);
    } catch {
      setStatusError("Couldn't suspend — try again.");
    } finally {
      setSavingStatus(false);
    }
  }

  async function handleReactivate() {
    if (!id) return;
    setSavingStatus(true);
    setStatusError(null);
    try {
      const updated = await reactivatePractice(id);
      setDetail(updated);
    } catch {
      setStatusError("Couldn't reactivate — try again.");
    } finally {
      setSavingStatus(false);
    }
  }

  return (
    <>
      <Link to={ADMIN_ROUTES.clinics} className="inline-flex items-center gap-1.5 text-sm font-semibold text-ink-muted hover:text-ink">
        <ArrowLeftIcon className="h-4 w-4" /> All clinics
      </Link>

      {error && <p className="mt-6 text-sm text-danger">{error}</p>}
      {!detail && !error &&
      <div className="mt-10 flex justify-center">
          <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
        </div>
      }

      {detail &&
      <>
          <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="font-display text-[26px] font-600 tracking-tight text-ink">{detail.name}</h1>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${STATUS_CLASS[detail.status] ?? STATUS_CLASS.active}`}>
                  {STATUS_LABEL[detail.status] ?? detail.status}
                </span>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-ink-muted">
                <span className="flex items-center gap-1.5"><MailIcon className="h-3.5 w-3.5" /> {detail.email}</span>
                {detail.phone && <span className="flex items-center gap-1.5"><PhoneIcon className="h-3.5 w-3.5" /> {detail.phone}</span>}
                {detail.address && <span className="flex items-center gap-1.5"><MapPinIcon className="h-3.5 w-3.5" /> {detail.address}</span>}
              </div>
              <div className="mt-3">
                {detail.status === "suspended" ? (
                  <button
                    type="button"
                    onClick={handleReactivate}
                    disabled={savingStatus}
                    className="flex items-center gap-1.5 rounded-lg border border-success/30 px-3 py-1.5 text-xs font-semibold text-success transition-colors hover:bg-success/5 disabled:opacity-50">
                    {savingStatus ? "Reactivating…" : "Reactivate this organization"}
                  </button>
                ) : confirmingSuspend ? (
                  <div className="flex items-center gap-2 rounded-xl border border-danger/25 bg-danger/[0.03] p-3">
                    <p className="text-xs text-ink-muted">Data stays intact — this just blocks their dashboard access.</p>
                    <button type="button" onClick={() => setConfirmingSuspend(false)} className="rounded-lg border border-sand-200 px-2.5 py-1 text-xs font-semibold text-ink-soft hover:bg-sand-100">
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleSuspend}
                      disabled={savingStatus}
                      className="rounded-lg bg-danger px-2.5 py-1 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50">
                      {savingStatus ? "Suspending…" : "Confirm suspend"}
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmingSuspend(true)}
                    className="flex items-center gap-1.5 rounded-lg border border-danger/25 px-3 py-1.5 text-xs font-semibold text-danger transition-colors hover:bg-danger/5">
                    Suspend this organization
                  </button>
                )}
                {statusError && <p className="mt-1.5 text-xs text-danger">{statusError}</p>}
              </div>
            </div>

            <div className="relative flex flex-col items-end gap-2">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center rounded-full bg-accent-500/10 px-3 py-1.5 text-sm font-semibold text-accent-700">
                  {TIER_LABEL[detail.plan_tier] ?? detail.plan_tier} plan
                </span>
                <span className="inline-flex items-center rounded-full bg-sand-100 px-3 py-1.5 text-sm font-semibold text-ink-muted">
                  {detail.subscription_status}
                </span>
              </div>

              <div className="relative flex items-center gap-2">
                <button
                  type="button"
                  onClick={openEdit}
                  className="flex items-center gap-1.5 rounded-lg border border-sand-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-accent-500/50 hover:text-accent-700">
                  <PencilIcon className="h-3 w-3" /> Edit
                </button>
                <button
                  onClick={() => setPlanMenuOpen((o) => !o)}
                  disabled={savingPlan}
                  className="flex items-center gap-1.5 rounded-lg border border-sand-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink transition-colors hover:border-accent-500/50 hover:text-accent-700 disabled:opacity-50">
                  {savingPlan ? <Loader2Icon className="h-3 w-3 animate-spin" /> : <ChevronDownIcon className="h-3 w-3" />}
                  Change plan
                </button>

                {planMenuOpen &&
                <div className="absolute right-0 z-20 mt-1.5 w-52 overflow-hidden rounded-xl border border-sand-200 bg-white shadow-[0_12px_40px_-12px_rgba(11,29,38,0.25)]">
                    {TIER_ORDER.map((t) =>
                  <button
                    key={t}
                    disabled={t === detail.plan_tier}
                    onClick={() => changePlan(t)}
                    className={`flex w-full items-center justify-between px-4 py-2.5 text-left text-sm transition-colors ${
                    t === detail.plan_tier ? "cursor-default bg-accent-500/5 text-ink" : "text-ink hover:bg-sand-50"}`
                    }>

                        {TIER_LABEL[t]}
                        {t === detail.plan_tier &&
                  <CheckIcon className="h-3.5 w-3.5 text-accent-500" />
                  }
                      </button>
                  )}
                  </div>
                }
              </div>

              {planError && <p className="text-xs text-danger">{planError}</p>}
              {planSaved && <p className="text-xs font-medium text-success">Plan updated.</p>}
            </div>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-2xl border border-sand-200 bg-white p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Est. revenue / mo</p>
              <p className="mt-1 font-display text-2xl font-bold text-ink">{money(detail.estimated_monthly_revenue)}</p>
            </div>
            <div className="rounded-2xl border border-sand-200 bg-white p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Est. cost / mo</p>
              <p className="mt-1 font-display text-2xl font-bold text-ink">{money(detail.estimated_monthly_cost)}</p>
            </div>
            <div className="rounded-2xl border border-sand-200 bg-white p-5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Est. margin / mo</p>
              <p className="mt-1 font-display text-2xl font-bold text-success">
                {money(detail.estimated_monthly_revenue - detail.estimated_monthly_cost)}
              </p>
            </div>
          </div>

          <div className="mt-6 overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <div className="border-b border-sand-200 px-5 py-4">
              <p className="text-sm font-bold text-ink">Agent cost breakdown</p>
              <p className="text-xs text-ink-muted">{detail.agent_breakdown.length} agents configured</p>
            </div>
            {detail.agent_breakdown.length === 0 ?
          <p className="p-6 text-sm text-ink-muted">No agents configured for this clinic yet.</p> :

          <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-sand-200 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                      <th className="px-5 py-3">Agent</th>
                      <th className="px-5 py-3">Enabled</th>
                      <th className="px-5 py-3">Cost / session</th>
                      <th className="px-5 py-3">Est. cost / mo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.agent_breakdown.map((a) =>
                <tr key={a.agent_slug} className="border-b border-sand-100 last:border-0">
                        <td className="px-5 py-3 font-medium text-ink">{a.agent_slug.replace(/_/g, " ")}</td>
                        <td className="px-5 py-3">
                          <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${a.enabled ? "bg-success/10 text-success" : "bg-ink-muted/10 text-ink-muted"}`}>
                            {a.enabled ? "Enabled" : "Disabled"}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-ink-soft">{money(a.cost_per_session)}</td>
                        <td className="px-5 py-3 text-ink-soft">{money(a.estimated_monthly_cost)}</td>
                      </tr>
                )}
                  </tbody>
                </table>
              </div>
          }
          </div>

          {editOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm" onClick={(e) => { if (e.target === e.currentTarget) setEditOpen(false); }}>
              <div className="w-full max-w-md rounded-3xl border border-sand-200 bg-white p-6 shadow-2xl">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-bold text-ink">Edit clinic</p>
                  <button type="button" onClick={() => setEditOpen(false)} className="rounded-lg p-1 text-ink-muted hover:text-ink">
                    <XIcon className="h-4 w-4" />
                  </button>
                </div>
                {editError && <p className="mt-3 text-xs text-danger">{editError}</p>}
                <div className="mt-4 space-y-3">
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-ink-muted">Practice name</label>
                    <input
                      value={editForm.name}
                      onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                      className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50 focus:bg-white"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-semibold text-ink-muted">Contact email</label>
                    <input
                      value={editForm.email}
                      onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                      className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50 focus:bg-white"
                    />
                  </div>
                </div>
                <div className="mt-5 flex justify-end gap-2">
                  <button type="button" onClick={() => setEditOpen(false)} className="rounded-xl border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft hover:bg-sand-100">
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={editBusy || !editForm.name.trim() || !editForm.email.trim()}
                    onClick={handleEditSave}
                    className="rounded-xl bg-accent-500 px-4 py-2 text-sm font-semibold text-white hover:bg-accent-600 disabled:opacity-50">
                    {editBusy ? "Saving…" : "Save changes"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      }
    </>);

}
