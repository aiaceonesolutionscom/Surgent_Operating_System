import { useEffect, useState } from "react";
import { CopyIcon, PencilIcon, CheckIcon, XIcon, RefreshCwIcon } from "lucide-react";
import { usePlan } from "../plan/PlanContext";
import {
  getAIReceptionistSystemPrompt,
  updateAIReceptionistSystemPrompt,
  type SystemPromptResponse
} from "../../../api/entities";

export function SystemPromptCard() {
  const { authedFetch, role } = usePlan();
  const canEdit = role === "owner";
  const [prompt, setPrompt] = useState<SystemPromptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    getAIReceptionistSystemPrompt(authedFetch)
      .then((data) => {
        if (!cancelled) setPrompt(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const startEdit = () => {
    setDraft(prompt?.custom_instructions ?? "");
    setEditing(true);
    setFlash(null);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft("");
    setFlash(null);
  };

  const save = async () => {
    if (!authedFetch) return;
    setSaving(true);
    try {
      const data = await updateAIReceptionistSystemPrompt(authedFetch, draft.trim());
      setPrompt(data);
      setEditing(false);
      setFlash("Saved — next WhatsApp message uses it.");
    } catch {
      setFlash("Couldn't save — try again.");
    } finally {
      setSaving(false);
    }
  };

  const copy = async () => {
    const text = prompt?.system_prompt ?? "";
    try {
      await navigator.clipboard.writeText(text);
      setFlash("Copied to clipboard.");
    } catch {
      setFlash("Couldn't copy.");
    }
  };

  return (
    <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-ink">System prompt — WhatsApp receptionist</p>
          <p className="mt-0.5 text-xs text-ink-muted">
            {canEdit
              ? "You can edit the practice-specific instructions below. The base template is fixed."
              : "Read-only for you — only the practice owner can edit these instructions."}
          </p>
        </div>
        <button
          onClick={copy}
          className="flex shrink-0 items-center gap-1.5 rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-300 hover:text-teal-700">
          <CopyIcon className="h-3.5 w-3.5" /> Copy
        </button>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-ink-muted">Loading…</p>
      ) : error || !prompt ? (
        <p className="mt-4 text-sm text-ink-muted">Couldn't load the system prompt.</p>
      ) : (
        <>
          <pre className="mt-4 max-h-72 overflow-auto whitespace-pre-wrap rounded-2xl bg-sand-50 p-4 font-mono text-xs leading-relaxed text-ink">
            {prompt.system_prompt}
          </pre>

          {!editing ? (
            canEdit && (
              <button
                onClick={startEdit}
                className="mt-3 flex items-center gap-1.5 rounded-full bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
                <PencilIcon className="h-4 w-4" /> Edit instructions
              </button>
            )
          ) : (
            <div className="mt-4 space-y-3">
              <label className="block text-xs font-semibold text-ink-soft">
                Practice-specific instructions
              </label>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={6}
                placeholder="e.g. Clinic name, visiting hours, which procedures we book over chat, pricing policy, Urdu/English response preference…"
                className="w-full resize-y rounded-2xl border border-sand-200 bg-white p-3 font-mono text-xs text-ink focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
              <p className="text-xs text-ink-muted">
                These are appended to the fixed base template and apply to every inbound
                WhatsApp message. Empty = back to the base template only.
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={save}
                  disabled={saving}
                  className="flex items-center gap-1.5 rounded-full bg-teal-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60">
                  {saving ? <RefreshCwIcon className="h-4 w-4 animate-spin" /> : <CheckIcon className="h-4 w-4" />} Save
                </button>
                <button
                  onClick={cancelEdit}
                  className="flex items-center gap-1.5 rounded-full border border-sand-200 px-4 py-2 text-sm font-semibold text-ink-soft transition-colors hover:border-sand-300 hover:text-ink">
                  <XIcon className="h-4 w-4" /> Cancel
                </button>
                {prompt.custom_instructions && (
                  <button
                    onClick={() => setDraft("")}
                    className="text-xs font-semibold text-red-500 hover:text-red-600">
                    Clear instructions
                  </button>
                )}
              </div>
            </div>
          )}

          {flash && <p className="mt-3 text-xs font-semibold text-teal-700">{flash}</p>}
          {prompt.updated_at && !editing && (
            <p className="mt-2 text-[11px] text-ink-muted">Last edited {new Date(prompt.updated_at).toLocaleString()}</p>
          )}
        </>
      )}
    </div>
  );
}