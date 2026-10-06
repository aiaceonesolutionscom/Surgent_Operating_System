import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, MailIcon, PhoneIcon, AwardIcon, CalendarCheckIcon, DollarSignIcon, PencilIcon, ClockIcon, FileTextIcon, DownloadIcon, Maximize2Icon, SparklesIcon, SendIcon, CheckCircle2Icon, UserXIcon, UserCheckIcon, AlertTriangleIcon } from "lucide-react";
import { ComingSoon } from "../components/ComingSoon";
import { useDoctors } from "./useDoctors";
import { WEEKDAYS } from "./types";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { DocumentViewerModal } from "./DocumentViewerModal";
import { getDoctorCompleteness } from "./doctorCompleteness";
import { usePlan } from "../plan/PlanContext";
import { inviteDoctor } from "../../../api/entities";

export function DoctorDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch, role } = usePlan();
  const { getDoctor, updateDoctor, loading } = useDoctors(authedFetch);
  const doctor = id ? getDoctor(id) : undefined;
  const [viewingDocId, setViewingDocId] = useState<string | null>(null);
  const [inviteState, setInviteState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  const [removeSaving, setRemoveSaving] = useState(false);

  async function handleInvite() {
    if (!doctor || !authedFetch) return;
    setInviteState("sending");
    setInviteError(null);
    try {
      await inviteDoctor(authedFetch, doctor.id);
      setInviteState("sent");
    } catch (err: unknown) {
      setInviteState("error");
      setInviteError(err instanceof Error && err.message ? err.message : "Couldn't send invite — try again.");
    }
  }

  async function handleSetActive(nextActive: boolean) {
    if (!doctor) return;
    setRemoveSaving(true);
    await updateDoctor(doctor.id, { isActive: nextActive });
    setRemoveSaving(false);
    setConfirmingRemove(false);
  }

  if (loading) return null;

  if (!doctor) {
    return <ComingSoon icon={AwardIcon} title="Doctor not found" body="This doctor record doesn't exist." phase="—" />;
  }

  const slotsByDay = new Map(WEEKDAYS.map((d) => [d, doctor.availability.filter((s) => s.day === d)]));
  const viewingDoc = doctor.documents.find((d) => d.id === viewingDocId);
  const completeness = getDoctorCompleteness(doctor);

  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <Link
          to={DASHBOARD_ROUTES.doctors}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

          <ArrowLeftIcon className="h-4 w-4" /> Back to doctors
        </Link>
        <div className="flex items-center gap-2">
          {role === "owner" && !doctor.userId &&
          <button
            type="button"
            onClick={handleInvite}
            disabled={inviteState === "sending" || inviteState === "sent"}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:cursor-not-allowed disabled:opacity-60">

              {inviteState === "sent" ?
            <><CheckCircle2Icon className="h-3.5 w-3.5 text-teal-600" /> Invite sent</> :

            <><SendIcon className="h-3.5 w-3.5" /> {inviteState === "sending" ? "Sending…" : "Invite to portal"}</>
            }
            </button>
          }
          {role === "owner" && doctor.userId &&
          <span className="flex items-center gap-1.5 rounded-xl bg-teal-600/8 px-4 py-2 text-sm font-semibold text-teal-600">
              <CheckCircle2Icon className="h-3.5 w-3.5" /> Portal linked
            </span>
          }
          {inviteState === "error" && <p className="text-xs font-medium text-danger">{inviteError}</p>}
          <Link
            to={DASHBOARD_ROUTES.doctorEdit(doctor.id)}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

            <PencilIcon className="h-3.5 w-3.5" /> Edit
          </Link>
          {role === "owner" && doctor.isActive && !confirmingRemove &&
          <button
            type="button"
            onClick={() => setConfirmingRemove(true)}
            className="flex items-center gap-1.5 rounded-xl border border-danger/25 px-4 py-2 text-sm font-semibold text-danger transition-colors hover:bg-danger/5">

              <UserXIcon className="h-3.5 w-3.5" /> Remove doctor
            </button>
          }
          {role === "owner" && doctor.isActive && confirmingRemove &&
          <div className="flex items-center gap-2 rounded-xl border border-danger/25 bg-danger/5 px-3 py-1.5">
              <span className="text-xs font-medium text-danger">Revoke their dashboard access?</span>
              <button
              type="button"
              onClick={() => handleSetActive(false)}
              disabled={removeSaving}
              className="rounded-lg bg-danger px-2.5 py-1 text-xs font-semibold text-white transition-colors hover:opacity-90 disabled:opacity-50">

                {removeSaving ? "Removing…" : "Confirm"}
              </button>
              <button
              type="button"
              onClick={() => setConfirmingRemove(false)}
              disabled={removeSaving}
              className="rounded-lg px-2.5 py-1 text-xs font-semibold text-ink-muted hover:text-ink">

                Cancel
              </button>
            </div>
          }
          {role === "owner" && !doctor.isActive &&
          <button
            type="button"
            onClick={() => handleSetActive(true)}
            disabled={removeSaving}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">

              <UserCheckIcon className="h-3.5 w-3.5" /> {removeSaving ? "Reactivating…" : "Reactivate doctor"}
            </button>
          }
        </div>
      </div>

      {!doctor.isActive &&
      <div className="mb-6 flex items-center gap-2.5 rounded-3xl border border-danger/25 bg-danger/[0.05] p-5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
            <AlertTriangleIcon className="h-4 w-4" />
          </span>
          <div>
            <p className="text-sm font-bold text-ink">This doctor has been removed</p>
            <p className="text-xs text-ink-muted">Their dashboard login access is revoked. Reactivate to restore it.</p>
          </div>
        </div>
      }

      {completeness.percent < 100 &&
      <div className="mb-6 rounded-3xl border border-warning/25 bg-warning/[0.05] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-warning/10 text-warning">
                <SparklesIcon className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-bold text-ink">Profile {completeness.percent}% complete</p>
                <p className="text-xs text-ink-muted">Missing: {completeness.missing.join(", ")}</p>
              </div>
            </div>
            <Link
              to={DASHBOARD_ROUTES.doctorEdit(doctor.id)}
              className="shrink-0 rounded-xl bg-warning px-4 py-2 text-xs font-semibold text-white transition-colors hover:opacity-90">

              Complete profile
            </Link>
          </div>
          <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white">
            <div className="h-full rounded-full bg-warning transition-[width]" style={{ width: `${completeness.percent}%` }} />
          </div>
        </div>
      }

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <div className="flex items-center gap-4">
          {doctor.photoUrl ?
          <img src={doctor.photoUrl} alt={doctor.name} className="h-16 w-16 shrink-0 rounded-full object-cover" /> :

          <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-xl font-bold text-teal-600">
              {doctor.initial}
            </span>
          }
          <div>
            <p className="text-lg font-bold text-ink">{doctor.name}</p>
            <p className="text-sm text-ink-muted">{doctor.specialty}</p>
          </div>
        </div>

        <p className="mt-4 text-sm leading-relaxed text-ink-soft">{doctor.bio || "No bio added yet."}</p>

        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <MailIcon className="h-4 w-4 text-ink-muted" />
            <span className="truncate text-sm text-ink-soft">{doctor.email}</span>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <PhoneIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">{doctor.phone || "—"}</span>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <AwardIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">License {doctor.licenseNumber || "—"}</span>
          </div>
          <div className="flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <CalendarCheckIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">{doctor.yearsExperience} years experience</span>
          </div>
        </div>

        {doctor.capabilities.length > 0 &&
        <div className="mt-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-muted">Capable of</p>
            <div className="flex flex-wrap gap-2">
              {doctor.capabilities.map((c) =>
            <span key={c} className="rounded-full bg-teal-600/8 px-3 py-1.5 text-xs font-semibold text-teal-600">
                  {c}
                </span>
            )}
            </div>
          </div>
        }
      </div>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold text-ink">
          <ClockIcon className="h-4 w-4 text-teal-600" /> Availability
        </div>
        {doctor.availability.length === 0 ?
        <p className="text-sm text-ink-muted">No availability set yet — add it from Edit.</p> :

        <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-7">
            {WEEKDAYS.map((day) => {
            const slots = slotsByDay.get(day) || [];
            return (
              <div key={day} className={`rounded-xl px-3 py-2.5 ${slots.length ? "bg-teal-600/8" : "bg-sand-100"}`}>
                  <p className={`text-xs font-bold uppercase tracking-wide ${slots.length ? "text-teal-600" : "text-ink-muted"}`}>{day}</p>
                  {slots.length === 0 ?
                <p className="mt-1 text-xs text-ink-muted">Off</p> :

                <div className="mt-1 space-y-0.5">
                      {slots.map((s, i) =>
                  <p key={i} className="text-xs font-semibold text-ink-soft">{s.startTime}–{s.endTime}</p>
                  )}
                    </div>
                }
                </div>);

          })}
          </div>
        }
      </div>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold text-ink">
          <FileTextIcon className="h-4 w-4 text-teal-600" /> Documents
        </div>
        {doctor.documents.length === 0 ?
        <p className="text-sm text-ink-muted">No documents uploaded yet — add license, certification, or CV files from Edit.</p> :

        <div className="grid gap-2 sm:grid-cols-2">
            {doctor.documents.map((doc) =>
          <div key={doc.id} className="flex items-center gap-3 rounded-xl bg-sand-100 px-4 py-3">
                <FileTextIcon className="h-4 w-4 shrink-0 text-ink-muted" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink-soft">{doc.name}</span>
                <button
              type="button"
              onClick={() => setViewingDocId(doc.id)}
              title="View full screen"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-white hover:text-teal-600">

                  <Maximize2Icon className="h-3.5 w-3.5" />
                </button>
                <a
              href={doc.dataUrl}
              download={doc.name}
              title="Download"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-muted transition-colors hover:bg-white hover:text-teal-600">

                  <DownloadIcon className="h-3.5 w-3.5" />
                </a>
              </div>
          )}
          </div>
        }
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="font-mono text-3xl font-bold tabular-nums text-ink">{doctor.activePatients}</p>
          <p className="text-sm text-ink-muted">Active patients</p>
        </div>
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="font-mono text-3xl font-bold tabular-nums text-ink">{doctor.upcomingSurgeries}</p>
          <p className="text-sm text-ink-muted">Upcoming surgeries</p>
        </div>
      </div>

      <div className="mt-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6">
        <div className="flex items-center gap-2 text-sm font-bold text-ink">
          <DollarSignIcon className="h-4 w-4 text-teal-600" /> My performance
        </div>
        <p className="mt-1.5 text-xs text-ink-muted">
          Revenue attributed to procedures this doctor performed — separate from payroll/compensation,
          which belongs in an admin-only Practice Finance area, not here. Not built yet; would read from
          the real <code className="rounded bg-sand-100 px-1.5 py-0.5">Invoice</code> model once
          procedure-level doctor attribution exists.
        </p>
      </div>

      {viewingDoc && <DocumentViewerModal doc={viewingDoc} onClose={() => setViewingDocId(null)} />}
    </>);

}
