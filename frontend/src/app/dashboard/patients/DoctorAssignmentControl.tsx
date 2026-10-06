import { useState } from "react";
import { StethoscopeIcon, ChevronDownIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useDoctors } from "../doctors/useDoctors";
import { assignPatientDoctor } from "../../../api/entities";

// Owner and Receptionist can both assign/reassign — matches
// patients_router.py's require_role(OWNER, RECEPTIONIST) on
// /assign-doctor. This is the one durable doctor-patient link a Doctor's
// own hard-restricted access is scoped against (server/patient_access.py),
// so changing it is a real, audited action, not a cosmetic field edit.
export function DoctorAssignmentControl({
  patientId,
  currentDoctorId,
  currentDoctorName,
  onAssigned
}: {
  patientId: string;
  currentDoctorId: string | null;
  currentDoctorName: string | null;
  onAssigned: (doctorId: string | null, doctorName: string | null) => void;
}) {
  const { authedFetch } = usePlan();
  const { doctors } = useDoctors(authedFetch);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAssign(doctorId: string | null) {
    if (!authedFetch) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await assignPatientDoctor(authedFetch, patientId, doctorId);
      onAssigned(updated.assigned_doctor_id, updated.assigned_doctor_name);
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't assign doctor.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={busy}
        className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3.5 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
        <StethoscopeIcon className="h-3.5 w-3.5" />
        {currentDoctorName || "Assign doctor"}
        <ChevronDownIcon className="h-3 w-3" />
      </button>

      {open &&
      <div className="absolute right-0 z-20 mt-1.5 w-56 rounded-xl border border-sand-200 bg-white p-1.5 shadow-[0_8px_24px_rgba(15,23,42,0.12)]">
          {doctors.filter((d) => d.isActive).map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => handleAssign(d.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-sand-100 ${d.id === currentDoctorId ? "font-semibold text-teal-600" : "text-ink-soft"}`}>
              {d.name}
            </button>
          ))}
          {currentDoctorId &&
          <button
            type="button"
            onClick={() => handleAssign(null)}
            className="mt-1 flex w-full items-center gap-2 rounded-lg border-t border-sand-100 px-3 py-2 text-left text-xs font-medium text-ink-muted hover:text-danger">
              Unassign
            </button>
          }
          {error && <p className="px-3 py-1.5 text-xs text-danger">{error}</p>}
        </div>
      }
    </div>);
}
