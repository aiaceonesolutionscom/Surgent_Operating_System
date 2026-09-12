import React from "react";
import { Link } from "react-router-dom";
import { LayoutDashboardIcon, StethoscopeIcon, CameraIcon, FileTextIcon, CalendarIcon, CalendarPlusIcon, MessageCircleIcon } from "lucide-react";
import type { Patient } from "./types";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { PatientHeaderCard } from "./PatientHeaderCard";
import { PatientTabShell, type PatientTab } from "./PatientTabShell";
import { PatientOverviewTab } from "./PatientOverviewTab";
import { PatientAppointmentsTab } from "./PatientAppointmentsTab";
import { ClinicalSection } from "../clinical/ClinicalSection";
import { PatientPhotosGallery } from "../clinical/PatientPhotosGallery";
import { ConsentDocumentsList } from "../clinical/ConsentDocumentsList";
import { PatientMedicalProfile } from "./PatientMedicalProfile";
import { SessionsView } from "../sessions/SessionsView";
import { useSessions } from "../sessions/useSessions";

// Doctor's Clinical Workspace — clinical detail only. No billing, no
// portal-credential management, no lead/CRM information — matches the
// redesign's explicit boundary ("Doctor should NOT see the Owner's
// business/administrative patient workspace"). Communication is scoped to
// THIS patient only (server-enforced via patient_id + verify_doctor_access
// in conversations_controllers.py) — never the practice-wide lead/CRM
// inbox, which stays Owner/Receptionist-only (see Sidebar.tsx).
export function DoctorPatientDetail({ patient }: { patient: Patient }) {
  const { sessions, loading: sessionsLoading, error: sessionsError, refetch, resolve, loadMessages, sendMessage } = useSessions(undefined, patient.id);
  const patientSessions = sessions.filter((s) => s.patientId === patient.id);

  const tabs: PatientTab[] = [
    { id: "overview", label: "Clinical overview", icon: LayoutDashboardIcon, content: <PatientOverviewTab patient={patient} variant="doctor" /> },
    {
      id: "clinical", label: "Consultations & treatment", icon: StethoscopeIcon, content: (
        <div><PatientMedicalProfile patientId={patient.id} /><ClinicalSection patientId={patient.id} /></div>
      )
    },
    { id: "photos", label: "Photos", icon: CameraIcon, content: <PatientPhotosGallery patientId={patient.id} /> },
    { id: "consents", label: "Consents", icon: FileTextIcon, content: <ConsentDocumentsList patientId={patient.id} /> },
    { id: "appointments", label: "Appointments", icon: CalendarIcon, content: <PatientAppointmentsTab patientId={patient.id} /> },
    {
      id: "communication", label: "Communication", icon: MessageCircleIcon, content: (
        sessionsLoading ? <p className="rounded-3xl border border-sand-200 bg-white p-8 text-center text-sm text-ink-muted">Loading…</p> :
        sessionsError ? <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center"><p className="text-sm text-danger">{sessionsError}</p><button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button></div> :
        <SessionsView
          sessions={patientSessions}
          onLoadMessages={loadMessages}
          onResolve={resolve}
          onSendMessage={sendMessage} />
      )
    }
  ];

  return (
    <>
      <Link to={DASHBOARD_ROUTES.patients} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        Back to my patients
      </Link>

      <PatientHeaderCard patient={patient}>
        <Link
          to={`${DASHBOARD_ROUTES.myBook}?patientId=${patient.id}`}
          className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-3.5 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700">
          <CalendarPlusIcon className="h-3.5 w-3.5" /> Book appointment
        </Link>
      </PatientHeaderCard>

      <PatientTabShell tabs={tabs} />
    </>
  );
}
