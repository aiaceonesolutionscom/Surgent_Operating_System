import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ClipboardListIcon, ArrowRightIcon, TrashIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { listApplications, deleteApplication, type DoctorApplicationResponse } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

export function DoctorRequestsPage() {
  const { authedFetch } = usePlan();
  const [applications, setApplications] = useState<DoctorApplicationResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        setLoading(false);
        return;
      }
      try {
        const apps = await listApplications(authedFetch);
        if (!cancelled) setApplications(apps);
      } catch {
        if (!cancelled) setApplications([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  async function handleDelete(id: string) {
    if (!authedFetch) return;
    await deleteApplication(authedFetch, id);
    setApplications((prev) => prev.filter((a) => a.id !== id));
  }

  const pending = applications.filter((a) => a.status === "pending");
  const decided = applications.filter((a) => a.status !== "pending");

  return (
    <>
      <PageHeader
        title="Doctor Requests"
        subtitle="Doctors who signed up themselves via your practice's signup link — review their details and decide what access to grant." />


      {loading ?
      <p className="text-sm text-ink-muted">Loading…</p> :
      applications.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState
          icon={ClipboardListIcon}
          title="No requests yet"
          body="Share your doctor signup link (from the Doctors page) — applications will show up here for review." />

        </div> :

      <div className="space-y-6">
          {pending.length > 0 &&
        <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
              <div className="border-b border-sand-200 px-5 py-4">
                <p className="text-sm font-bold text-ink">Pending review ({pending.length})</p>
              </div>
              <div className="divide-y divide-sand-100">
                {pending.map((a) => <RequestRow key={a.id} application={a} onDelete={handleDelete} />)}
              </div>
            </div>
        }

          {decided.length > 0 &&
        <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
              <div className="border-b border-sand-200 px-5 py-4">
                <p className="text-sm font-bold text-ink">Past decisions</p>
              </div>
              <div className="divide-y divide-sand-100">
                {decided.map((a) => <RequestRow key={a.id} application={a} onDelete={handleDelete} />)}
              </div>
            </div>
        }
        </div>
      }
    </>);

}

function RequestRow({ application, onDelete }: { application: DoctorApplicationResponse; onDelete: (id: string) => Promise<void> }) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const statusClass =
  application.status === "approved" ?
  "bg-success/10 text-success" :
  application.status === "rejected" ?
  "bg-danger/10 text-danger" :
  "bg-warning/10 text-warning";

  async function confirmDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDeleting(true);
    try {
      await onDelete(application.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-sand-50">
      <Link to={DASHBOARD_ROUTES.doctorRequestDetail(application.id)} className="flex min-w-0 flex-1 items-center gap-4">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-ink">{application.name}</p>
          <p className="truncate text-xs text-ink-muted">{application.specialty || "No specialty listed"} · {application.email}</p>
        </div>
        <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusClass}`}>{application.status}</span>
      </Link>
      {confirmingDelete ?
      <div className="flex shrink-0 items-center gap-1.5">
          <button type="button" onClick={confirmDelete} disabled={deleting} className="rounded-lg bg-danger px-2.5 py-1.5 text-[11px] font-semibold text-white hover:opacity-90 disabled:opacity-50">
            {deleting ? "…" : "Confirm"}
          </button>
          <button type="button" onClick={(e) => { e.preventDefault(); e.stopPropagation(); setConfirmingDelete(false); }} className="text-[11px] font-medium text-ink-muted hover:text-ink">
            Cancel
          </button>
        </div> :

      <button
        type="button"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); setConfirmingDelete(true); }}
        title="Delete request"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-danger/10 hover:text-danger">

          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      }
      <Link to={DASHBOARD_ROUTES.doctorRequestDetail(application.id)}>
        <ArrowRightIcon className="h-4 w-4 shrink-0 text-ink-muted" />
      </Link>
    </div>);

}
