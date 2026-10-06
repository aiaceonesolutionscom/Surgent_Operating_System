import { Link } from "react-router-dom";
import { TargetIcon, ClipboardListIcon, SparklesIcon, ScissorsIcon, ShieldCheckIcon, ShieldAlertIcon } from "lucide-react";
import type { Patient } from "./types";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import { DASHBOARD_ROUTES } from "../constants/routes";

function formatDate(iso: string | null) {
  if (!iso) return "Not scheduled";
  return new Date(iso).toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
}

// One flexible Overview tab shared by all three role-specific detail pages
// — sections are conditional on `variant`, not on hiding-after-the-fact, so
// a role only ever sees blocks meant for it (registration/source/portal
// detail for Owner+Receptionist, AI intake summary for Owner+Doctor, lead
// qualification for Owner+Receptionist only — Doctor stays purely clinical).
export function PatientOverviewTab({ patient, variant }: { patient: Patient; variant: "owner" | "doctor" | "receptionist" }) {
  const agent = patient.assignedAgentSlug ? AGENTS_BY_SLUG[patient.assignedAgentSlug] : null;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <p className="text-sm font-bold text-ink">Demographics &amp; contact</p>
          <dl className="mt-4 space-y-2.5 text-sm">
            <div className="flex justify-between gap-4"><dt className="text-ink-muted">Email</dt><dd className="text-ink-soft">{patient.email || "—"}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-ink-muted">Phone</dt><dd className="text-ink-soft">{patient.phone || "—"}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-ink-muted">Assigned doctor</dt><dd className="text-ink-soft">{patient.assignedDoctorName || "Unassigned"}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-ink-muted">Last visit</dt><dd className="text-ink-soft">{formatDate(patient.lastVisit)}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-ink-muted">Next appointment</dt><dd className="font-medium text-teal-600">{formatDate(patient.nextAppointment)}</dd></div>
          </dl>
        </div>

        {variant !== "doctor" &&
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <p className="text-sm font-bold text-ink">Registration &amp; portal</p>
            <dl className="mt-4 space-y-2.5 text-sm">
              <div className="flex justify-between gap-4"><dt className="text-ink-muted">Patient ID</dt><dd className="text-ink-soft">{patient.portalId || "—"}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-ink-muted">Source</dt><dd className="text-ink-soft">{patient.source || "—"}</dd></div>
              <div className="flex items-center justify-between gap-4">
                <dt className="text-ink-muted">Portal access</dt>
                <dd>
                  {patient.portalEnabled ?
                  <span className="flex items-center gap-1 text-xs font-semibold text-success"><ShieldCheckIcon className="h-3.5 w-3.5" /> Active</span> :
                  <span className="flex items-center gap-1 text-xs font-semibold text-ink-muted"><ShieldAlertIcon className="h-3.5 w-3.5" /> Not active</span>
                  }
                </dd>
              </div>
            </dl>
          </div>
        }
      </div>

      {patient.qualification && variant !== "doctor" &&
      <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center gap-2">
            <TargetIcon className="h-4 w-4 text-teal-600" />
            <p className="text-sm font-bold text-ink">Lead qualification</p>
            <span className="ml-auto rounded-full bg-teal-600/10 px-2.5 py-1 text-xs font-semibold text-teal-600">
              Score: {patient.qualification.score}/100
            </span>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">{patient.qualification.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {patient.qualification.interestedProcedure &&
            <span className="rounded-full border border-sand-200 px-2.5 py-1 font-medium text-ink-soft">
                Interested in: {patient.qualification.interestedProcedure}
              </span>
            }
            <span className="rounded-full border border-sand-200 px-2.5 py-1 font-medium capitalize text-ink-soft">Budget: {patient.qualification.budgetSignal}</span>
            <span className="rounded-full border border-sand-200 px-2.5 py-1 font-medium capitalize text-ink-soft">Urgency: {patient.qualification.urgency.replace("_", " ")}</span>
          </div>
        </div>
      }

      {patient.intakeSummary && variant !== "receptionist" &&
      <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center gap-2">
            <ClipboardListIcon className="h-4 w-4 text-teal-600" />
            <p className="text-sm font-bold text-ink">AI intake summary</p>
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">{patient.intakeSummary}</p>
        </div>
      }

      {patient.chiefComplaint &&
      <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between">
            <p className="text-sm font-bold text-ink">Reason for visit</p>
            {patient.needsSurgery &&
          <span className="flex items-center gap-1.5 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-semibold text-warning">
                <ScissorsIcon className="h-3 w-3" /> Surgery indicated
              </span>
          }
          </div>
          <p className="mt-2 text-sm leading-relaxed text-ink-soft">{patient.chiefComplaint}</p>

          {agent && variant === "owner" &&
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-teal-600/20 bg-teal-600/[0.04] px-4 py-3.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-600/10 text-teal-600">
                <SparklesIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-ink">
                  Assigned to{" "}
                  <Link to={DASHBOARD_ROUTES.agentDetail(agent.categoryId, agent.slug)} className="text-teal-600 hover:underline">{agent.name}</Link>
                </p>
                {patient.assignmentReasoning && <p className="mt-0.5 text-xs text-ink-muted">{patient.assignmentReasoning}</p>}
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ${patient.agentStatus === "active" ? "bg-success/10 text-success" : "bg-ink-muted/10 text-ink-muted"}`}>
                {patient.agentStatus === "active" ? "Active" : "Inactive"}
              </span>
            </div>
        }
        </div>
      }
    </div>
  );
}
