import React, { useState } from "react";
import { Link } from "react-router-dom";
import { LockIcon, PencilIcon, PlusIcon, StethoscopeIcon, TrashIcon, UserCircleIcon, SendIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { useDoctors } from "./useDoctors";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import { planFor } from "../plan/plan";
import { getDoctorCompleteness } from "./doctorCompleteness";
import { DoctorSignupLinkCard } from "./DoctorSignupLinkCard";
import { KebabMenu } from "../components/KebabMenu";

export function DoctorsPage() {
  const { authedFetch, role, capabilities } = usePlan();
  const { doctors, loading, updateDoctor, resendAccess } = useDoctors(authedFetch);
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);
  const [resendingId, setResendingId] = useState<string | null>(null);
  const [resendMessage, setResendMessage] = useState<{ id: string; text: string } | null>(null);

  async function handleResend(id: string) {
    setResendingId(id);
    const error = await resendAccess(id);
    setResendMessage({ id, text: error || "Invite sent — ask them to check their email." });
    setResendingId(null);
  }
  const atLimit = doctors.length >= capabilities.limits.maxDoctors;
  // Deactivated ("permanently removed") doctors drop off the active roster —
  // their record is kept (so linked history stays safe) but they no longer
  // show up as available staff.
  const activeDoctors = doctors.filter((d) => d.isActive);

  return (
    <>
      <DoctorSignupLinkCard />

      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader title="Doctors" subtitle="Every surgeon on your team — their specialty, capabilities, availability, and current caseload." />
        <div className="flex shrink-0 items-center gap-2.5">
          {role === "owner" &&
          <Link
            to={DASHBOARD_ROUTES.doctorRequests}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

              <UserCircleIcon className="h-4 w-4" /> Requests
            </Link>
          }
          {atLimit ?
        <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="flex cursor-not-allowed items-center gap-1.5 rounded-xl bg-sand-100 px-4 py-2.5 text-sm font-semibold text-ink-muted">
              <LockIcon className="h-4 w-4" /> Add doctor
            </span>
            <Link to={DASHBOARD_ROUTES.settingsBilling} className="text-xs font-medium text-teal-600 hover:underline">
              {planFor(capabilities.tier).name} includes {capabilities.limits.maxDoctors} — upgrade to add more
            </Link>
          </div> :

        <Link
          to={DASHBOARD_ROUTES.doctorNew}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

            <PlusIcon className="h-4 w-4" /> Add doctor
          </Link>
        }
        </div>
      </div>

      {loading ?
      <p className="text-sm text-ink-muted">Loading…</p> :
      activeDoctors.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={StethoscopeIcon} title="No doctors yet" body="Add your practice's surgeons to see them here." />
        </div> :

      <div className="grid gap-4 sm:grid-cols-2">
          {activeDoctors.map((doc) => {
          const completeness = getDoctorCompleteness(doc);
          return (
            <div
            key={doc.id}
            className={`group relative rounded-3xl border bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)] transition-colors hover:border-teal-600/40 ${doc.isActive ? "border-sand-200" : "border-danger/25 bg-danger/[0.02]"}`}>

              <Link
              to={DASHBOARD_ROUTES.doctorEdit(doc.id)}
              title="Edit doctor"
              className="absolute right-5 top-5 flex h-8 w-8 items-center justify-center rounded-lg text-ink-muted opacity-0 transition-opacity hover:bg-sand-100 hover:text-teal-600 group-hover:opacity-100">

                <PencilIcon className="h-3.5 w-3.5" />
              </Link>

              <div className="absolute right-[4.5rem] top-5 z-20 opacity-0 transition-opacity group-hover:opacity-100">
                <KebabMenu items={[
                  {
                    label: resendingId === doc.id ? "Sending…" : "Resend access",
                    icon: <SendIcon className="h-3.5 w-3.5" />,
                    onClick: () => void handleResend(doc.id)
                  },
                  {
                    label: "Delete permanently",
                    icon: <TrashIcon className="h-3.5 w-3.5" />,
                    danger: true,
                    onClick: () => setConfirmingDeleteId(doc.id)
                  }
                ]} />
              </div>

              {resendMessage?.id === doc.id &&
              <p className="absolute right-5 top-14 z-30 w-64 rounded-xl border border-sand-200 bg-white p-3 text-xs text-ink-muted shadow-[0_8px_24px_rgba(15,23,42,0.14)]">
                  {resendMessage.text}
                </p>
              }

              {confirmingDeleteId === doc.id &&
              <div className="absolute right-5 top-14 z-30 rounded-xl border border-danger/25 bg-white w-72 p-4 shadow-[0_8px_24px_rgba(15,23,42,0.14)]">
                  <p className="text-sm font-semibold text-ink">Delete {doc.name} permanently?</p>
                  <p className="mt-1 text-xs text-ink-muted">They'll be removed from your doctors list and lose access. Their past history (appointments, notes, plans) will be kept.</p>
                  <div className="mt-3 flex items-center justify-end gap-2">
                    <button
                    type="button"
                    onClick={() => setConfirmingDeleteId(null)}
                    className="rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft hover:bg-sand-100">
                      Cancel
                    </button>
                    <button
                    type="button"
                    onClick={() => {
                      setConfirmingDeleteId(null);
                      void updateDoctor(doc.id, { isActive: false });
                    }}
                    className="flex items-center gap-1 rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white hover:bg-danger/90">
                      <TrashIcon className="h-3.5 w-3.5" /> Delete permanently
                    </button>
                  </div>
                </div>
              }

              <Link to={DASHBOARD_ROUTES.doctorDetail(doc.id)} className="block">
                <div className="flex items-center gap-4">
                  {doc.photoUrl ?
                <img src={doc.photoUrl} alt={doc.name} className="h-14 w-14 shrink-0 rounded-full object-cover" /> :

                <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-teal-600/8 text-lg font-bold text-teal-600">
                      {doc.initial}
                    </span>
                }
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-bold text-ink">{doc.name}</p>
                    <p className="truncate text-xs text-ink-muted">{doc.specialty}</p>
                  </div>
                  {!doc.isActive &&
                <span className="shrink-0 rounded-full bg-danger/10 px-2.5 py-1 text-[11px] font-semibold text-danger">
                      Removed
                    </span>
                }
                  {doc.isActive && completeness.percent < 100 &&
                <span
                  title={`Profile ${completeness.percent}% complete — missing ${completeness.missing.join(", ")}`}
                  className="shrink-0 rounded-full bg-warning/10 px-2.5 py-1 text-[11px] font-semibold text-warning">

                      {completeness.percent}%
                    </span>
                }
                </div>

                {doc.capabilities.length > 0 &&
            <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {doc.capabilities.slice(0, 3).map((c) =>
              <span key={c} className="rounded-full bg-sand-100 px-2.5 py-1 text-[11px] font-semibold text-ink-soft">
                        {c}
                      </span>
              )}
                    {doc.capabilities.length > 3 &&
              <span className="rounded-full bg-sand-100 px-2.5 py-1 text-[11px] font-semibold text-ink-muted">
                        +{doc.capabilities.length - 3} more
                      </span>
              }
                  </div>
            }

                <div className="mt-4 flex gap-4 text-xs text-ink-muted">
                  <span><span className="font-mono font-semibold text-ink">{doc.activePatients}</span> active patients</span>
                  <span><span className="font-mono font-semibold text-ink">{doc.upcomingSurgeries}</span> upcoming surgeries</span>
                </div>
              </Link>
            </div>);

        })}
        </div>
      }
    </>);

}
