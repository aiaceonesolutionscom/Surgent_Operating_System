import React, { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftIcon, MailIcon, PhoneIcon, AwardIcon, FileTextIcon, CheckIcon, XIcon, DownloadIcon, TrashIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { getApplication, approveApplication, rejectApplication, deleteApplication, type DoctorApplicationResponse } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { DOCTOR_PERMISSIONS, RECOMMENDED_DOCTOR_PERMISSIONS } from "../../../data/doctorPermissions";

export function DoctorRequestDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch } = usePlan();
  const navigate = useNavigate();
  const [application, setApplication] = useState<DoctorApplicationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string[]>(RECOMMENDED_DOCTOR_PERMISSIONS);
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || !id) {
        setLoading(false);
        return;
      }
      try {
        const app = await getApplication(authedFetch, id);
        if (!cancelled) setApplication(app);
      } catch {
        if (!cancelled) setApplication(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, id]);

  function togglePermission(key: string) {
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  async function handleApprove() {
    if (!authedFetch || !id) return;
    setSaving(true);
    setError(null);
    try {
      await approveApplication(authedFetch, id, selected);
      navigate(DASHBOARD_ROUTES.doctorRequests);
    } catch (e: unknown) {
      setError(e instanceof Error && e.message ? e.message : "Couldn't approve — try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReject() {
    if (!authedFetch || !id) return;
    setSaving(true);
    setError(null);
    try {
      await rejectApplication(authedFetch, id, rejectReason || undefined);
      navigate(DASHBOARD_ROUTES.doctorRequests);
    } catch (e: unknown) {
      setError(e instanceof Error && e.message ? e.message : "Couldn't reject — try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!authedFetch || !id) return;
    setSaving(true);
    setError(null);
    try {
      await deleteApplication(authedFetch, id);
      navigate(DASHBOARD_ROUTES.doctorRequests);
    } catch (e: unknown) {
      setError(e instanceof Error && e.message ? e.message : "Couldn't delete — try again.");
      setSaving(false);
    }
  }

  if (loading) return null;

  if (!application) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center">
        <p className="text-sm font-semibold text-ink">Request not found</p>
      </div>);

  }

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-3">
        <Link
          to={DASHBOARD_ROUTES.doctorRequests}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

          <ArrowLeftIcon className="h-4 w-4" /> Back to requests
        </Link>

        {!confirmingDelete ?
        <button
          type="button"
          onClick={() => setConfirmingDelete(true)}
          className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger">

            <TrashIcon className="h-3.5 w-3.5" /> Delete request
          </button> :

        <div className="flex items-center gap-2">
            <span className="text-xs text-ink-muted">Delete this request permanently?</span>
            <button
            type="button"
            onClick={handleDelete}
            disabled={saving}
            className="rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:opacity-90 disabled:opacity-50">

              {saving ? "Deleting…" : "Confirm"}
            </button>
            <button type="button" onClick={() => setConfirmingDelete(false)} className="text-xs font-medium text-ink-muted hover:text-ink">
              Cancel
            </button>
          </div>
        }
      </div>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <div className="flex items-center gap-4">
          {application.photo_url ?
          <img src={application.photo_url} alt={application.name} className="h-16 w-16 shrink-0 rounded-full object-cover" /> :

          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-xl font-bold text-teal-600">
              {application.name[0]?.toUpperCase() || "?"}
            </span>
          }
          <div>
            <p className="text-lg font-bold text-ink">{application.name}</p>
            <p className="text-sm text-ink-muted">{application.specialty || "No specialty listed"}</p>
          </div>
        </div>

        {application.bio && <p className="mt-4 text-sm leading-relaxed text-ink-soft">{application.bio}</p>}

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <MailIcon className="h-4 w-4 text-ink-muted" />
            <span className="truncate text-sm text-ink-soft">{application.email}</span>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <PhoneIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">{application.phone || "—"}</span>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <AwardIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">License {application.license_number || "—"}</span>
          </div>
        </div>
      </div>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold text-ink">
          <FileTextIcon className="h-4 w-4 text-teal-600" /> Documents
        </div>
        {application.documents.length === 0 ?
        <p className="text-sm text-ink-muted">No documents uploaded.</p> :

        <div className="grid gap-2 sm:grid-cols-2">
            {application.documents.map((doc, i) =>
          <a
            key={i}
            href={doc.url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-3 rounded-xl bg-sand-100 px-4 py-3 transition-colors hover:bg-sand-200">

                <FileTextIcon className="h-4 w-4 shrink-0 text-ink-muted" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink-soft">{doc.name}</span>
                <DownloadIcon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
              </a>
          )}
          </div>
        }
      </div>

      {application.status === "pending" &&
      <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="mb-1 text-sm font-bold text-ink">Grant access</p>
          <p className="mb-4 text-xs text-ink-muted">
            Recommended items are pre-checked — adjust as needed before approving.
          </p>
          <div className="space-y-2">
            {DOCTOR_PERMISSIONS.map((perm) =>
          <label key={perm.key} className="flex cursor-pointer items-start gap-3 rounded-xl border border-sand-200 px-4 py-3 transition-colors hover:border-teal-600/40">
                <input
              type="checkbox"
              checked={selected.includes(perm.key)}
              onChange={() => togglePermission(perm.key)}
              className="mt-0.5 h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink">
                    {perm.label} {perm.recommended && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-teal-600">Recommended</span>}
                  </p>
                  <p className="text-xs text-ink-muted">{perm.description}</p>
                </div>
              </label>
          )}
          </div>

          {showRejectForm &&
        <div className="mt-4 rounded-xl border border-danger/25 bg-danger/[0.03] p-4">
              <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Reason (optional)</label>
              <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={2}
            className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-danger/40" />

            </div>
        }

          {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

          <div className="mt-5 flex items-center justify-end gap-3">
            {!showRejectForm ?
          <button
            type="button"
            onClick={() => setShowRejectForm(true)}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger">

                <XIcon className="h-4 w-4" /> Reject
              </button> :

          <button
            type="button"
            onClick={handleReject}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:opacity-90 disabled:opacity-50">

                <XIcon className="h-4 w-4" /> {saving ? "Rejecting…" : "Confirm reject"}
              </button>
          }
            <button
            type="button"
            onClick={handleApprove}
            disabled={saving || showRejectForm}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

              <CheckIcon className="h-4 w-4" /> {saving ? "Approving…" : "Approve"}
            </button>
          </div>
        </div>
      }

      {application.status !== "pending" &&
      <div className="rounded-3xl border border-sand-200 bg-white p-6 text-center">
          <p className="text-sm font-semibold capitalize text-ink">{application.status}</p>
          {application.rejected_reason && <p className="mt-1 text-sm text-ink-muted">{application.rejected_reason}</p>}
        </div>
      }
    </>);

}
