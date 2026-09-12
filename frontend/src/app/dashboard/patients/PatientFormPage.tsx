import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeftIcon, SparklesIcon, UserIcon, ScissorsIcon, SearchIcon, CheckCircle2Icon, KeyIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePatients } from "./usePatients";
import { classifyPatient } from "./classifyPatient";
import type { Patient } from "./types";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import { enablePatientPortal } from "../../../api/entities";

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

export function PatientFormPage() {
  const { authedFetch } = usePlan();
  const { patients, addPatient } = usePatients(authedFetch);

  const [step, setStep] = useState<"search" | "create" | "done">("search");
  const [savedPatientId, setSavedPatientId] = useState<string | null>(null);
  const [searchPhone, setSearchPhone] = useState("");
  const [searchedOnce, setSearchedOnce] = useState(false);
  const foundPatient = searchedOnce ? findByPhone(patients, searchPhone) : null;

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [gender, setGender] = useState("");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [needsSurgery, setNeedsSurgery] = useState(false);
  const [sendPortalAccess, setSendPortalAccess] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [portalNote, setPortalNote] = useState<string | null>(null);

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
      gender: gender || null
    });
    if (!saved) {
      setSaveError("Couldn't save — this browser's storage is full or unavailable. Please try again.");
      setSaving(false);
      return;
    }

    setSavedPatientId(saved.id);

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
        subtitle="Describe what they need — the right agent gets assigned automatically." />


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
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@example.com"
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

            </label>
            <label className="block sm:col-span-2">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Phone</span>
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
                onChange={(e) => setGender(e.target.value)}
                className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white">
                <option value="">Not specified</option>
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </label>
          </div>

          {(phone.trim() || email.trim()) &&
          <label className="mt-4 flex items-center gap-2.5 rounded-xl bg-teal-600/[0.05] px-4 py-3">
              <input
                type="checkbox"
                checked={sendPortalAccess}
                onChange={(e) => setSendPortalAccess(e.target.checked)}
                className="h-4 w-4 rounded border-sand-200 text-teal-600 focus:ring-teal-600/40" />
              <KeyIcon className="h-4 w-4 text-teal-600" />
              <span className="text-sm text-ink-soft">Generate a patient portal ID and send it to them now</span>
            </label>
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
