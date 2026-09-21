import React, { useEffect, useState } from "react";
import { ShieldCheckIcon, PlusIcon, PenLineIcon, XIcon, CheckIcon, MessageSquareIcon, FileDownIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import { useConsentDocuments } from "./useConsentDocuments";
import { listConsentTemplates, type ConsentDocumentResponse, type ConsentTemplateResponse } from "../../../api/entities";

const STATUS_CLASS: Record<string, string> = {
  draft: "bg-sand-100 text-ink-soft",
  sent: "bg-warning/10 text-warning",
  signed: "bg-success/10 text-success",
  void: "bg-danger/10 text-danger"
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Owner/Receptionist manage the workflow (create/send/sign/void); Doctor
// gets read access plus one lightweight action — "mark discussed" — rather
// than administrative control over the consent process (matches
// consent_router.py's role split).
export function ConsentDocumentsList({ patientId }: { patientId: string }) {
  const { authedFetch, role } = usePlan();
  const { documents, loading, create, sign, voidDoc, markDiscussed } = useConsentDocuments(authedFetch, patientId);
  const [adding, setAdding] = useState(false);
  const canManage = role === "owner" || role === "receptionist";
  const isDoctor = role === "doctor";

  return (
    <div className="mb-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
        <p className="flex items-center gap-2 text-sm font-bold text-ink">
          <ShieldCheckIcon className="h-4 w-4 text-teal-600" /> Consent documents
        </p>
        {canManage &&
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

          <PlusIcon className="h-3.5 w-3.5" /> New document
        </button>
        }
      </div>

      {adding && <NewDocumentForm onCreate={create} onDone={() => setAdding(false)} />}

      <div className="p-2">
        {loading ?
        <p className="px-3 py-4 text-sm text-ink-muted">Loading…</p> :
        documents.length === 0 ?
        <p className="px-3 py-4 text-sm text-ink-muted">No consent documents yet.</p> :

        <div className="divide-y divide-sand-100">
            {documents.map((doc) => (
              <DocumentRow key={doc.id} document={doc} canManage={canManage} isDoctor={isDoctor} onSign={sign} onVoid={voidDoc} onMarkDiscussed={markDiscussed} />
            ))}
          </div>
        }
      </div>
    </div>);

}

function NewDocumentForm({
  onCreate,
  onDone
}: {
  onCreate: (data: { document_type: string; content?: string | null; template_id?: string | null }) => Promise<unknown>;
  onDone: () => void;
}) {
  const { authedFetch } = usePlan();
  const [templates, setTemplates] = useState<ConsentTemplateResponse[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!authedFetch) return;
    listConsentTemplates(authedFetch).then((data) => setTemplates(data.filter((t) => t.is_active))).catch(() => setTemplates([]));
  }, [authedFetch]);

  function pickTemplate(id: string) {
    setTemplateId(id);
    const template = templates.find((t) => t.id === id);
    if (template) {
      setDocumentType(template.document_type.replace(/_/g, " "));
      setContent(template.body);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!documentType.trim()) return;
    setSaving(true);
    await onCreate({
      document_type: documentType.trim(),
      content: templateId ? undefined : content.trim() || null,
      template_id: templateId || null
    });
    setSaving(false);
    onDone();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border-b border-sand-200 bg-sand-50/50 px-5 py-4">
      {templates.length > 0 &&
      <label className="block">
          <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Use a template (optional)</span>
          <select
          value={templateId}
          onChange={(e) => pickTemplate(e.target.value)}
          className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40">
            <option value="">None — write it manually</option>
            {templates.map((t) => <option key={t.id} value={t.id}>{t.document_type.replace(/_/g, " ")} (v{t.version})</option>)}
          </select>
        </label>
      }

      <input
        required
        value={documentType}
        onChange={(e) => setDocumentType(e.target.value)}
        placeholder="Document type, e.g. Surgical Consent"
        disabled={!!templateId}
        className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 disabled:bg-sand-100 disabled:text-ink-muted" />

      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={3}
        placeholder="The consent text the patient will read and sign, optional to fill in now"
        disabled={!!templateId}
        className="w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 disabled:bg-sand-100 disabled:text-ink-muted" />
      {templateId && <p className="text-[11px] text-ink-muted">Wording locked to the template — this exact text is what gets signed.</p>}

      <div className="flex justify-end gap-2">
        <button type="button" onClick={onDone} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink">Cancel</button>
        <button type="submit" disabled={saving || !documentType.trim()} className="rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:opacity-50">
          {saving ? "Creating…" : "Create"}
        </button>
      </div>
    </form>);

}

function DocumentRow({
  document,
  canManage,
  isDoctor,
  onSign,
  onVoid,
  onMarkDiscussed




}: {
  document: ConsentDocumentResponse;
  canManage: boolean;
  isDoctor: boolean;
  onSign: (id: string, name: string) => Promise<unknown>;
  onVoid: (id: string) => Promise<unknown>;
  onMarkDiscussed: (id: string) => Promise<unknown>;
}) {
  const [signing, setSigning] = useState(false);
  const [name, setName] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [markingDiscussed, setMarkingDiscussed] = useState(false);

  async function handleSign() {
    if (!name.trim() || !confirmed) return;
    setSaving(true);
    try {
      await onSign(document.id, name.trim());
      setSigning(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleMarkDiscussed() {
    setMarkingDiscussed(true);
    try {
      await onMarkDiscussed(document.id);
    } finally {
      setMarkingDiscussed(false);
    }
  }

  return (
    <div className="px-5 py-3.5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{document.document_type}</p>
          <p className="text-xs text-ink-muted">
            {document.status === "signed" && document.signed_by_name && document.signed_at ?
            `Signed by ${document.signed_by_name} on ${formatDate(document.signed_at)}` :
            `Created ${formatDate(document.created_at)}`}
          </p>
          {document.discussed_at &&
          <p className="mt-0.5 flex items-center gap-1 text-[11px] text-teal-600">
              <MessageSquareIcon className="h-3 w-3" /> Discussed with patient on {formatDate(document.discussed_at)}
            </p>
          }
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {document.file_url &&
          <a
            href={document.file_url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 rounded-lg border border-sand-200 px-2.5 py-1 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600">

              <FileDownIcon className="h-3 w-3" /> PDF
            </a>
          }
          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[document.status]}`}>{document.status}</span>
          {canManage && (document.status === "draft" || document.status === "sent") && !signing &&
          <>
              <button type="button" onClick={() => setSigning(true)} className="flex items-center gap-1 rounded-lg border border-sand-200 px-2.5 py-1 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600">
                <PenLineIcon className="h-3 w-3" /> Sign
              </button>
              <button type="button" onClick={() => onVoid(document.id)} className="rounded-lg px-2 py-1 text-[11px] font-semibold text-ink-muted hover:text-danger">
                Void
              </button>
            </>
          }
          {isDoctor && !document.discussed_at &&
          <button
            type="button"
            onClick={handleMarkDiscussed}
            disabled={markingDiscussed}
            className="flex items-center gap-1 rounded-lg border border-sand-200 px-2.5 py-1 text-xs font-semibold text-ink-soft hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-50">
              <MessageSquareIcon className="h-3 w-3" /> {markingDiscussed ? "…" : "Mark discussed"}
            </button>
          }
        </div>
      </div>

      {signing &&
      <div className="mt-3 rounded-xl border border-teal-600/20 bg-teal-600/[0.03] p-4">
          <p className="mb-2 text-xs text-ink-muted">
            Patient should be present. Have them type their full legal name below to record their signature.
          </p>
          <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Patient's full legal name"
          className="mb-2 w-full rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40" />

          <label className="mb-3 flex items-center gap-2 text-xs text-ink-soft">
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="h-3.5 w-3.5 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
            Patient confirms they have read and agree to this document.
          </label>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => { setSigning(false); setName(""); setConfirmed(false); }} className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold text-ink-muted hover:text-ink">
              <XIcon className="h-3.5 w-3.5" /> Cancel
            </button>
            <button
            type="button"
            onClick={handleSign}
            disabled={saving || !name.trim() || !confirmed}
            className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

              <CheckIcon className="h-3.5 w-3.5" /> {saving ? "Recording…" : "Record signature"}
            </button>
          </div>
        </div>
      }
    </div>);

}
