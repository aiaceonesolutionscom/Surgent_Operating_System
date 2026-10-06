import { useState } from "react";
import { Link } from "react-router-dom";
import { LayoutDashboardIcon, StethoscopeIcon, CalendarIcon, CameraIcon, FileTextIcon, ReceiptIcon, MessageCircleIcon, ActivityIcon, CalendarPlusIcon } from "lucide-react";
import type { Patient } from "./types";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { PatientHeaderCard } from "./PatientHeaderCard";
import { PatientTabShell, type PatientTab } from "./PatientTabShell";
import { PatientOverviewTab } from "./PatientOverviewTab";
import { PatientAppointmentsTab } from "./PatientAppointmentsTab";
import { PatientActivityTab } from "./PatientActivityTab";
import { DoctorAssignmentControl } from "./DoctorAssignmentControl";
import { ArchivePatientControl } from "./ArchivePatientControl";
import { ClinicalSection } from "../clinical/ClinicalSection";
import { PatientPhotosGallery } from "../clinical/PatientPhotosGallery";
import { ConsentDocumentsList } from "../clinical/ConsentDocumentsList";
import { VisitDocumentsList } from "../clinical/VisitDocumentsList";
import { InvoicesSection } from "../billing-invoices/InvoicesSection";
import { PatientMedicalProfile } from "./PatientMedicalProfile";
import { PatientPortalLinkCard } from "./PatientPortalLinkCard";
import { SessionsView } from "../sessions/SessionsView";
import { useSessions } from "../sessions/useSessions";

// Owner's "complete patient + clinic administration" view — every section
// the redesign's access matrix grants Owner, organized into real tabs
// instead of one long scrolling page.
export function OwnerPatientDetail({ patient: initialPatient }: { patient: Patient }) {
  const [patient, setPatient] = useState(initialPatient);
  const { sessions, loading: sessionsLoading, error: sessionsError, refetch } = useSessions();
  const patientSessions = sessions.filter((s) => s.patientId === patient.id);

  const tabs: PatientTab[] = [
    {
      id: "overview", label: "Overview", icon: LayoutDashboardIcon, content: (
        <div><PatientPortalLinkCard patientId={patient.id} /><PatientOverviewTab patient={patient} variant="owner" /></div>
      )
    },
    {
      id: "clinical", label: "Clinical", icon: StethoscopeIcon, content: (
        <div><PatientMedicalProfile patientId={patient.id} /><ClinicalSection patientId={patient.id} /></div>
      )
    },
    { id: "appointments", label: "Appointments", icon: CalendarIcon, content: <PatientAppointmentsTab patientId={patient.id} /> },
    { id: "photos", label: "Photos", icon: CameraIcon, content: <PatientPhotosGallery patientId={patient.id} /> },
    { id: "consents", label: "Consents & Documents", icon: FileTextIcon, content: <div><VisitDocumentsList patientId={patient.id} /><ConsentDocumentsList patientId={patient.id} /></div> },
    { id: "billing", label: "Billing", icon: ReceiptIcon, content: <InvoicesSection patientId={patient.id} /> },
    {
      id: "communication", label: "Communication", icon: MessageCircleIcon, content: (
        sessionsLoading ? <p className="rounded-3xl border border-sand-200 bg-white p-8 text-center text-sm text-ink-muted">Loading…</p> :
        sessionsError ? <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center"><p className="text-sm text-danger">{sessionsError}</p><button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button></div> :
        <SessionsView sessions={patientSessions} />
      )
    },
    { id: "activity", label: "Activity", icon: ActivityIcon, content: <PatientActivityTab patientId={patient.id} /> }
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
        <ArchivePatientControl
          patientId={patient.id}
          isArchived={!!patient.isArchived}
          onChanged={(archived) => setPatient((p) => ({ ...p, isArchived: archived }))} />
      </PatientHeaderCard>

      <PatientTabShell tabs={tabs} />
    </>
  );
}
