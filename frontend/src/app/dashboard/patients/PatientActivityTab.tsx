import { useEffect, useState } from "react";
import { ActivityIcon, UserIcon, ClockIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { getPatientAuditLog, type PatientAuditLogEntry } from "../../../api/entities";

// Owner-only (backend enforces the same via require_role(OWNER) on
// GET /patients/{id}/audit-log) — "who did what to this record and when,"
// assembled across every resource type that touches the patient (photos,
// consent, appointments, treatment plans, invoices — see
// services/audit/patient_audit_service.py).
const ACTION_LABELS: Record<string, string> = {
  "patient.created": "Patient record created",
  "patient.updated": "Patient details updated",
  "patient.stage_changed": "Funnel stage changed",
  "patient.doctor_assigned": "Doctor assigned",
  "patient.doctor_unassigned": "Doctor unassigned",
  "patient.archived": "Patient archived",
  "patient.restored": "Patient restored",
  "patient.view": "Patient record viewed",
  "photo.view": "Photos viewed",
  "photo.delete": "Photo deleted",
  "consent.sign": "Consent signed",
  "consent.void": "Consent voided",
  "consent.discussed": "Consent discussed with patient",
  "appointment.reschedule": "Appointment rescheduled",
  "appointment.cancel": "Appointment cancelled",
  "recovery.checkin.create": "Recovery check-in submitted",
  "recovery.checkin.review": "Recovery check-in reviewed",
  "portal_login.success": "Patient logged into portal",
  "portal_login.failed": "Failed portal login attempt"
};

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit"
  });
}

export function PatientActivityTab({ patientId }: { patientId: string }) {
  const { authedFetch } = usePlan();
  const [entries, setEntries] = useState<PatientAuditLogEntry[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!authedFetch) {
      setEntries([]);
      return;
    }
    getPatientAuditLog(authedFetch, patientId)
      .then((data) => { if (!cancelled) setEntries(data); })
      .catch(() => { if (!cancelled) setEntries([]); });
    return () => { cancelled = true; };
  }, [authedFetch, patientId]);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2 border-b border-sand-200 px-5 py-4">
        <ActivityIcon className="h-4 w-4 text-teal-600" />
        <p className="text-sm font-bold text-ink">Activity &amp; audit history</p>
      </div>

      {entries === null &&
      <p className="px-5 py-8 text-center text-sm text-ink-muted">Loading…</p>
      }
      {entries !== null && entries.length === 0 &&
      <p className="px-5 py-8 text-center text-sm text-ink-muted">No activity recorded yet.</p>
      }
      {entries !== null && entries.length > 0 &&
      <div className="divide-y divide-sand-100">
          {entries.map((e) => (
            <div key={e.id} className="flex items-start gap-3 px-5 py-3.5">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sand-100 text-ink-muted">
                <ActivityIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-ink">{ACTION_LABELS[e.action] || e.action}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-muted">
                  <span className="flex items-center gap-1">
                    <UserIcon className="h-3 w-3" /> {e.actor_name || (e.actor_type === "patient_portal" ? "Patient" : e.actor_type === "ai_agent" ? "AI Receptionist" : "System")}
                  </span>
                  <span className="flex items-center gap-1">
                    <ClockIcon className="h-3 w-3" /> {formatWhen(e.created_at)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      }
    </div>
  );
}
