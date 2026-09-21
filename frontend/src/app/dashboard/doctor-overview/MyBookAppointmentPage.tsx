import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon, UserCircleIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { createAppointment, getMyDoctor } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

function toLocalInputValue(date: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

// Doctor-scoped booking — the Doctor's own "Book" action. Same backend call as
// the front desk's BookAppointmentPage, but the doctor is permanently pinned
// (doctor_id = self via getMyDoctor) so a doctor can only ever add themselves
// to a patient's schedule, not shuffle other doctors around.
export function MyBookAppointmentPage() {
  const navigate = useNavigate();
  const { authedFetch } = usePlan();
  const { patients, loading: patientsLoading } = usePatients(authedFetch);
  const [searchParams] = useSearchParams();

  const [doctorId, setDoctorId] = useState<string | null>(null);
  const [doctorLoading, setDoctorLoading] = useState(true);

  const now = new Date(Date.now() + 60 * 60 * 1000);
  const later = new Date(now.getTime() + 30 * 60 * 1000);

  const [patientId, setPatientId] = useState(searchParams.get("patientId") || "");
  const [appointmentType, setAppointmentType] = useState("Consultation");
  const [startTime, setStartTime] = useState(toLocalInputValue(now));
  const [endTime, setEndTime] = useState(toLocalInputValue(later));
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) {
        setDoctorLoading(false);
        return;
      }
      try {
        const doctor = await getMyDoctor(authedFetch);
        if (!cancelled) setDoctorId(doctor?.id ?? null);
      } catch {
        if (!cancelled) setDoctorId(null);
      } finally {
        if (!cancelled) setDoctorLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const canSubmit = Boolean(doctorId && patientId && appointmentType.trim() && startTime && endTime) && !saving;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || !doctorId) return;
    setSaving(true);
    setError(null);
    try {
      await createAppointment(authedFetch!, {
        patient_id: patientId,
        doctor_id: doctorId,
        appointment_type: appointmentType.trim(),
        start_time: new Date(startTime).toISOString(),
        end_time: new Date(endTime).toISOString(),
        notes: notes.trim() || null
      });
      navigate(DASHBOARD_ROUTES.myCalendar);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't book this appointment — check the times and try again.");
      setSaving(false);
    }
  }

  const loading = patientsLoading || doctorLoading;

  return (
    <>
      <Link
        to={DASHBOARD_ROUTES.myCalendar}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to My Calendar
      </Link>

      <PageHeader title="Book an appointment" subtitle="Add yourself to a patient's schedule — the appointment lands straight on your calendar." />

      {loading ?
      <p className="mt-6 text-sm text-ink-muted">Loading…</p> :

      !doctorId && !authedFetch ?
      <div className="mt-6 max-w-xl rounded-3xl border border-sand-200 bg-white p-6 text-sm text-ink-muted shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          Booking needs a linked doctor account on the backend — sign in / preview may work in read-only demo mode, but real bookings need the API up.
        </div> :

      <form onSubmit={handleSubmit} className="mt-6 max-w-xl space-y-4 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <div className="flex items-center gap-2.5 rounded-xl bg-teal-600/[0.06] px-4 py-3">
            <UserCircleIcon className="h-4 w-4 text-teal-600" />
            <p className="text-sm font-medium text-ink">Booking as <span className="font-semibold text-teal-600">you</span> — no doctor selector needed</p>
          </div>

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
          to={DASHBOARD_ROUTES.myCalendar}
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