import { useEffect, useState } from "react";
import { UsersIcon, PencilIcon, CheckIcon, XIcon, TrashIcon, UserCheckIcon, UserPlusIcon, Clock4Icon, SendIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { KebabMenu } from "../components/KebabMenu";
import { usePlan } from "../plan/PlanContext";
import { useStaff } from "./useStaff";
import { StaffSignupLinkCard } from "./StaffSignupLinkCard";
import { RECEPTIONIST_PERMISSIONS, RECOMMENDED_RECEPTIONIST_PERMISSIONS } from "../../../data/receptionistPermissions";
import {
  listStaffApplications,
  approveStaffApplication,
  rejectStaffApplication,
  resendStaffAccess,
  type StaffApplicationResponse
} from "../../../api/entities";
import type { StaffResponse } from "../../../api/entities";

export function StaffPage() {
  const { authedFetch } = usePlan();
  const { staff, loading, update } = useStaff(authedFetch);
  const resendAccess = async (id: string): Promise<string | null> => {
    if (!authedFetch) return "Not signed in.";
    try {
      await resendStaffAccess(authedFetch, id);
      return null;
    } catch (err) {
      return err instanceof Error && err.message ? err.message : "Couldn't resend — try again.";
    }
  };

  return (
    <>
      <PageHeader
        title="Staff"
        subtitle="Receptionists who can access the Front Desk, Waiting Room, and booking — share the signup link to add someone, then approve their application here." />

      <StaffSignupLinkCard />

      <PendingRequests />

      <div className="mt-6">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        staff.length === 0 ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState icon={UsersIcon} title="No receptionists yet" body="Share the signup link above to add your first front-desk staff member." />
          </div> :

        <div className="space-y-3">
            {staff.map((s) => <StaffRow key={s.id} staff={s} onUpdate={update} onResendAccess={resendAccess} />)}
          </div>
        }
      </div>
    </>);

}

// Owner's review queue for receptionist self-applications — the approval side
// of the shared signup link (see StaffApplyPage.tsx). Approving grants the
// chosen permissions and activates the account; rejecting moves it out of the
// queue so the applicant sees the decline on their status page.
function PendingRequests() {
  const { authedFetch } = usePlan();
  const [applications, setApplications] = useState<StaffApplicationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);

  async function load() {
    if (!authedFetch) return;
    try {
      const list = await listStaffApplications(authedFetch, "pending");
      setApplications(list);
    } catch {
      setApplications([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  async function handleApprove(id: string, permissions: string[]) {
    if (!authedFetch) return;
    setBusyId(id);
    setError(null);
    try {
      await approveStaffApplication(authedFetch, id, permissions);
      await load();
      setApproving(null);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't approve — try again.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    if (!authedFetch) return;
    setBusyId(id);
    setError(null);
    try {
      await rejectStaffApplication(authedFetch, id);
      await load();
      setRejecting(null);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't reject — try again.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return null;

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Clock4Icon className="h-4 w-4 text-ink-muted" />
        <h2 className="text-sm font-bold text-ink">Pending receptionist applications</h2>
        {applications.length > 0 && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-700">
            {applications.length}
          </span>
        )}
      </div>

      {applications.length === 0 ?
      <div className="rounded-2xl border border-dashed border-sand-200 bg-white/60 px-5 py-4 text-sm text-ink-muted">
          No applications waiting — share the receptionist signup link above.
        </div> :

      <div className="space-y-3">
          {applications.map((app) => (
            <PendingRow
              key={app.id}
              app={app}
              busy={busyId === app.id}
              approving={approving === app.id}
              rejecting={rejecting === app.id}
              error={error}
              onApprove={(permissions) => handleApprove(app.id, permissions)}
              onReject={() => handleReject(app.id)}
              onStartApprove={() => setApproving(app.id)}
              onCancelApprove={() => setApproving(null)}
              onStartReject={() => setRejecting(app.id)}
              onCancelReject={() => setRejecting(null)}
              canApproveNow={Boolean(authedFetch)} />
          ))}
        </div>
      }
    </div>);

}

function PendingRow(props: {
  app: StaffApplicationResponse;
  busy: boolean;
  approving: boolean;
  rejecting: boolean;
  error: string | null;
  onApprove: (permissions: string[]) => void;
  onReject: () => void;
  onStartApprove: () => void;
  onCancelApprove: () => void;
  onStartReject: () => void;
  onCancelReject: () => void;
  canApproveNow: boolean;
}) {
  const [selected, setSelected] = useState<string[]>(RECOMMENDED_RECEPTIONIST_PERMISSIONS);

  return (
    <div className="rounded-3xl border border-amber-200/60 bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-bold text-ink">{props.app.name}</p>
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
              Awaiting approval
            </span>
          </div>
          <p className="truncate text-xs text-ink-muted">{props.app.email}{props.app.phone ? ` · ${props.app.phone}` : ""}</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {!props.approving && !props.rejecting && <ApproveButton onClick={props.onStartApprove} disabled={props.busy} />}
          {!props.approving && !props.rejecting && (
            <button
              type="button"
              onClick={props.onStartReject}
              disabled={props.busy}
              className="flex items-center gap-1.5 rounded-xl border border-danger/25 px-3 py-1.5 text-xs font-semibold text-danger transition-colors hover:bg-danger/5 disabled:opacity-50">

              <XIcon className="h-3.5 w-3.5" /> Reject
            </button>
          )}

          {props.rejecting &&
          <div className="flex items-center gap-2">
              <button type="button" onClick={props.onCancelReject} className="rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:bg-sand-100">
                Cancel
              </button>
              <button
              type="button"
              onClick={props.onReject}
              disabled={props.busy}
              className="flex items-center gap-1 rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50">

                <XIcon className="h-3.5 w-3.5" /> {props.busy ? "Rejecting…" : "Confirm reject"}
              </button>
            </div>
          }
        </div>
      </div>

      {props.approving &&
      <div className="mt-4 space-y-2 border-t border-sand-100 pt-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Grant access to approve</p>
          {RECEPTIONIST_PERMISSIONS.map((perm) => (
            <label key={perm.key} className="flex cursor-pointer items-start gap-3 rounded-xl border border-sand-200 px-4 py-3 transition-colors hover:border-teal-600/40">
              <input
                type="checkbox"
                checked={selected.includes(perm.key)}
                onChange={() => setSelected((prev) => (prev.includes(perm.key) ? prev.filter((k) => k !== perm.key) : [...prev, perm.key]))}
                className="mt-0.5 h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />

              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">
                  {perm.label}{perm.recommended && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-teal-600">Recommended</span>}
                </p>
                <p className="text-xs text-ink-muted">{perm.description}</p>
              </div>
            </label>
          ))}
          {props.error && <p className="text-sm font-medium text-danger">{props.error}</p>}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button type="button" onClick={props.onCancelApprove} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink">
              Cancel
            </button>
            <button
              type="button"
              onClick={() => props.onApprove(selected)}
              disabled={props.busy || !props.canApproveNow}
              className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50">

              <UserCheckIcon className="h-3.5 w-3.5" /> {props.busy ? "Approving…" : "Approve & activate"}
            </button>
          </div>
        </div>
      }
    </div>);

}

function ApproveButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex items-center gap-1.5 rounded-xl border border-teal-600/30 px-3 py-1.5 text-xs font-semibold text-teal-700 transition-colors hover:bg-teal-600/5 disabled:opacity-50">

      <UserPlusIcon className="h-3.5 w-3.5" /> Approve
    </button>);

}

function StaffRow({ staff, onUpdate, onResendAccess }: {
  staff: StaffResponse;
  onUpdate: (id: string, patch: { permissions?: string[]; is_active?: boolean }) => Promise<boolean>;
  onResendAccess: (id: string) => Promise<string | null>;
}) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<string[]>(staff.permissions);
  const [saving, setSaving] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMessage, setResendMessage] = useState<string | null>(null);

  async function handleResend() {
    setResending(true);
    setResendMessage(null);
    const error = await onResendAccess(staff.id);
    setResendMessage(error || "Invite sent — ask them to check their email.");
    setResending(false);
  }

  function toggle(key: string) {
    setSelected((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  }

  async function savePermissions() {
    setSaving(true);
    const ok = await onUpdate(staff.id, { permissions: selected });
    setSaving(false);
    if (ok) setEditing(false);
  }

  async function toggleActive() {
    setSaving(true);
    await onUpdate(staff.id, { is_active: !staff.is_active });
    setSaving(false);
  }

  return (
    <div className={`rounded-3xl border bg-white p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] ${staff.is_active ? "border-sand-200" : "border-danger/25 bg-danger/[0.02]"}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-ink">{staff.name || staff.email}</p>
          <p className="truncate text-xs text-ink-muted">{staff.email}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {!staff.is_active && <span className="rounded-full bg-danger/10 px-2.5 py-1 text-[11px] font-semibold text-danger">Removed</span>}
          <button
            type="button"
            onClick={() => setEditing((v) => !v)}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

            <PencilIcon className="h-3.5 w-3.5" /> Permissions
          </button>
          {!staff.is_active &&
          <button
            type="button"
            onClick={toggleActive}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">

            <UserCheckIcon className="h-3.5 w-3.5" /> Reactivate
          </button>
          }
          <KebabMenu items={[
            {
              label: resending ? "Sending…" : "Resend access",
              icon: <SendIcon className="h-3.5 w-3.5" />,
              onClick: () => void handleResend()
            },
            {
              label: "Delete permanently",
              icon: <TrashIcon className="h-3.5 w-3.5" />,
              danger: true,
              onClick: () => setConfirmingDelete(true)
            }
          ]} />
        </div>
      </div>

      {resendMessage && <p className="mt-2 text-xs text-ink-muted">{resendMessage}</p>}

      {confirmingDelete &&
      <div className="mt-3 rounded-xl border border-danger/25 bg-danger/[0.03] p-4">
          <p className="text-sm font-semibold text-ink">Delete {staff.name || staff.email} permanently?</p>
          <p className="mt-1 text-xs text-ink-muted">Their account will lose access and be removed from your staff list. Their past history (messages, expenses, consents) will be kept.</p>
          <div className="mt-3 flex items-center justify-end gap-2">
            <button
            type="button"
            onClick={() => setConfirmingDelete(false)}
            className="rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:bg-sand-100">
              Cancel
            </button>
            <button
            type="button"
            onClick={() => {
              setConfirmingDelete(false);
              void toggleActive();
            }}
            disabled={saving}
            className="flex items-center gap-1 rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:bg-danger/90 disabled:opacity-50">
              <TrashIcon className="h-3.5 w-3.5" /> {saving ? "Deleting…" : "Delete permanently"}
            </button>
          </div>
        </div>
      }

      {!editing &&
      <div className="mt-3 flex flex-wrap gap-1.5">
          {staff.permissions.length === 0 ?
        <span className="text-xs text-ink-muted">No permissions granted yet.</span> :

        staff.permissions.map((key) => {
          const perm = RECEPTIONIST_PERMISSIONS.find((p) => p.key === key);
          return (
            <span key={key} className="rounded-full bg-sand-100 px-2.5 py-1 text-[11px] font-semibold text-ink-soft">
                  {perm?.label || key}
                </span>);

        })
        }
        </div>
      }

      {editing &&
      <div className="mt-4 space-y-2 border-t border-sand-100 pt-4">
          {RECEPTIONIST_PERMISSIONS.map((perm) =>
        <label key={perm.key} className="flex cursor-pointer items-start gap-3 rounded-xl border border-sand-200 px-4 py-3 transition-colors hover:border-teal-600/40">
              <input
            type="checkbox"
            checked={selected.includes(perm.key)}
            onChange={() => toggle(perm.key)}
            className="mt-0.5 h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />

              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">{perm.label}</p>
                <p className="text-xs text-ink-muted">{perm.description}</p>
              </div>
            </label>
        )}
          <div className="flex items-center justify-end gap-2 pt-1">
            <button type="button" onClick={() => { setSelected(staff.permissions); setEditing(false); }} className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink">
              <XIcon className="h-3.5 w-3.5" /> Cancel
            </button>
            <button
            type="button"
            onClick={savePermissions}
            disabled={saving}
            className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50">

              <CheckIcon className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      }
    </div>);

}