import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { SearchIcon, UsersIcon, PlusIcon, ArchiveIcon, ShieldCheckIcon, ShieldOffIcon, StethoscopeIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePatients } from "./usePatients";
import { DASHBOARD_ROUTES } from "../constants/routes";
import type { Patient } from "./types";
import { usePlan } from "../plan/PlanContext";

const STATUS_CLASS: Record<Patient["status"], string> = {
  active: "bg-success/10 text-success",
  lead: "bg-warning/10 text-warning",
  inactive: "bg-ink-muted/10 text-ink-muted"
};

const STATUS_LABEL: Record<Patient["status"], string> = {
  active: "Active patient",
  lead: "Lead",
  inactive: "Inactive"
};

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function PortalBadge({ patient }: { patient: Patient }) {
  if (!patient.portalEnabled) {
    return (
      <span className="flex items-center gap-1 text-xs text-ink-muted">
        <ShieldOffIcon className="h-3 w-3" /> Not active
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 text-xs font-medium text-success">
      <ShieldCheckIcon className="h-3 w-3" /> Active
    </span>
  );
}

function PatientCell({ patient }: { patient: Patient }) {
  return (
    <Link to={DASHBOARD_ROUTES.patientDetail(patient.id)} className="flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sand-200 text-sm font-bold text-ink-soft">
        {patient.initial}
      </span>
      <span>
        <span className="block font-semibold text-ink hover:text-teal-600">{patient.name}</span>
        <span className="block text-xs text-ink-muted">{patient.email}</span>
      </span>
    </Link>
  );
}

// Three genuinely different column sets — Owner runs the whole clinic
// (status/doctor/balance-adjacent/portal), Doctor works clinically (their
// own patients, treatment/follow-up focus, no financial columns), Receptionist
// runs the front desk (phone/appointment/portal, no clinical detail). Matches
// the redesign's explicit "do not show the same generic patient list to
// every role" requirement.
export function PatientsPage() {
  const { authedFetch, role } = usePlan();
  const [showArchived, setShowArchived] = useState(false);
  const canSeeArchived = role === "owner" || role === "receptionist";
  const { patients, loading } = usePatients(authedFetch, { includeArchived: canSeeArchived && showArchived });
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) => p.name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q) || p.phone.toLowerCase().includes(q)
    );
  }, [patients, query]);

  const subtitle =
    role === "doctor"
      ? "Your assigned patients — clinical status, visits, and follow-ups."
      : role === "receptionist"
      ? "Front-desk patient operations — contact, doctor, and appointments."
      : "Every patient record across the clinic — doctor, visits, and portal status.";

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <PageHeader title="Patients" subtitle={subtitle} />
        <Link
          to={DASHBOARD_ROUTES.patientNew}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          <PlusIcon className="h-4 w-4" /> Add patient
        </Link>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2.5">
        <div className="flex flex-1 items-center gap-2.5 rounded-xl border border-sand-200 bg-white px-3.5 py-2.5">
          <SearchIcon className="h-4 w-4 text-ink-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search patients by name, email, or phone…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />
        </div>
        {canSeeArchived &&
        <button
          type="button"
          onClick={() => setShowArchived((v) => !v)}
          className={`flex shrink-0 items-center gap-1.5 rounded-xl border px-3.5 py-2.5 text-xs font-semibold transition-colors ${
          showArchived ? "border-teal-600/40 bg-teal-600/10 text-teal-600" : "border-sand-200 text-ink-soft hover:border-teal-600/40"}`}>
            <ArchiveIcon className="h-3.5 w-3.5" /> {showArchived ? "Showing archived" : "Show archived"}
          </button>
        }
      </div>

      <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        {loading ?
        <p className="px-5 py-8 text-center text-sm text-ink-muted">Loading…</p> :
        filtered.length === 0 ?
        <EmptyState icon={UsersIcon} title="No patients found" body={role === "doctor" ? "No patients assigned to you yet." : "Try a different search term."} /> :

        <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-5 py-3 font-semibold">Patient</th>
                {role === "receptionist" && <th className="px-5 py-3 font-semibold">Phone</th>}
                {role !== "doctor" && <th className="px-5 py-3 font-semibold">Assigned doctor</th>}
                {role === "owner" && <th className="px-5 py-3 font-semibold">Status</th>}
                <th className="px-5 py-3 font-semibold">Last visit</th>
                <th className="px-5 py-3 font-semibold">Next appointment</th>
                {role !== "owner" && <th className="px-5 py-3 font-semibold">Status</th>}
                {role !== "doctor" && <th className="px-5 py-3 font-semibold">Portal</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((p) => (
                <tr key={p.id} className={`border-b border-sand-200/70 last:border-0 hover:bg-sand-100 ${p.isArchived ? "opacity-50" : ""}`}>
                  <td className="px-5 py-3.5">
                    <PatientCell patient={p} />
                    {p.isArchived && <span className="ml-12 mt-0.5 block text-[11px] font-semibold text-ink-muted">Archived</span>}
                  </td>
                  {role === "receptionist" && <td className="px-5 py-3.5 text-ink-soft">{p.phone || "—"}</td>}
                  {role !== "doctor" &&
                  <td className="px-5 py-3.5">
                    {p.assignedDoctorName ? (
                      <span className="flex items-center gap-1.5 text-xs font-medium text-ink-soft">
                        <StethoscopeIcon className="h-3 w-3 text-teal-600" /> {p.assignedDoctorName}
                      </span>
                    ) : (
                      <span className="text-xs text-ink-muted">Unassigned</span>
                    )}
                  </td>
                  }
                  {role === "owner" &&
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_CLASS[p.status]}`}>
                      {STATUS_LABEL[p.status]}
                    </span>
                  </td>
                  }
                  <td className="px-5 py-3.5 tabular-nums text-ink-soft">{formatDate(p.lastVisit)}</td>
                  <td className="px-5 py-3.5 tabular-nums text-ink-soft">{formatDate(p.nextAppointment)}</td>
                  {role !== "owner" &&
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_CLASS[p.status]}`}>
                      {STATUS_LABEL[p.status]}
                    </span>
                  </td>
                  }
                  {role !== "doctor" && <td className="px-5 py-3.5"><PortalBadge patient={p} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        }
      </div>
    </>);

}
