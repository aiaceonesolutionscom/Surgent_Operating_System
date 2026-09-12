import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUser } from "@clerk/clerk-react";
import { CameraIcon, FileTextIcon, UploadIcon, XIcon } from "lucide-react";
import { AuthLayout } from "./AuthLayout";
import { useAuthedFetch } from "../../api/authFetch";
import { uploadApplicationFile, submitMyApplication, type DocumentEntry } from "../../api/entities";
import { DOCTOR_APPLY_SESSION_KEY, clearDoctorApplyFlow } from "./DoctorApplyPage";

// Reached right after Clerk sign-up (DoctorApplyPage's forceRedirectUrl) —
// the applicant's User row already exists (inactive) by now, created by the
// user.created webhook's doctor_self_apply branch. This form is what turns
// that bare account into a real, reviewable application.
export function DoctorApplyCompletePage() {
  const { user } = useUser();
  const { authedFetch } = useAuthedFetch();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [bio, setBio] = useState("");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentEntry[]>([]);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [uploadingDocs, setUploadingDocs] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setName(`${user.firstName || ""} ${user.lastName || ""}`.trim());
    }
  }, [user]);

  const email = user?.primaryEmailAddress?.emailAddress || "";
  const canSubmit = Boolean(name.trim() && email) && !submitting && !uploadingPhoto && uploadingDocs === 0;

  async function handlePhotoPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingPhoto(true);
    try {
      const result = await uploadApplicationFile(authedFetch, file);
      setPhotoUrl(result.url);
    } catch (err) {
      const message = err instanceof Error && err.message ? err.message : "Couldn't upload photo — you can still submit without one.";
      setError(`Photo upload failed: ${message}`);
    } finally {
      setUploadingPhoto(false);
    }
  }

  async function handleDocumentsPick(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    setUploadingDocs((n) => n + files.length);
    for (const file of files) {
      try {
        const result = await uploadApplicationFile(authedFetch, file);
        setDocuments((prev) => [...prev, { name: file.name, url: result.url, uploaded_at: new Date().toISOString() }]);
      } catch (err) {
        const message = err instanceof Error && err.message ? err.message : "try again.";
        setError(`Couldn't upload ${file.name} — ${message}`);
      } finally {
        setUploadingDocs((n) => n - 1);
      }
    }
  }

  function removeDocument(index: number) {
    setDocuments((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitMyApplication(authedFetch, {
        name: name.trim(),
        email,
        phone: phone || null,
        specialty: specialty || null,
        license_number: licenseNumber || null,
        bio: bio || null,
        photo_url: photoUrl,
        documents
      });
      // Done with the risky post-signup-redirect window this key exists to
      // patch over (see DoctorApplyRecovery.tsx) — clearing it here means a
      // later, legitimately-approved doctor navigating their real dashboard
      // never gets yanked back here by a stale marker still sitting in
      // sessionStorage from this same tab. The was-signed-in decision is
      // reset too so the next visit to the apply page re-classifies fresh.
      try {
        sessionStorage.removeItem(DOCTOR_APPLY_SESSION_KEY);
      } catch {
        // private browsing / storage disabled — nothing to clear
      }
      clearDoctorApplyFlow();
      navigate("/doctor/apply/pending");
    } catch (err) {
      setError(err instanceof Error && err.message ? `Couldn't submit — ${err.message}` : "Couldn't submit — try again.");
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout variant="doctor">
      <div className="w-full max-w-lg">
        <h1 className="mb-1 font-display text-2xl font-600 text-ink">Tell us about yourself</h1>
        <p className="mb-6 text-sm text-ink-muted">
          This goes to the practice owner for review — the more complete, the faster they can decide.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex items-center gap-4">
            <label className="group relative flex h-16 w-16 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-full border border-sand-200 bg-teal-600/8 text-xl font-bold text-teal-600">
              {photoUrl ?
              <img src={photoUrl} alt="" className="h-full w-full object-cover" /> :

              name.trim()[0]?.toUpperCase() || <CameraIcon className="h-5 w-5" />
              }
              <input type="file" accept="image/*" onChange={handlePhotoPick} className="hidden" />
            </label>
            <div className="flex-1">
              <TextField label="Full name" required value={name} onChange={setName} placeholder="Dr. Jane Smith" />
            </div>
          </div>

          <TextField label="Email" value={email} onChange={() => undefined} disabled />
          <TextField label="Phone" value={phone} onChange={setPhone} placeholder="+1 (555) 000-0000" />
          <TextField label="Specialty" value={specialty} onChange={setSpecialty} placeholder="Rhinoplasty & Facial Aesthetics" />
          <TextField label="License number" value={licenseNumber} onChange={setLicenseNumber} placeholder="MD-00000-CA" />

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Bio</span>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              rows={3}
              placeholder="Board-certified surgeon focused on…"
              className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

          </label>

          <div>
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
              Documents (license, certification, CV)
            </span>
            {documents.length > 0 &&
            <div className="mb-2 space-y-2">
                {documents.map((doc, i) =>
              <div key={i} className="flex items-center gap-3 rounded-xl bg-sand-100 px-4 py-2.5">
                    <FileTextIcon className="h-4 w-4 shrink-0 text-teal-600" />
                    <span className="flex-1 truncate text-sm font-medium text-ink-soft">{doc.name}</span>
                    <button type="button" onClick={() => removeDocument(i)} className="text-ink-muted hover:text-danger">
                      <XIcon className="h-4 w-4" />
                    </button>
                  </div>
              )}
              </div>
            }
            <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-sand-200 px-4 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
              <UploadIcon className="h-4 w-4" /> {uploadingDocs > 0 ? `Uploading ${uploadingDocs}…` : "Upload document(s)"}
              <input type="file" multiple onChange={handleDocumentsPick} className="hidden" />
            </label>
          </div>

          {error && <p className="text-sm font-medium text-danger">{error}</p>}

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:cursor-not-allowed disabled:opacity-40">

            {submitting ? "Submitting…" : "Submit for review"}
          </button>
        </form>
      </div>
    </AuthLayout>);

}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  required,
  disabled



}: {label: string;value: string;onChange: (v: string) => void;placeholder?: string;required?: boolean;disabled?: boolean;}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {label}{required && <span className="text-danger"> *</span>}
      </span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        disabled={disabled}
        className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white disabled:opacity-60" />

    </label>);

}
