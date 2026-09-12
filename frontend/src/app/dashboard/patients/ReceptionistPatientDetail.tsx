import React, { useState } from "react";
import { Link } from "react-router-dom";
import { LayoutDashboardIcon, CalendarIcon, FileTextIcon, ReceiptIcon, CalendarPlusIcon, SendIcon } from "lucide-react";
import type { Patient } from "./types";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { PatientHeaderCard } from "./PatientHeaderCard";
import { PatientTabShell, type PatientTab } from "./PatientTabShell";
import { PatientOverviewTab } from "./PatientOverviewTab";
import { PatientAppointmentsTab } from "./PatientAppointmentsTab";
import { DoctorAssignmentControl } from "./DoctorAssignmentControl";
import { ArchivePatientControl } from "./ArchivePatientControl";
import { ConsentDocumentsList } from "../clinical/ConsentDocumentsList";
import { InvoicesSection } from "../billing-invoices/InvoicesSection";
import { usePlan } from "../plan/PlanContext";
import { enablePatientPortal, resendPatientPortalInvite } from "../../../api/entities";

// Receptionist's Front-Desk Operations view — no clinical notes, no medical
// profile, no clinical photos ("do not render empty cards... if the
// receptionist does not have permission, simply don't render those
// sections" — matches the backend's own Owner/Doctor-only gate on those
// domains, so there's nothing here to even fetch).
export function ReceptionistPatientDetail({ patient: initialPatient }: { patient: Patient }) {
  const { authedFetch } = usePlan();
  const [patient, setPatient] = useState(initialPatient);
  const [inviteStatus, setInviteStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handlePortalInvite() {
    if (!authedFetch) return;
    setBusy(true);
    setInviteStatus(null);
    try {
      if (patient.portalEnabled) {
        await resendPatientPortalInvite(authedFetch, patient.id);
        setInviteStatus("Invite resent.");
      } else {
        const res = await enablePatientPortal(authedFetch, patient.id);
        setPatient((p) => ({ ...p, portalEnabled: true, portalId: res.portal_id }));
        setInviteStatus(res.invite_sent ? "Portal enabled and invite sent." : "Portal enabled — invite couldn't be delivered, check phone/email on file.");
      }
    } catch (err) {
      setInviteStatus(err instanceof Error ? err.message : "Couldn't send the invite.");
    } finally {
      setBusy(false);
    }
  }

  const tabs: PatientTab[] = [
    { id: "overview", label: "Overview", icon: LayoutDashboardIcon, content: <PatientOverviewTab patient={patient} variant="receptionist" /> },
    { id: "appointments", label: "Appointments", icon: CalendarIcon, content: <PatientAppointmentsTab patientId={patient.id} /> },
    { id: "consents", label: "Consents / Forms", icon: FileTextIcon, content: <ConsentDocumentsList patientId={patient.id} /> },
    { id: "billing", label: "Billing", icon: ReceiptIcon, content: <InvoicesSection patientId={patient.id} /> }
  ];

  return (
    <>
      <Link to={DASHBOARD_ROUTES.patients} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        Back to patients
      </Link>

      <PatientHeaderCard patient={patient}>
        <Link
          to={`${DASHBOARD_ROUTES.bookAppointment}?patientId=${patient.id}`}
          className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700">
          <CalendarPlusIcon className="h-3.5 w-3.5" /> Book appointment
        </Link>
        <DoctorAssignmentControl
          patientId={patient.id}
          currentDoctorId={patient.assignedDoctorId ?? null}
          currentDoctorName={patient.assignedDoctorName ?? null}
          onAssigned={(doctorId, doctorName) => setPatient((p) => ({ ...p, assignedDoctorId: doctorId, assignedDoctorName: doctorName }))} />
        <button
          type="button"
          onClick={handlePortalInvite}
          disabled={busy}
          className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
          <SendIcon className="h-3.5 w-3.5" /> {patient.portalEnabled ? "Resend portal invite" : "Send portal invite"}
        </button>
        <ArchivePatientControl
          patientId={patient.id}
          isArchived={!!patient.isArchived}
          onChanged={(archived) => setPatient((p) => ({ ...p, isArchived: archived }))} />
      </PatientHeaderCard>
      {inviteStatus && <p className="-mt-4 mb-4 text-xs text-ink-muted">{inviteStatus}</p>}

      <PatientTabShell tabs={tabs} />
    </>
  );
}
