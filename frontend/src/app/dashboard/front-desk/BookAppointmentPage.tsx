import React, { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useDoctors } from "../doctors/useDoctors";
import { createAppointment } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

function toLocalInputValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Reuses the already-real POST /api/v1/appointments (Phase 2) — this page is
// the first UI in the dashboard to actually call it directly rather than an
// AI agent.
export function BookAppointmentPage() {
  const navigate = useNavigate();
  const { authedFetch } = usePlan();
  const { patients, loading: patientsLoading } = usePatients(authedFetch);
  const { doctors, loading: doctorsLoading } = useDoctors(authedFetch);
  const [searchParams] = useSearchParams();

  const now = new Date(Date.now() + 60 * 60 * 1000);
  const later = new Date(now.getTime() + 30 * 60 * 1000);

  // Pre-filled when reached from a specific patient's profile (e.g. Owner/
  // Doctor/Receptionist's "Book appointment" action) — staff shouldn't have
  // to re-search for the patient they're already looking at.
  const [patientId, setPatientId] = useState(searchParams.get("patientId") || "");
  const [doctorId, setDoctorId] = useState("");
  const [appointmentType, setAppointmentType] = useState("Consultation");
  const [startTime, setStartTime] = useState(toLocalInputValue(now));
  const [endTime, setEndTime] = useState(toLocalInputValue(later));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = Boolean(patientId && appointmentType.trim() && startTime && endTime) && !saving;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !authedFetch) return;
    setSaving(true);
    setError(null);
    try {
      const appointment = await createAppointment(authedFetch, {
        patient_id: patientId,
        doctor_id: doctorId || null,
        appointment_type: appointmentType.trim(),
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        notes: notes.trim() || null
      });
      navigate(DASHBOARD_ROUTES.patientDetail(appointment.patient_id));
    } catch (err: unknown) {
      // Surface the real reason (e.g. "Dr. X doesn't work on Tuesdays", or
      // an overlapping-appointment conflict) instead of a generic message —
      // this is exactly what "found out too late the doctor wasn't
      // available" needs to catch at booking time, not after.
      setError(err instanceof Error && err.message ? err.message : "Couldn't book this appointment — check the times and try again.");
      setSaving(false);
    }
  }

  const loading = patientsLoading || doctorsLoading;

  return (
    <>
      <Link
        to={DASHBOARD_ROUTES.frontDesk}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to Front Desk
      </Link>

      <PageHeader title="Book appointment" subtitle="Schedule a new appointment for any patient and doctor." />

      {loading ?
      <p className="mt-6 text-sm text-ink-muted">Loading…</p> :

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Patient *</span>
            <select
            required
            value={patientId}
            onChange={(e) => setPatientId(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">

              <option value="">Select a patient…</option>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Doctor (optional)</span>
            <select
            value={doctorId}
            onChange={(e) => setDoctorId(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">

              <option value="">Unassigned</option>
              {doctors.filter((d) => d.isActive).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Appointment type *</span>
            <input
            required
            value={appointmentType}
            onChange={(e) => setAppointmentType(e.target.value)}
            placeholder="Consultation"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

          </label>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Start *</span>
              <input
              required
              type="datetime-local"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">End *</span>
              <input
              required
              type="datetime-local"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
          </div>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Notes</span>
            <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

          </label>

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <div className="flex items-center justify-end gap-3">
            <Link
            to={DASHBOARD_ROUTES.frontDesk}
            className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

              Cancel
            </Link>
            <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

              {saving ? "Booking…" : "Book appointment"}
            </button>
          </div>
        </form>
      }
    </>);

}
