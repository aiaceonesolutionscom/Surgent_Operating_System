import React, { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon, PlusIcon, XIcon, CheckCircleIcon, XCircleIcon, LoaderIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useDoctors } from "../doctors/useDoctors";
import { useProcedures } from "../clinical/useProcedures";
import { useSurgeries } from "./useSurgeries";
import { listPracticeAppointments, checkSurgeryAvailability, type SurgeryAvailabilityCheckResponse } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

const DEFAULT_DURATION = 60;

export function SurgeryFormPage() {
  const { authedFetch } = usePlan();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const preselectedPatientId = searchParams.get("patient_id") || "";
  const preselectedProcedureId = searchParams.get("procedure_id") || "";
  const appointmentId = searchParams.get("appointment_id") || "";

  const { patients, loading: patientsLoading } = usePatients(authedFetch);
  const { doctors, loading: doctorsLoading } = useDoctors(authedFetch);
  const { procedures } = useProcedures(authedFetch);
  const { create } = useSurgeries(authedFetch);

  const [patientId, setPatientId] = useState(preselectedPatientId);
  const [doctorId, setDoctorId] = useState("");
  const [assistantDoctorId, setAssistantDoctorId] = useState("");
  const [procedureId, setProcedureId] = useState(preselectedProcedureId);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("09:00");
  const [durationMinutes, setDurationMinutes] = useState("");
  const [anesthesiaType, setAnesthesiaType] = useState("");
  const [facilityNote, setFacilityNote] = useState("");
  const [checklist, setChecklist] = useState<string[]>(["Consent signed", "Labs cleared", "Fasting confirmed"]);
  const [newChecklistItem, setNewChecklistItem] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── live doctor-availability gate ───────────────────────────────────────
  // The front desk's "is ye doctor us waqt available hai?" check, run as soon
  // as a doctor + date + time are on the form. Cleared on every field change;
  // a blueberry-grey "checking…" while the request is in flight, then green
  // (this slot works) or red + reasons (this slot doesn't).
  const [availability, setAvailability] = useState<SurgeryAvailabilityCheckResponse | null>(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);
  const availabilityTimer = useRef<number | null>(null);

  function buildIsoDate(): string | null {
    if (!date) return null;
    const [y, mo, d] = date.split("-").map(Number);
    const [hh, mm] = time.split(":").map(Number);
    if (!y || !mo || !d) return null;
    return new Date(y, mo - 1, d, hh, mm).toISOString();
  }

  const runAvailabilityCheck = useCallback(async () => {
    if (!authedFetch || !doctorId || !date || !time) {
      setAvailability(null);
      setCheckingAvailability(false);
      return;
    }
    const iso = buildIsoDate();
    if (!iso) return;
    setCheckingAvailability(true);
    setAvailability(null);
    try {
      const result = await checkSurgeryAvailability(authedFetch, {
        doctor_id: doctorId,
        scheduled_date: iso,
        duration_minutes: durationMinutes ? Number(durationMinutes) : DEFAULT_DURATION
      });
      setAvailability(result);
    } catch {
      setAvailability(null);
    } finally {
      setCheckingAvailability(false);
    }
  }, [authedFetch, doctorId, date, time, durationMinutes]);

  // Debounce so typing the duration or nudging the time doesn't hammer the API.
  useEffect(() => {
    if (availabilityTimer.current) window.clearTimeout(availabilityTimer.current);
    if (!doctorId || !date || !time) {
      setAvailability(null);
      setCheckingAvailability(false);
      return;
    }
    availabilityTimer.current = window.setTimeout(() => {
      void runAvailabilityCheck();
    }, 350);
    return () => {
      if (availabilityTimer.current) window.clearTimeout(availabilityTimer.current);
    };
  }, [runAvailabilityCheck, doctorId, date, time, durationMinutes]);

  // Appointment -> Surgery: when opened from the Front Desk (or any call
  // site) via ?appointment_id=..., pre-fill the patient, surgeon, and time
  // from that appointment and pin it as the surgery's source appointment.
  useEffect(() => {
    if (!appointmentId || !authedFetch) return;
    let cancelled = false;
    listPracticeAppointments(authedFetch)
      .then((appointments) => {
        if (cancelled) return;
        const appt = appointments.find((a) => a.id === appointmentId);
        if (!appt) return;
        setPatientId(appt.patient_id);
        setDoctorId(appt.doctor_id || "");
        const start = new Date(appt.start_time);
        setDate(`${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, "0")}-${String(start.getDate()).padStart(2, "0")}`);
        setTime(`${String(start.getHours()).padStart(2, "0")}:${String(start.getMinutes()).padStart(2, "0")}`);
      })
      .catch(() => { /* non-fatal: fall back to an empty, fully editable form */ })
      .finally(() => { cancelled = true; });
    return () => { cancelled = true; };
  }, [appointmentId, authedFetch]);

  const activeDoctors = doctors.filter((d) => d.isActive);

  function addChecklistItem() {
    if (!newChecklistItem.trim()) return;
    setChecklist((prev) => [...prev, newChecklistItem.trim()]);
    setNewChecklistItem("");
  }

  function removeChecklistItem(idx: number) {
    setChecklist((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!patientId || !doctorId || !date) return;
    // Requirement #1's gate: only an available doctor gets a booked surgery.
    if (!checkingAvailability && availability !== null && !availability.available) {
      setError("This doctor isn't available at the chosen time — pick another slot or surgeon.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const iso = buildIsoDate();
      if (!iso) {
        setError("Pick a valid date and time.");
        setSaving(false);
        return;
      }
      const created = await create({
        patient_id: patientId,
        doctor_id: doctorId,
        assistant_doctor_id: assistantDoctorId || null,
        procedure_id: procedureId || null,
        scheduled_appointment_id: appointmentId || null,
        scheduled_date: iso,
        duration_estimate_minutes: durationMinutes ? Number(durationMinutes) : DEFAULT_DURATION,
        anesthesia_type: anesthesiaType.trim() || null,
        facility_note: facilityNote.trim() || null,
        pre_op_checklist: checklist.map((item) => ({ item, checked: false }))
      });
      navigate(DASHBOARD_ROUTES.surgeryDetail(created!.id));
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't schedule this surgery — try again.");
      setSaving(false);
    }
  }

  const submitBlockedByAvailability = !checkingAvailability && availability !== null && !availability.available;

  return (
    <>
      <Link to={DASHBOARD_ROUTES.surgeries} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        <ArrowLeftIcon className="h-4 w-4" /> Back to Surgery
      </Link>
      <PageHeader title="Schedule surgery" subtitle="Pick a surgeon who's actually available at that time — then pin the case down with the pre-op checklist." />
      {appointmentId &&
      <p className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-teal-50 px-3.5 py-2 text-xs font-semibold text-teal-700">
        <ArrowLeftIcon className="h-3.5 w-3.5 rotate-180" /> Coming from an appointment — patient, surgeon, and time pre-filled and linked.
      </p>
      }

      <form onSubmit={handleSubmit} className="mt-6 max-w-2xl space-y-5 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Patient *</span>
            <select
              required
              disabled={patientsLoading}
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
              <option value="">Select a patient…</option>
              {patients.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Procedure</span>
            <select
              value={procedureId}
              onChange={(e) => setProcedureId(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
              <option value="">Not specified</option>
              {procedures.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Surgeon *</span>
            <select
              required
              disabled={doctorsLoading}
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
              <option value="">Select a surgeon…</option>
              {activeDoctors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Assistant surgeon</span>
            <select
              value={assistantDoctorId}
              onChange={(e) => setAssistantDoctorId(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
              <option value="">None</option>
              {activeDoctors.filter((d) => d.id !== doctorId).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Date *</span>
            <input
              required
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Time *</span>
            <input
              required
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Est. duration (min)</span>
            <input
              type="number"
              min="15"
              value={durationMinutes}
              onChange={(e) => setDurationMinutes(e.target.value)}
              placeholder={`${DEFAULT_DURATION}`}
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
        </div>

        {/* Doctor-availability gate — the front desk's "is he free?" moment. */}
        {doctorId && date && time &&
        <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${submitBlockedByAvailability ? "border-danger/30 bg-danger/5 text-danger" : availability?.available ? "border-success/30 bg-success/5 text-success" : "border-sand-200 bg-canvas text-ink-soft"}`}>
          {checkingAvailability ?
          <><LoaderIcon className="mt-0.5 h-4 w-4 shrink-0 animate-spin" /><span>Checking if this surgeon is available at that time…</span></> :
          submitBlockedByAvailability ?
          <><XCircleIcon className="mt-0.5 h-4 w-4 shrink-0" /><span>
              <span className="font-semibold">Surgeon not available.</span>
              <span className="mt-0.5 block text-xs opacity-90">{availability.reasons.join(" · ")}</span>
            </span></> :
          availability?.available ?
          <><CheckCircleIcon className="mt-0.5 h-4 w-4 shrink-0" /><span>
              <span className="font-semibold">Surgeon is available at this time.</span>
            </span></> :
          <span>Select a surgeon and time to check availability.</span>}
        </div>
        }

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Anesthesia type</span>
            <input
              value={anesthesiaType}
              onChange={(e) => setAnesthesiaType(e.target.value)}
              placeholder="General"
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Facility / OT note</span>
            <input
              value={facilityNote}
              onChange={(e) => setFacilityNote(e.target.value)}
              placeholder="OR 1"
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
        </div>

        <div>
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Pre-op checklist</span>
          <div className="space-y-2">
            {checklist.map((item, i) =>
            <div key={i} className="flex items-center gap-2 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink-soft">
                <span className="flex-1">{item}</span>
                <button type="button" onClick={() => removeChecklistItem(i)} className="text-ink-muted hover:text-danger">
                  <XIcon className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={newChecklistItem}
              onChange={(e) => setNewChecklistItem(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addChecklistItem(); } }}
              placeholder="Add a checklist item…"
              className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            <button
              type="button"
              onClick={addChecklistItem}
              className="flex items-center gap-1 rounded-xl border border-sand-200 px-3 py-2 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
              <PlusIcon className="h-3.5 w-3.5" /> Add
            </button>
          </div>
        </div>

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <div className="flex items-center justify-end gap-3 border-t border-sand-100 pt-5">
          <Link to={DASHBOARD_ROUTES.surgeries} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving || !patientId || !doctorId || !date || submitBlockedByAvailability}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
            {saving ? "Scheduling…" : "Schedule surgery"}
          </button>
        </div>
      </form>
    </>);

}