import { useParams } from "react-router-dom";
import { ShieldAlertIcon } from "lucide-react";
import { usePatients } from "./usePatients";
import { ComingSoon } from "../components/ComingSoon";
import { usePlan } from "../plan/PlanContext";
import { OwnerPatientDetail } from "./OwnerPatientDetail";
import { DoctorPatientDetail } from "./DoctorPatientDetail";
import { ReceptionistPatientDetail } from "./ReceptionistPatientDetail";

// Thin role dispatcher — mirrors front-desk/FrontDeskPage.tsx's own
// Owner-vs-Receptionist split. The three views below are genuinely
// different workspaces (complete administration / clinical / front-desk
// operations), not the same page with sections hidden — see each
// component's own docstring for exactly what it does and doesn't render.
// Backend enforces the same boundaries independently (patients_router.py,
// server/patient_access.py) — this dispatch is a UX convenience, not the
// security boundary itself.
export function PatientDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch, role } = usePlan();
  const { getPatient, loading } = usePatients(authedFetch, { includeArchived: role === "owner" });
  const patient = id ? getPatient(id) : undefined;

  if (loading) return null;

  if (!patient) {
    return <ComingSoon icon={ShieldAlertIcon} title="Patient not found" body="This patient record doesn't exist, or isn't assigned to you." phase="—" />;
  }

  if (role === "doctor") return <DoctorPatientDetail patient={patient} />;
  if (role === "receptionist") return <ReceptionistPatientDetail patient={patient} />;
  return <OwnerPatientDetail patient={patient} />;
}
