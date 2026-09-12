import React, { useEffect, useState } from "react";
import { HeartPulseIcon, PencilIcon, PlusIcon, XIcon, PhoneIcon, GlobeIcon, ShieldIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { getPatientById, updatePatient, type PatientResponse, type UpdatePatientRequest } from "../../../api/entities";

type ListField = { key: string; placeholder: string };

const ALLERGY_FIELDS: ListField[] = [
  { key: "name", placeholder: "Allergen" },
  { key: "severity", placeholder: "Severity" },
  { key: "reaction", placeholder: "Reaction" }
];
const SURGICAL_HISTORY_FIELDS: ListField[] = [
  { key: "procedure", placeholder: "Procedure" },
  { key: "year", placeholder: "Year" },
  { key: "facility", placeholder: "Facility" }
];
const MEDICATION_FIELDS: ListField[] = [
  { key: "name", placeholder: "Medication" },
  { key: "dosage", placeholder: "Dosage" },
  { key: "frequency", placeholder: "Frequency" }
];
const COSMETIC_FIELDS: ListField[] = [
  { key: "procedure", placeholder: "Procedure" },
  { key: "year", placeholder: "Year" },
  { key: "provider", placeholder: "Provider" }
];
const PHONE_FIELDS: ListField[] = [
  { key: "number", placeholder: "Phone number" },
  { key: "label", placeholder: "Label (Home, Work…)" }
];

const SMOKING_OPTIONS = ["", "never", "former", "current"];
const COMM_CHANNELS = ["sms", "email", "whatsapp", "call"];

export function PatientMedicalProfile({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const [patient, setPatient] = useState<PatientResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);

  async function load() {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getPatientById(authedFetch, patientId);
      setPatient(data);
    } catch {
      setPatient(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch, patientId]);

  const canEdit = role === "owner" || role === "doctor" || role === "receptionist";

  if (loading || !patient) {
    return (
      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <p className="text-sm text-ink-muted">{loading ? "Loading medical profile…" : "Couldn't load medical profile."}</p>
      </div>);
  }

  if (editing) {
    return <EditProfile patient={patient} onCancel={() => setEditing(false)} onSaved={async () => { setEditing(false); await load(); }} />;
  }

  const hasAnyDepth =
    patient.gender || patient.additional_phones.length > 0 || patient.emergency_contact_name || patient.allergies.length > 0 || patient.surgical_history.length > 0 ||
    patient.current_medications.length > 0 || patient.smoking_status || patient.previous_cosmetic_procedures.length > 0 ||
    patient.referral_source || patient.preferred_language || Object.keys(patient.communication_preferences).length > 0 ||
    patient.insurance_provider;

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-100 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <HeartPulseIcon className="h-4 w-4 text-teal-600" /> Medical profile
        </p>
        {canEdit &&
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
            <PencilIcon className="h-3.5 w-3.5" /> Edit
          </button>
        }
      </div>

      {!hasAnyDepth ?
      <p className="px-5 py-6 text-sm text-ink-muted">No medical profile on file yet — click Edit to add allergies, history, and emergency contact.</p> :

      <div className="grid gap-5 p-5 sm:grid-cols-2">
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Personal &amp; contact</p>
            {patient.gender && <Field label="Gender" value={patient.gender} />}
            {patient.additional_phones.length > 0 &&
          <ListSummary
            label="Other phone numbers"
            items={patient.additional_phones.map((p) => [p.number, p.label].filter(Boolean).join(" — "))} />
          }
            {(patient.emergency_contact_name || patient.emergency_contact_phone) &&
          <Field label="Emergency contact" value={[patient.emergency_contact_name, patient.emergency_contact_phone].filter(Boolean).join(" · ")} icon={PhoneIcon} />
          }
            {patient.preferred_language && <Field label="Preferred language" value={patient.preferred_language} icon={GlobeIcon} />}
            {Object.keys(patient.communication_preferences).length > 0 &&
          <Field
            label="Contact via"
            value={Object.entries(patient.communication_preferences).filter(([, v]) => v).map(([k]) => k).join(", ") || "None selected"} />
          }
            {(patient.insurance_provider || patient.insurance_number) &&
          <Field label="Insurance" value={[patient.insurance_provider, patient.insurance_number].filter(Boolean).join(" · ")} icon={ShieldIcon} />
          }
          </div>

          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Clinical history</p>
            {patient.smoking_status && <Field label="Smoking status" value={patient.smoking_status} />}
            {patient.allergies.length > 0 &&
          <ListSummary label="Allergies" items={patient.allergies.map((a) => [a.name, a.severity, a.reaction].filter(Boolean).join(" — "))} danger />
          }
            {patient.current_medications.length > 0 &&
          <ListSummary label="Current medications" items={patient.current_medications.map((m) => [m.name, m.dosage, m.frequency].filter(Boolean).join(" — "))} />
          }
            {patient.surgical_history.length > 0 &&
          <ListSummary label="Surgical history" items={patient.surgical_history.map((s) => [s.procedure, s.year, s.facility].filter(Boolean).join(" — "))} />
          }
            {patient.previous_cosmetic_procedures.length > 0 &&
          <ListSummary label="Previous cosmetic procedures" items={patient.previous_cosmetic_procedures.map((p) => [p.procedure, p.year, p.provider].filter(Boolean).join(" — "))} />
          }
            {patient.referral_source && <Field label="Referred by" value={patient.referral_source} />}
          </div>
        </div>
      }
    </div>);

}

function Field({ label, value, icon: Icon }: { label: string; value: string; icon?: React.ComponentType<{ className?: string }> }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="mt-0.5 flex items-center gap-1.5 text-sm text-ink">
        {Icon && <Icon className="h-3.5 w-3.5 text-ink-muted" />} {value}
      </p>
    </div>);

}

function ListSummary({ label, items, danger }: { label: string; items: string[]; danger?: boolean }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {items.map((item, i) =>
        <span key={i} className={`rounded-full px-2.5 py-1 text-xs font-medium ${danger ? "bg-danger/10 text-danger" : "bg-sand-100 text-ink-soft"}`}>
            {item}
          </span>
        )}
      </div>
    </div>);

}

function ListFieldEditor({
  label,
  fields,
  items,
  onChange
}: {
  label: string;
  fields: ListField[];
  items: Record<string, string>[];
  onChange: (items: Record<string, string>[]) => void;
}) {
  function addRow() {
    onChange([...items, {}]);
  }
  function updateRow(i: number, key: string, value: string) {
    onChange(items.map((item, idx) => (idx === i ? { ...item, [key]: value } : item)));
  }
  function removeRow(i: number) {
    onChange(items.filter((_, idx) => idx !== i));
  }

  return (
    <div>
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      <div className="space-y-2">
        {items.map((item, i) =>
        <div key={i} className="flex items-center gap-1.5">
            {fields.map((f) =>
          <input
            key={f.key}
            value={item[f.key] || ""}
            onChange={(e) => updateRow(i, f.key, e.target.value)}
            placeholder={f.placeholder}
            className="min-w-0 flex-1 rounded-lg border border-sand-200 bg-canvas px-2.5 py-1.5 text-xs text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          )}
            <button type="button" onClick={() => removeRow(i)} className="shrink-0 text-ink-muted hover:text-danger">
              <XIcon className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>
      <button type="button" onClick={addRow} className="mt-2 flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
        <PlusIcon className="h-3 w-3" /> Add
      </button>
    </div>);

}

function EditProfile({ patient, onCancel, onSaved }: { patient: PatientResponse; onCancel: () => void; onSaved: () => void }) {
  const { authedFetch } = usePlan();
  const [phone, setPhone] = useState(patient.phone || "");
  const [additionalPhones, setAdditionalPhones] = useState<Record<string, string>[]>(patient.additional_phones as Record<string, string>[]);
  const [gender, setGender] = useState(patient.gender || "");
  const [emergencyName, setEmergencyName] = useState(patient.emergency_contact_name || "");
  const [emergencyPhone, setEmergencyPhone] = useState(patient.emergency_contact_phone || "");
  const [preferredLanguage, setPreferredLanguage] = useState(patient.preferred_language || "");
  const [smokingStatus, setSmokingStatus] = useState(patient.smoking_status || "");
  const [referralSource, setReferralSource] = useState(patient.referral_source || "");
  const [insuranceProvider, setInsuranceProvider] = useState(patient.insurance_provider || "");
  const [insuranceNumber, setInsuranceNumber] = useState(patient.insurance_number || "");
  const [commPrefs, setCommPrefs] = useState<Record<string, boolean>>(patient.communication_preferences || {});
  const [allergies, setAllergies] = useState<Record<string, string>[]>(patient.allergies as Record<string, string>[]);
  const [surgicalHistory, setSurgicalHistory] = useState<Record<string, string>[]>(patient.surgical_history as Record<string, string>[]);
  const [medications, setMedications] = useState<Record<string, string>[]>(patient.current_medications as Record<string, string>[]);
  const [cosmeticProcedures, setCosmeticProcedures] = useState<Record<string, string>[]>(patient.previous_cosmetic_procedures as Record<string, string>[]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggleComm(channel: string) {
    setCommPrefs((prev) => ({ ...prev, [channel]: !prev[channel] }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!authedFetch) return;
    setSaving(true);
    setError(null);
    try {
      const data: UpdatePatientRequest = {
        phone: phone.trim() || null,
        additional_phones: additionalPhones.filter((p) => p.number),
        gender: gender || null,
        emergency_contact_name: emergencyName || null,
        emergency_contact_phone: emergencyPhone || null,
        preferred_language: preferredLanguage || null,
        smoking_status: smokingStatus || null,
        referral_source: referralSource || null,
        insurance_provider: insuranceProvider || null,
        insurance_number: insuranceNumber || null,
        communication_preferences: commPrefs,
        allergies: allergies.filter((a) => a.name),
        surgical_history: surgicalHistory.filter((s) => s.procedure),
        current_medications: medications.filter((m) => m.name),
        previous_cosmetic_procedures: cosmeticProcedures.filter((p) => p.procedure)
      };
      await updatePatient(authedFetch, patient.id, data);
      onSaved();
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="border-b border-sand-100 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <HeartPulseIcon className="h-4 w-4 text-teal-600" /> Edit medical profile
        </p>
      </div>

      <div className="grid gap-5 p-5 sm:grid-cols-2">
        <div className="space-y-4">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Primary phone</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 (555) 000-0000" className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <ListFieldEditor label="Other phone numbers" fields={PHONE_FIELDS} items={additionalPhones} onChange={setAdditionalPhones} />
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Gender</span>
              <input value={gender} onChange={(e) => setGender(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Smoking status</span>
              <select value={smokingStatus} onChange={(e) => setSmokingStatus(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
                {SMOKING_OPTIONS.map((o) => <option key={o} value={o}>{o || "Not specified"}</option>)}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Emergency contact name</span>
              <input value={emergencyName} onChange={(e) => setEmergencyName(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Emergency contact phone</span>
              <input value={emergencyPhone} onChange={(e) => setEmergencyPhone(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            </label>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Preferred language</span>
            <input value={preferredLanguage} onChange={(e) => setPreferredLanguage(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
          <div>
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Contact via</span>
            <div className="flex flex-wrap gap-3">
              {COMM_CHANNELS.map((c) =>
              <label key={c} className="flex items-center gap-1.5 text-sm text-ink-soft">
                  <input type="checkbox" checked={!!commPrefs[c]} onChange={() => toggleComm(c)} className="h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
                  {c}
                </label>
              )}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Insurance provider</span>
              <input value={insuranceProvider} onChange={(e) => setInsuranceProvider(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Insurance number</span>
              <input value={insuranceNumber} onChange={(e) => setInsuranceNumber(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
            </label>
          </div>
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Referred by</span>
            <input value={referralSource} onChange={(e) => setReferralSource(e.target.value)} placeholder="Dr. Ahmed, existing patient Sara…" className="w-full rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
          </label>
        </div>

        <div className="space-y-4">
          <ListFieldEditor label="Allergies" fields={ALLERGY_FIELDS} items={allergies} onChange={setAllergies} />
          <ListFieldEditor label="Current medications" fields={MEDICATION_FIELDS} items={medications} onChange={setMedications} />
          <ListFieldEditor label="Surgical history" fields={SURGICAL_HISTORY_FIELDS} items={surgicalHistory} onChange={setSurgicalHistory} />
          <ListFieldEditor label="Previous cosmetic procedures" fields={COSMETIC_FIELDS} items={cosmeticProcedures} onChange={setCosmeticProcedures} />
        </div>
      </div>

      {error && <p className="px-5 pb-2 text-sm font-medium text-danger">{error}</p>}

      <div className="flex items-center justify-end gap-3 border-t border-sand-100 px-5 py-4">
        <button type="button" onClick={onCancel} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Save profile"}
        </button>
      </div>
    </form>);

}
