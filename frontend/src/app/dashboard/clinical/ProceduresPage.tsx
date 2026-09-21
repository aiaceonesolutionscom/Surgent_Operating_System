import React, { useState } from "react";
import { ScissorsIcon, PlusIcon, PencilIcon, CheckIcon, XIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { useProcedures } from "./useProcedures";
import type { ProcedureResponse } from "../../../api/entities";

export function ProceduresPage() {
  const { authedFetch } = usePlan();
  const { procedures, loading, create, update } = useProcedures(authedFetch);
  const [adding, setAdding] = useState(false);

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <PageHeader title="Procedures" subtitle="Your practice's own procedure catalog and pricing — used when building treatment plans." />
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          <PlusIcon className="h-4 w-4" /> Add procedure
        </button>
      </div>

      {adding && <AddForm onCreate={create} onDone={() => setAdding(false)} />}

      <div className="mt-6">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        procedures.length === 0 ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState icon={ScissorsIcon} title="No procedures yet" body="Add the procedures your practice performs, with pricing, to build treatment plans against them." />
          </div> :

        <div className="overflow-x-auto rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead>
                <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3">Name</th>
                  <th className="px-5 py-3">Category</th>
                  <th className="px-5 py-3">Price</th>
                  <th className="px-5 py-3">Duration</th>
                  <th className="px-5 py-3">Sessions</th>
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-100">
                {procedures.map((p) => <ProcedureRow key={p.id} procedure={p} onUpdate={update} />)}
              </tbody>
            </table>
          </div>
        }
      </div>
    </>);

}

function AddForm({
  onCreate, onDone
}: {
  onCreate: (data: { name: string; category?: string | null; base_price?: number | null; duration_minutes?: number | null; default_session_count?: number; default_checklist?: string[] }) => Promise<boolean>;
  onDone: () => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [price, setPrice] = useState("");
  const [duration, setDuration] = useState("");
  const [sessions, setSessions] = useState("1");
  const [checklistText, setChecklistText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    const ok = await onCreate({
      name: name.trim(),
      category: category.trim() || null,
      base_price: price ? Number(price) : null,
      duration_minutes: duration ? Number(duration) : null,
      default_session_count: sessions ? Number(sessions) : 1,
      default_checklist: checklistText.split("\n").map((l) => l.trim()).filter(Boolean)
    });
    setSaving(false);
    if (ok) onDone();
    else setError("Couldn't save — try again.");
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Name *</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Rhinoplasty"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Category</span>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Surgical"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Price ($)</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Duration (min)</span>
          <input
            type="number"
            min="0"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Sessions</span>
          <input
            type="number"
            min="1"
            value={sessions}
            onChange={(e) => setSessions(e.target.value)}
            title="How many visits this procedure normally takes (e.g. 6 for a laser hair removal course)"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
      </div>

      <label className="mt-4 block">
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Pre-visit checklist (one item per line, optional)</span>
        <textarea
          rows={3}
          value={checklistText}
          onChange={(e) => setChecklistText(e.target.value)}
          placeholder={"Confirm no recent Accutane use\nNumbing cream applied\nConsent form on file"}
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        <span className="mt-1 block text-[11px] text-ink-muted">Copied onto every session of this procedure — the doctor checks these off before/during the visit.</span>
      </label>

      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

      <div className="mt-5 flex items-center justify-end gap-3">
        <button type="button" onClick={onDone} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

          {saving ? "Saving…" : "Add procedure"}
        </button>
      </div>
    </form>);

}

function ProcedureRow({
  procedure, onUpdate
}: {
  procedure: ProcedureResponse;
  onUpdate: (id: string, data: { name?: string; category?: string | null; base_price?: number | null; duration_minutes?: number | null; default_session_count?: number; default_checklist?: string[]; is_active?: boolean }) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(procedure.name);
  const [category, setCategory] = useState(procedure.category || "");
  const [price, setPrice] = useState(procedure.base_price != null ? String(procedure.base_price) : "");
  const [duration, setDuration] = useState(procedure.duration_minutes != null ? String(procedure.duration_minutes) : "");
  const [sessions, setSessions] = useState(String(procedure.default_session_count || 1));
  const [checklistText, setChecklistText] = useState((procedure.default_checklist || []).join("\n"));
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    const ok = await onUpdate(procedure.id, {
      name: name.trim(),
      category: category.trim() || null,
      base_price: price ? Number(price) : null,
      duration_minutes: duration ? Number(duration) : null,
      default_session_count: sessions ? Number(sessions) : 1,
      default_checklist: checklistText.split("\n").map((l) => l.trim()).filter(Boolean)
    });
    setSaving(false);
    if (ok) setEditing(false);
  }

  if (editing) {
    return (
      <tr>
        <td className="px-5 py-3"><input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" /></td>
        <td className="px-5 py-3"><input value={category} onChange={(e) => setCategory(e.target.value)} className="w-full rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" /></td>
        <td className="px-5 py-3"><input type="number" value={price} onChange={(e) => setPrice(e.target.value)} className="w-24 rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" /></td>
        <td className="px-5 py-3"><input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} className="w-20 rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" /></td>
        <td className="px-5 py-3"><input type="number" min="1" value={sessions} onChange={(e) => setSessions(e.target.value)} className="w-16 rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" /></td>
        <td className="px-5 py-3">
          <div className="flex items-center gap-1.5">
            <button type="button" onClick={save} disabled={saving} className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-600 text-white hover:bg-teal-700 disabled:opacity-50"><CheckIcon className="h-3.5 w-3.5" /></button>
            <button type="button" onClick={() => setEditing(false)} className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100"><XIcon className="h-3.5 w-3.5" /></button>
          </div>
        </td>
        <td colSpan={6} className="px-5 pb-3">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-ink-muted">Pre-visit checklist (one item per line)</span>
            <textarea rows={2} value={checklistText} onChange={(e) => setChecklistText(e.target.value)} className="w-full rounded-lg border border-sand-200 px-2.5 py-1.5 text-sm outline-none focus:border-teal-600/40" />
          </label>
        </td>
      </tr>);

  }

  return (
    <tr className={!procedure.is_active ? "opacity-50" : ""}>
      <td className="px-5 py-3 font-medium text-ink">{procedure.name}</td>
      <td className="px-5 py-3 text-ink-soft">{procedure.category || "—"}</td>
      <td className="px-5 py-3 text-ink-soft">{procedure.base_price != null ? `$${procedure.base_price.toLocaleString()}` : "—"}</td>
      <td className="px-5 py-3 text-ink-soft">{procedure.duration_minutes != null ? `${procedure.duration_minutes} min` : "—"}</td>
      <td className="px-5 py-3 text-ink-soft">{procedure.default_session_count > 1 ? `${procedure.default_session_count} visits` : "1 visit"}</td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-1.5">
          <button type="button" onClick={() => setEditing(true)} className="flex h-7 w-7 items-center justify-center rounded-lg text-ink-muted hover:bg-sand-100 hover:text-teal-600"><PencilIcon className="h-3.5 w-3.5" /></button>
          <button
            type="button"
            onClick={() => onUpdate(procedure.id, { is_active: !procedure.is_active })}
            className="rounded-lg px-2 py-1 text-[11px] font-semibold text-ink-muted hover:text-danger">

            {procedure.is_active ? "Deactivate" : "Reactivate"}
          </button>
        </div>
      </td>
    </tr>);

}
