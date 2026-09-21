import React, { useEffect, useState } from "react";
import { FileTextIcon, PlusIcon, PencilIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import {
  listConsentTemplates,
  createConsentTemplate,
  updateConsentTemplate,
  CONSENT_DOCUMENT_TYPES,
  type ConsentTemplateResponse
} from "../../../api/entities";
import { ConsentSectionsBuilder, type ConsentSections } from "./ConsentSectionsBuilder";

function label(type: string) {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ConsentTemplatesPage() {
  const { authedFetch } = usePlan();
  const [templates, setTemplates] = useState<ConsentTemplateResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  async function load() {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await listConsentTemplates(authedFetch);
      setTemplates(data);
    } catch {
      setTemplates([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  const usedTypes = new Set(templates.filter((t) => t.is_active).map((t) => t.document_type));
  const availableTypes = CONSENT_DOCUMENT_TYPES.filter((t) => !usedTypes.has(t));

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader
          title="Consent templates"
          subtitle="The reusable wording behind each consent type. Editing bumps a version — patients who already signed keep exactly what they agreed to." />
        {availableTypes.length > 0 &&
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            <PlusIcon className="h-4 w-4" /> New template
          </button>
        }
      </div>

      {adding &&
      <AddForm
        availableTypes={availableTypes}
        onCreate={async (documentType, body, sections) => {
          if (!authedFetch) return;
          await createConsentTemplate(authedFetch, { document_type: documentType, body, sections });
          setAdding(false);
          await load();
        }}
        onCancel={() => setAdding(false)} />
      }

      {loading ?
      <p className="mt-6 text-sm text-ink-muted">Loading…</p> :
      templates.length === 0 ?
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={FileTextIcon} title="No templates yet" body="Create a template for each consent type your practice uses — procedure, anesthesia, photo, marketing, and so on." />
        </div> :

      <div className="mt-6 space-y-3">
          {templates.map((t) =>
        <div key={t.id} className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
              <div className="flex items-center justify-between gap-3 border-b border-sand-100 px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <p className="text-sm font-bold text-ink">{label(t.document_type)}</p>
                  <span className="rounded-full bg-sand-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">v{t.version}</span>
                  {!t.is_active &&
              <span className="rounded-full bg-ink-muted/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">Inactive</span>
              }
                </div>
                <button
              type="button"
              onClick={() => setEditingId(editingId === t.id ? null : t.id)}
              className="flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">
                  <PencilIcon className="h-3.5 w-3.5" /> {editingId === t.id ? "Close" : "Edit"}
                </button>
              </div>

              {editingId === t.id ?
          <EditForm
            template={t}
            onSave={async (body, isActive, sections) => {
              if (!authedFetch) return;
              await updateConsentTemplate(authedFetch, t.id, { body, is_active: isActive, sections });
              setEditingId(null);
              await load();
            }} /> :

          <>
              <p className="whitespace-pre-wrap px-5 py-4 text-sm leading-relaxed text-ink-soft">{t.body}</p>
              {t.sections &&
          <p className="border-t border-sand-100 px-5 py-2 text-[11px] font-medium text-teal-600">
                  Structured sections configured — used for the generated consent PDF instead of plain wording.
                </p>
          }
            </>
          }
            </div>
        )}
        </div>
      }
    </>);

}

function AddForm({
  availableTypes,
  onCreate,
  onCancel
}: {
  availableTypes: readonly string[];
  onCreate: (documentType: string, body: string, sections?: object) => Promise<void>;
  onCancel: () => void;
}) {
  const [documentType, setDocumentType] = useState(availableTypes[0] || "");
  const [body, setBody] = useState("");
  const [sections, setSections] = useState<ConsentSections | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!documentType || !body.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onCreate(documentType, body.trim(), sections ?? undefined);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block sm:col-span-1">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Consent type</span>
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white">
            {availableTypes.map((t) => <option key={t} value={t}>{label(t)}</option>)}
          </select>
        </label>
        <label className="block sm:col-span-2">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Wording</span>
          <textarea
            required
            rows={4}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="I consent to..."
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
      </div>
      <div className="mt-4">
        <ConsentSectionsBuilder value={sections} onChange={setSections} />
      </div>
      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
      <div className="mt-5 flex items-center justify-end gap-3">
        <button type="button" onClick={onCancel} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !body.trim()}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Create template"}
        </button>
      </div>
    </form>);

}

function EditForm({ template, onSave }: { template: ConsentTemplateResponse; onSave: (body: string, isActive: boolean, sections: object | null) => Promise<void> }) {
  const [body, setBody] = useState(template.body);
  const [sections, setSections] = useState<ConsentSections | null>((template.sections as ConsentSections | null) ?? null);
  const [isActive, setIsActive] = useState(template.is_active);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(body.trim(), isActive, sections);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  const bodyChanged = body.trim() !== template.body;

  return (
    <form onSubmit={handleSubmit} className="border-t border-sand-100 px-5 py-4">
      <textarea
        rows={4}
        value={body}
        onChange={(e) => setBody(e.target.value)}
        className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
      <div className="mt-3">
        <ConsentSectionsBuilder value={sections} onChange={setSections} />
      </div>
      {bodyChanged &&
      <p className="mt-2 text-xs font-medium text-warning">
          Saving this will bump the version to v{template.version + 1} — already-signed documents keep their original wording.
        </p>
      }
      <label className="mt-3 flex items-center gap-2 text-sm text-ink-soft">
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="h-4 w-4 rounded border-sand-300 text-teal-600 focus:ring-teal-600" />
        Active (offered when raising a new consent document)
      </label>
      {error && <p className="mt-2 text-sm font-medium text-danger">{error}</p>}
      <div className="mt-4 flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="rounded-xl bg-teal-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </form>);

}
