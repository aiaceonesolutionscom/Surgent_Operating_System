import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeftIcon, SparklesIcon, UserIcon, ScissorsIcon, SearchIcon, CheckCircle2Icon, KeyIcon,
  CalendarPlusIcon, ShieldCheckIcon, ReceiptIcon, XIcon, AlertCircleIcon, MessageCircleIcon
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePatients } from "./usePatients";
import { classifyPatient } from "./classifyPatient";
import type { Patient } from "./types";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import { useDoctors } from "../doctors/useDoctors";
import { useProcedures } from "../clinical/useProcedures";
import {
  enablePatientPortal, createAppointment, createSurgery, createConsentDocument, createInvoice,
  CONSENT_DOCUMENT_TYPES
} from "../../../api/entities";

function normalizePhone(value: string): string {
  return value.replace(/\D/g, "");
}

// Front-desk duplicate-prevention: search by phone before creating a new
// record, matching how a real clinic works — a patient calling or walking
// in a second time should land back on their existing profile, not spawn a
// second one. Digit-suffix match (last 10 digits) so "+92 312 1234567" and
// "03121234567" resolve to the same person, same normalization the Patient
// Portal's own phone+OTP lookup uses server-side.
function findByPhone(patients: Patient[], phone: string): Patient | null {
  const digits = normalizePhone(phone);
  if (digits.length < 6) return null;
  const suffix = digits.slice(-10);
  return patients.find((p) => normalizePhone(p.phone).endsWith(suffix)) || null;
}

function defaultDateTimeLocal(hoursFromNow = 24) {
  const d = new Date(Date.now() + hoursFromNow * 60 * 60 * 1000);
  d.setMinutes(0, 0, 0);
  return d.toISOString().slice(0, 16);
}

interface CreationOutcome {
  label: string;
  ok: boolean;
  detail?: string;
}

export function PatientFormPage() {
  const { authedFetch } = usePlan();
  const { patients, addPatient } = usePatients(authedFetch);
  const { doctors } = useDoctors(authedFetch);
  const { procedures } = useProcedures(authedFetch);

  const [step, setStep] = useState<"search" | "create" | "done">("search");
  const [savedPatientId, setSavedPatientId] = useState<string | null>(null);
  const [searchPhone, setSearchPhone] = useState("");
  const [searchedOnce, setSearchedOnce] = useState(false);
  const foundPatient = searchedOnce ? findByPhone(patients, searchPhone) : null;

  // --- contact & profile ---------------------------------------------------
  const [name, setName] = useState("");
  const [fatherName, setFatherName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [hasWhatsapp, setHasWhatsapp] = useState(true);
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [pregnancyStatus, setPregnancyStatus] = useState("");
  const [occupation, setOccupation] = useState("");
  const [showMoreDetails, setShowMoreDetails] = useState(false);
  const [emergencyContactName, setEmergencyContactName] = useState("");
  const [emergencyContactPhone, setEmergencyContactPhone] = useState("");
  const [emergencyContactRelationship, setEmergencyContactRelationship] = useState("");
  const [assignedDoctorId, setAssignedDoctorId] = useState("");

  // --- why they're here ------------------------------------------------
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [needsSurgery, setNeedsSurgery] = useState(false);

  const [wantAppointment, setWantAppointment] = useState(true);
  const [appointmentType, setAppointmentType] = useState("Consultation");
  const [appointmentAt, setAppointmentAt] = useState(() => defaultDateTimeLocal());

  const [wantSurgery, setWantSurgery] = useState(false);
  const [surgeryProcedureId, setSurgeryProcedureId] = useState("");
  const [surgeryAt, setSurgeryAt] = useState(() => defaultDateTimeLocal(24 * 7));

  const [wantConsent, setWantConsent] = useState(false);
  const [consentType, setConsentType] = useState<string>(CONSENT_DOCUMENT_TYPES[0]);

  const [wantInvoice, setWantInvoice] = useState(false);
  const [invoiceDescription, setInvoiceDescription] = useState("");
  const [invoiceAmount, setInvoiceAmount] = useState("");

  const [sendPortalAccess, setSendPortalAccess] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [portalNote, setPortalNote] = useState<string | null>(null);
  const [outcomes, setOutcomes] = useState<CreationOutcome[]>([]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearchedOnce(true);
  }

  function proceedToCreate() {
    setPhone(searchPhone);
    setStep("create");
  }

  // Live preview — the same classifyPatient() call that runs on submit, so
  // what's shown here is exactly what will be saved, not a separate guess.
  const preview = useMemo(() => {
    if (!chiefComplaint.trim()) return null;
    return classifyPatient(chiefComplaint, needsSurgery);
  }, [chiefComplaint, needsSurgery]);

  const canSubmit = name.trim().length > 1 && chiefComplaint.trim().length > 3;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit || saving) return;
    setSaving(true);
    setSaveError(null);

    const classification = classifyPatient(chiefComplaint, needsSurgery);
    const patient: Patient = {
      id: `p${Date.now()}`,
      name: name.trim(),
      initial: name.trim()[0]?.toUpperCase() || "?",
      email: email.trim(),
      phone: phone.trim(),
      status: "lead",
      lastVisit: null,
      nextAppointment: null,
      procedures: [],
      consentOnFile: false,
      chiefComplaint: chiefComplaint.trim(),
      needsSurgery,
      assignedAgentSlug: classification.agentSlug,
      assignedCategoryId: classification.categoryId,
      assignmentReasoning: classification.reasoning,
      agentStatus: "active",
      lifecycleStage: "inquiry",
      lostReason: null,
      source: null
    };

    const saved = await addPatient(patient, {
      date_of_birth: dateOfBirth || null,
      gender: gender || null,
      father_name: fatherName.trim() || null,
      pregnancy_status: gender === "female" ? pregnancyStatus || null : null,
      occupation: occupation.trim() || null,
      emergency_contact_name: emergencyContactName.trim() || null,
      emergency_contact_phone: emergencyContactPhone.trim() || null,
      emergency_contact_relationship: emergencyContactRelationship.trim() || null,
      assigned_doctor_id: assignedDoctorId || null,
      preferred_channel: hasWhatsapp && phone.trim() ? "whatsapp" : null
    });
    if (!saved) {
      setSaveError("Couldn't save — this browser's storage is full or unavailable. Please try again.");
      setSaving(false);
      return;
    }

    setSavedPatientId(saved.id);

    // The sub-records below only make sense once this patient really
    // exists on the backend (not the offline/local-storage fallback) — same
    // gate the portal-invite step already used.
    const results: CreationOutcome[] = [];
    if (authedFetch) {
      if (wantAppointment && appointmentAt) {
        try {
          const start = new Date(appointmentAt);
          const end = new Date(start.getTime() + 30 * 60 * 1000);
          await createAppointment(authedFetch, {
            patient_id: saved.id,
            doctor_id: assignedDoctorId || null,
            appointment_type: appointmentType.trim() || "Consultation",
            start_time: start.toISOString(),
            end_time: end.toISOString(),
            notes: "Booked at front desk (walk-in intake)"
          });
          results.push({ label: "Appointment booked", ok: true });
        } catch (err: unknown) {
          results.push({ label: "Appointment", ok: false, detail: err instanceof Error ? err.message : undefined });
        }
      }

      if (wantSurgery && assignedDoctorId && surgeryAt) {
        try {
          await createSurgery(authedFetch, {
            patient_id: saved.id,
            doctor_id: assignedDoctorId,
            procedure_id: surgeryProcedureId || null,
            scheduled_date: new Date(surgeryAt).toISOString()
          });
          results.push({ label: "Surgery scheduled", ok: true });
        } catch (err: unknown) {
          results.push({ label: "Surgery", ok: false, detail: err instanceof Error ? err.message : undefined });
        }
      }

      if (wantConsent && consentType) {
        try {
          await createConsentDocument(authedFetch, saved.id, { document_type: consentType });
          results.push({ label: "Consent document raised", ok: true });
        } catch (err: unknown) {
          results.push({ label: "Consent document", ok: false, detail: err instanceof Error ? err.message : undefined });
        }
      }

      if (wantInvoice && invoiceAmount && invoiceDescription.trim()) {
        try {
          await createInvoice(authedFetch, {
            patient_id: saved.id,
            line_items: [{ description: invoiceDescription.trim(), quantity: 1, unit_price: Number(invoiceAmount) }]
          });
          results.push({ label: "Invoice created", ok: true });
        } catch (err: unknown) {
          results.push({ label: "Invoice", ok: false, detail: err instanceof Error ? err.message : undefined });
        }
      }
    }
    setOutcomes(results);

    if (sendPortalAccess && authedFetch && (phone.trim() || email.trim())) {
      try {
        const result = await enablePatientPortal(authedFetch, saved.id);
        setPortalNote(
          result.invite_sent
            ? `Portal ID ${result.portal_id} generated and sent to the patient.`
            : `Portal ID ${result.portal_id} generated, but the invite couldn't be delivered — check their phone/email later.`
        );
      } catch {
        setPortalNote("Patient saved, but portal access couldn't be set up — you can enable it from their profile.");
      }
    }

    setSaving(false);
    setStep("done");
  }

  const previewAgent = preview ? AGENTS_BY_SLUG[preview.agentSlug] : null;
  const activeDoctors = doctors.filter((d) => d.isActive);

  return (
    <>
      <Link
        to={DASHBOARD_ROUTES.patients}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to patients
      </Link>

      {step === "search" &&
      <>
          <PageHeader
          title="Add a patient"
          subtitle="Search by phone first — a patient calling or walking in again should land on their existing profile, not a duplicate." />

          <form onSubmit={handleSearch} className="max-w-lg space-y-4">
            <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <SearchIcon className="h-3.5 w-3.5" /> Patient&apos;s phone number
                </span>
                <input
                  autoFocus
                  value={searchPhone}
                  onChange={(e) => { setSearchPhone(e.target.value); setSearchedOnce(false); }}
                  placeholder="+1 (555) 000-0000"
                  className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
              </label>

              <button
                type="submit"
                disabled={normalizePhone(searchPhone).length < 6}
                className="mt-4 flex items-center gap-1.5 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
                <SearchIcon className="h-4 w-4" /> Search
              </button>
            </div>

            {searchedOnce && foundPatient &&
            <div className="rounded-3xl border border-success/25 bg-success/[0.04] p-6">
                <div className="flex items-center gap-2 text-success">
                  <CheckCircle2Icon className="h-4 w-4" />
                  <p className="text-sm font-bold">Existing patient found</p>
                </div>
                <p className="mt-2 text-sm text-ink-soft">
                  <span className="font-semibold text-ink">{foundPatient.name}</span> already has a record — no need to create a new one.
                </p>
                <Link
                to={DASHBOARD_ROUTES.patientDetail(foundPatient.id)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
                  Open their profile
                </Link>
              </div>
            }

            {searchedOnce && !foundPatient &&
            <div className="rounded-3xl border border-sand-200 bg-white p-6">
                <p className="text-sm text-ink-soft">No existing patient with this number.</p>
                <button
                type="button"
                onClick={proceedToCreate}
                className="mt-4 flex items-center gap-1.5 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
                  Continue — add new patient
                </button>
              </div>
            }
          </form>
        </>
      }

      {step === "create" &&
      <>
          <PageHeader
        title="Add a patient"
        subtitle="Full walk-in intake — everything a receptionist gathers when someone arrives in person, not through the AI." />


      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="mb-4 text-sm font-bold text-ink">Contact details</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <UserIcon className="h-3.5 w-3.5" /> Full name <span className="text-danger">*</span>
              </span>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Smith"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Father&apos;s name</span>
              <input
                value={fatherName}
                onChange={(e) => setFatherName(e.target.value)}
                placeholder="Optional"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@example.com — optional"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Phone number</span>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+1 (555) 000-0000"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Date of birth</span>
              <input
                type="date"
                value={dateOfBirth}
                onChange={(e) => setDateOfBirth(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Gender</span>
              <select
                value={gender}
                onChange={(e) => { setGender(e.target.value); if (e.target.value !== "female") setPregnancyStatus(""); }}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">
                <option value="">Not specified</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </label>
            {gender === "female" &&
            <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Pregnancy / nursing status</span>
                <select
                value={pregnancyStatus}
                onChange={(e) => setPregnancyStatus(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">
                  <option value="">Not asked / not specified</option>
                  <option value="pregnant">Pregnant</option>
                  <option value="nursing">Nursing</option>
                  <option value="not_pregnant_or_nursing">Not pregnant or nursing</option>
                  <option value="declined_to_answer">Declined to answer</option>
                </select>
              </label>
            }
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Assigned doctor</span>
              <select
                value={assignedDoctorId}
                onChange={(e) => setAssignedDoctorId(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">
                <option value="">Not assigned yet</option>
                {activeDoctors.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </label>
          </div>

          {phone.trim() &&
          <label className="mt-4 flex items-center gap-2.5 rounded-xl bg-teal-600/[0.05] px-4 py-3">
              <input
                type="checkbox"
                checked={hasWhatsapp}
                onChange={(e) => setHasWhatsapp(e.target.checked)}
                className="h-4 w-4 rounded border-sand-200 text-teal-600 focus:ring-teal-600/40" />
              <MessageCircleIcon className="h-4 w-4 text-teal-600" />
              <span className="text-sm text-ink-soft">This phone number has WhatsApp — send confirmations/documents there</span>
            </label>
          }

          <button
            type="button"
            onClick={() => setShowMoreDetails((v) => !v)}
            className="mt-4 text-xs font-semibold text-teal-600 hover:underline">
            {showMoreDetails ? "Hide" : "Add"} occupation &amp; emergency contact
          </button>

          {showMoreDetails &&
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Occupation</span>
                <input
                value={occupation}
                onChange={(e) => setOccupation(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Emergency contact name</span>
                <input
                value={emergencyContactName}
                onChange={(e) => setEmergencyContactName(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Emergency contact phone</span>
                <input
                value={emergencyContactPhone}
                onChange={(e) => setEmergencyContactPhone(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Relationship</span>
                <input
                value={emergencyContactRelationship}
                onChange={(e) => setEmergencyContactRelationship(e.target.value)}
                placeholder="e.g. Spouse, Parent"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
              </label>
            </div>
          }
        </div>

        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="mb-1 text-sm font-bold text-ink">What do they need?</p>
          <p className="mb-4 text-xs text-ink-muted">
            Describe it the way the patient would — this is what the AI reads to pick the right agent.
          </p>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Chief complaint / request <span className="text-danger">*</span>
            </span>
            <textarea
              value={chiefComplaint}
              onChange={(e) => setChiefComplaint(e.target.value)}
              rows={3}
              placeholder="e.g. Interested in rhinoplasty, wants to discuss options and pricing before booking"
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

          </label>

          <label className="mt-4 flex items-center gap-2.5 rounded-xl bg-sand-100 px-4 py-3">
            <input
              type="checkbox"
              checked={needsSurgery}
              onChange={(e) => setNeedsSurgery(e.target.checked)}
              className="h-4 w-4 rounded border-sand-200 text-teal-600 focus:ring-teal-600/40" />

            <ScissorsIcon className="h-4 w-4 text-ink-muted" />
            <span className="text-sm text-ink-soft">This patient needs (or is considering) surgery</span>
          </label>

          {preview && previewAgent &&
          <div className="mt-4 flex items-start gap-3 rounded-xl border border-teal-600/20 bg-teal-600/[0.04] px-4 py-3.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-600/10 text-teal-600">
                <SparklesIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">
                  AI will assign to <span className="text-teal-600">{previewAgent.name}</span>
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">{preview.reasoning}</p>
              </div>
            </div>
          }
        </div>

        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
          <p className="mb-1 text-sm font-bold text-ink">Create the right records now</p>
          <p className="mb-4 text-xs text-ink-muted">
            Toggle off anything this visit doesn't need — e.g. skip Surgery if they only came in for a consultation.
          </p>

          <div className="space-y-3">
            <ToggleSection
              icon={CalendarPlusIcon}
              label="Book an appointment"
              checked={wantAppointment}
              onToggle={() => setWantAppointment((v) => !v)}>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Type</span>
                  <input value={appointmentType} onChange={(e) => setAppointmentType(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40" />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Date &amp; time</span>
                  <input type="datetime-local" value={appointmentAt} onChange={(e) => setAppointmentAt(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40" />
                </label>
              </div>
            </ToggleSection>

            <ToggleSection
              icon={ScissorsIcon}
              label="Schedule a surgery"
              checked={wantSurgery}
              onToggle={() => setWantSurgery((v) => !v)}>
              {!assignedDoctorId &&
              <p className="mb-2 flex items-center gap-1.5 text-[11px] text-amber-700"><AlertCircleIcon className="h-3.5 w-3.5" /> Pick an assigned doctor above first — a surgery needs one.</p>
              }
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Procedure</span>
                  <select value={surgeryProcedureId} onChange={(e) => setSurgeryProcedureId(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40">
                    <option value="">Not specified</option>
                    {procedures.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Scheduled date &amp; time</span>
                  <input type="datetime-local" value={surgeryAt} onChange={(e) => setSurgeryAt(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40" />
                </label>
              </div>
            </ToggleSection>

            <ToggleSection
              icon={ShieldCheckIcon}
              label="Raise a consent form"
              checked={wantConsent}
              onToggle={() => setWantConsent((v) => !v)}>
              <label className="block">
                <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Consent type</span>
                <select value={consentType} onChange={(e) => setConsentType(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40">
                  {CONSENT_DOCUMENT_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                </select>
              </label>
            </ToggleSection>

            <ToggleSection
              icon={ReceiptIcon}
              label="Add an invoice"
              checked={wantInvoice}
              onToggle={() => setWantInvoice((v) => !v)}>
              <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Description</span>
                  <input value={invoiceDescription} onChange={(e) => setInvoiceDescription(e.target.value)} placeholder="e.g. Consultation fee" className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40" />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Amount</span>
                  <input type="number" min="0" step="0.01" value={invoiceAmount} onChange={(e) => setInvoiceAmount(e.target.value)} className="w-full rounded-lg border border-sand-200 px-3 py-2 text-sm outline-none focus:border-teal-600/40" />
                </label>
              </div>
            </ToggleSection>
          </div>
        </div>

        {(phone.trim() || email.trim()) &&
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
            <label className="flex items-center gap-2.5">
              <input
              type="checkbox"
              checked={sendPortalAccess}
              onChange={(e) => setSendPortalAccess(e.target.checked)}
              className="h-4 w-4 rounded border-sand-200 text-teal-600 focus:ring-teal-600/40" />
              <KeyIcon className="h-4 w-4 text-teal-600" />
              <span className="text-sm text-ink-soft">Generate a patient portal ID and send it to them now</span>
            </label>
          </div>
        }

        {saveError && <p className="text-sm text-danger">{saveError}</p>}

        <div className="flex justify-end gap-3">
          <Link
            to={DASHBOARD_ROUTES.patients}
            className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

            Cancel
          </Link>
          <button
            type="submit"
            disabled={!canSubmit || saving}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

            {saving ? "Adding…" : "Add patient"}
          </button>
        </div>
      </form>
        </>
      }

      {step === "done" && savedPatientId &&
      <>
          <PageHeader title="Patient added" subtitle="Their record has been created." />
          <div className="max-w-lg rounded-3xl border border-success/25 bg-success/[0.04] p-6">
            <div className="flex items-center gap-2 text-success">
              <CheckCircle2Icon className="h-4 w-4" />
              <p className="text-sm font-bold">{name.trim()} was added</p>
            </div>
            {outcomes.length > 0 &&
          <div className="mt-3 space-y-1.5">
                {outcomes.map((o, i) =>
            <p key={i} className={`flex items-center gap-2 text-sm ${o.ok ? "text-ink-soft" : "text-danger"}`}>
                  {o.ok ? <CheckCircle2Icon className="h-3.5 w-3.5 text-success" /> : <XIcon className="h-3.5 w-3.5" />}
                  {o.label}{!o.ok && o.detail ? ` — ${o.detail}` : !o.ok ? " — couldn't be created, try from their profile" : ""}
                </p>
            )}
              </div>
          }
            {portalNote &&
          <p className="mt-3 flex items-start gap-2 text-sm text-ink-soft">
                <KeyIcon className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" /> {portalNote}
              </p>
          }
            <Link
            to={DASHBOARD_ROUTES.patientDetail(savedPatientId)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
              Open their profile
            </Link>
          </div>
        </>
      }
    </>);

}

function ToggleSection({
  icon: Icon, label, checked, onToggle, children
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  checked: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-2xl border p-3.5 transition-colors ${checked ? "border-teal-600/25 bg-teal-600/[0.03]" : "border-sand-200 bg-sand-50/40"}`}>
      <label className="flex items-center gap-2.5">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="h-4 w-4 rounded border-sand-200 text-teal-600 focus:ring-teal-600/40" />
        <Icon className={`h-4 w-4 ${checked ? "text-teal-600" : "text-ink-muted"}`} />
        <span className="text-sm font-semibold text-ink">{label}</span>
      </label>
      {checked && <div className="mt-3 pl-6">{children}</div>}
    </div>);

}
