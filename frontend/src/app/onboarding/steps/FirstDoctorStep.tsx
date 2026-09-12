import React, { useState } from "react";
import { UserIcon, Loader2Icon } from "lucide-react";
import { useDoctors } from "../../dashboard/doctors/useDoctors";
import type { Doctor } from "../../dashboard/doctors/types";

interface StepProps {
  onNext: () => void;
  onSkip: () => void;
}

// A field subset of dashboard/doctors/DoctorFormPage.tsx — just enough to
// seed the first record. Photo/capabilities/availability/documents stay
// editable from the real Doctors page later.
export function FirstDoctorStep({ onNext, onSkip }: StepProps) {
  const { addDoctor } = useDoctors();
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleContinue() {
    setSaving(true);
    const doctor: Doctor = {
      id: `d${Date.now()}`,
      name: name.trim(),
      initial: name.trim()[0]?.toUpperCase() || "?",
      userId: null,
      email: "",
      phone: "",
      specialty: specialty.trim(),
      capabilities: [],
      licenseNumber: "",
      yearsExperience: 0,
      bio: "",
      availability: [],
      documents: [],
      isActive: true,
      activePatients: 0,
      upcomingSurgeries: 0
    };
    await addDoctor(doctor);
    setSaving(false);
    onNext();
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <p className="text-lg font-bold text-ink">Add your first doctor</p>
      <p className="mt-1 text-sm text-ink-muted">You can add photo, capabilities, and availability later from Doctors.</p>

      <label className="mt-6 block">
        <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          <UserIcon className="h-3.5 w-3.5" /> Full name
        </span>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Dr. Jane Smith"
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

      </label>

      <label className="mt-4 block">
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Specialty</span>
        <input
          value={specialty}
          onChange={(e) => setSpecialty(e.target.value)}
          placeholder="Rhinoplasty & Facial Aesthetics"
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

      </label>

      <div className="mt-6 flex gap-3">
        <button
          onClick={onSkip}
          className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

          Skip
        </button>
        <button
          onClick={handleContinue}
          disabled={!name.trim() || !specialty.trim() || saving}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

          {saving && <Loader2Icon className="h-4 w-4 animate-spin" />}
          Continue
        </button>
      </div>
    </div>);

}
