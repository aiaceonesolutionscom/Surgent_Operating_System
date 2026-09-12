import React, { useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeftIcon, SparklesIcon, MicIcon, SquareIcon, LoaderIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { usePatients } from "../patients/usePatients";
import { useConsultationNotes } from "./useConsultationNotes";
import { transcribeDictation } from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

// SOAP — Subjective/Objective/Assessment/Plan — the near-universal clinical
// documentation structure real EHR/EMR systems use, rather than one
// free-text box.
export function ConsultationNoteFormPage() {
  const { patientId } = useParams<{ patientId: string }>();
  const [searchParams] = useSearchParams();
  const appointmentId = searchParams.get("appointmentId");
  const navigate = useNavigate();
  const { authedFetch } = usePlan();
  const { getPatient, loading: patientLoading } = usePatients(authedFetch);
  const { create, aiDraft } = useConsultationNotes(authedFetch, patientId);

  const patient = patientId ? getPatient(patientId) : undefined;

  const [chiefComplaint, setChiefComplaint] = useState(patient?.chiefComplaint || "");
  const [subjective, setSubjective] = useState("");
  const [objective, setObjective] = useState("");
  const [assessment, setAssessment] = useState("");
  const [plan, setPlan] = useState("");
  const [saving, setSaving] = useState<"draft" | "final" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [rawNotes, setRawNotes] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [followUpTasks, setFollowUpTasks] = useState<string[]>([]);

  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [recordError, setRecordError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function startRecording() {
    setRecordError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        if (blob.size === 0) return;
        setTranscribing(true);
        try {
          if (!authedFetch) throw new Error("not signed in");
          const result = await transcribeDictation(authedFetch, blob, "dictation.webm");
          setRawNotes((prev) => (prev.trim() ? `${prev.trim()} ${result.text}` : result.text));
        } catch (err: unknown) {
          setRecordError(
            err instanceof Error && err.message
              ? err.message
              : "Couldn't transcribe that recording — try again, or type your notes instead."
          );
        } finally {
          setTranscribing(false);
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setRecording(true);
    } catch {
      setRecordError("Couldn't access your microphone — check browser permissions.");
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    mediaRecorderRef.current = null;
    setRecording(false);
  }

  async function handleAiDraft() {
    if (!patientId || !rawNotes.trim()) return;
    setDrafting(true);
    setDraftError(null);
    try {
      const draft = await aiDraft(patientId, rawNotes.trim());
      if (!draft) throw new Error("no draft");
      setSubjective(draft.subjective);
      setObjective(draft.objective);
      setAssessment(draft.assessment);
      setPlan(draft.plan);
      setFollowUpTasks(draft.follow_up_tasks);
    } catch (err) {
      setDraftError(
        err instanceof Error && err.message ?
        err.message :
        "Couldn't generate a draft — try again, or fill the fields in manually."
      );
    } finally {
      setDrafting(false);
    }
  }

  React.useEffect(() => {
    if (patient?.chiefComplaint) setChiefComplaint((prev) => prev || patient.chiefComplaint);
  }, [patient?.chiefComplaint]);

  async function handleSave(status: "draft" | "final") {
    if (!patientId) return;
    setSaving(status);
    setError(null);
    try {
      const note = await create({
        patient_id: patientId,
        appointment_id: appointmentId || undefined,
        chief_complaint: chiefComplaint || null,
        subjective: subjective || null,
        objective: objective || null,
        assessment: assessment || null,
        plan: plan || null,
        status
      });
      if (!note) throw new Error("no note");
      navigate(DASHBOARD_ROUTES.patientDetail(patientId));
    } catch (err: unknown) {
      setError(
        err instanceof Error && err.message ? err.message : "Couldn't save this note — try again."
      );
      setSaving(null);
    }
  }

  if (patientLoading) return null;

  return (
    <>
      <Link
        to={patientId ? DASHBOARD_ROUTES.patientDetail(patientId) : DASHBOARD_ROUTES.patients}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to patient
      </Link>

      <PageHeader
        title={patient ? `Consultation note — ${patient.name}` : "Consultation note"}
        subtitle="Structured SOAP note: what the patient reports, what you observe, your assessment, and the plan." />


      <div className="mt-6 max-w-2xl space-y-4">
        <div className="rounded-xl border border-teal-600/20 bg-teal-600/[0.04] p-4">
          <div className="flex items-center gap-1.5">
            <SparklesIcon className="h-4 w-4 text-teal-600" />
            <span className="text-xs font-semibold uppercase tracking-wide text-teal-600">Consultation Assistant</span>
          </div>
          <p className="mt-1 text-xs text-ink-muted">Paste, type, or dictate your raw notes — AI drafts the SOAP fields below for you to review and edit.</p>
          <textarea
            value={rawNotes}
            onChange={(e) => setRawNotes(e.target.value)}
            rows={3}
            placeholder="e.g. Patient here for rhinoplasty consult, unhappy with dorsal hump since teens, no prior surgeries, exam shows mild deviation..."
            className="mt-2 w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40" />
          {recordError && <p className="mt-1.5 text-xs font-medium text-danger">{recordError}</p>}
          {draftError && <p className="mt-1.5 text-xs font-medium text-danger">{draftError}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={recording ? stopRecording : startRecording}
              disabled={transcribing}
              className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                recording ? "bg-danger text-white hover:bg-danger/90" : "border border-sand-200 text-ink-soft hover:border-teal-600/40 hover:text-teal-600"
              }`}>
              {transcribing ? (
                <><LoaderIcon className="h-3.5 w-3.5 animate-spin" /> Transcribing…</>
              ) : recording ? (
                <><SquareIcon className="h-3.5 w-3.5" /> Stop recording</>
              ) : (
                <><MicIcon className="h-3.5 w-3.5" /> Dictate</>
              )}
            </button>
            <button
              type="button"
              onClick={handleAiDraft}
              disabled={drafting || !rawNotes.trim()}
              className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
              <SparklesIcon className="h-3.5 w-3.5" /> {drafting ? "Drafting…" : "Generate SOAP draft"}
            </button>
          </div>
        </div>

        <Field label="Chief complaint" value={chiefComplaint} onChange={setChiefComplaint} rows={2} placeholder="What brings the patient in today" />
        <Field label="Subjective" value={subjective} onChange={setSubjective} rows={4} placeholder="What the patient reports — symptoms, history, concerns, in their own words." />
        <Field label="Objective" value={objective} onChange={setObjective} rows={4} placeholder="What you observe — exam findings, measurements, photos taken." />
        <Field label="Assessment" value={assessment} onChange={setAssessment} rows={3} placeholder="Your clinical impression / diagnosis." />
        <Field label="Plan" value={plan} onChange={setPlan} rows={3} placeholder="Next steps — treatment plan, follow-up, referrals." />

        {followUpTasks.length > 0 &&
        <div className="rounded-xl border border-sand-200 bg-sand-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">AI-suggested follow-up tasks</p>
            <ul className="mt-2 space-y-1 text-sm text-ink-soft">
              {followUpTasks.map((t, i) => <li key={i}>• {t}</li>)}
            </ul>
          </div>
        }

        {error && <p className="text-sm font-medium text-danger">{error}</p>}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={() => handleSave("draft")}
            disabled={saving !== null}
            className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:cursor-not-allowed disabled:opacity-40">

            {saving === "draft" ? "Saving…" : "Save as draft"}
          </button>
          <button
            type="button"
            onClick={() => handleSave("final")}
            disabled={saving !== null}
            className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

            {saving === "final" ? "Finalizing…" : "Finalize note"}
          </button>
        </div>
        <p className="text-xs text-ink-muted">Finalized notes can&apos;t be edited — a later change creates a new note instead.</p>
      </div>
    </>);

}

function Field({
  label,
  value,
  onChange,
  rows,
  placeholder



}: {label: string;value: string;onChange: (v: string) => void;rows: number;placeholder: string;}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows}
        placeholder={placeholder}
        className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

    </label>);

}
