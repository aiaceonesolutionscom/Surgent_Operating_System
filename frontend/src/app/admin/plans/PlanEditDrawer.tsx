import { useState } from "react";
import { XIcon, Loader2Icon, PlusIcon, Trash2Icon } from "lucide-react";
import type { PlanResponse } from "../../../api/practice";

interface PlanEditDrawerProps {
  plan: PlanResponse;
  onClose: () => void;
  onSave: (body: Partial<PlanResponse>) => Promise<void>;
}

// The "change pricing without code" screen — every field here PATCHes the
// real backend/src/models/plan.py row (via PATCH /api/v1/admin/plans/{id}),
// which services/checkout/checkout_services.py reads directly at checkout
// time. Not a mock form.
export function PlanEditDrawer({ plan, onClose, onSave }: PlanEditDrawerProps) {
  const [name, setName] = useState(plan.name);
  const [tagline, setTagline] = useState(plan.tagline ?? "");
  const [price, setPrice] = useState(plan.price != null ? String(plan.price) : "");
  const [isCustomPricing, setIsCustomPricing] = useState(plan.is_custom_pricing);
  const [isActive, setIsActive] = useState(plan.is_active);
  const [highlight, setHighlight] = useState(plan.highlight);
  const [features, setFeatures] = useState<string[]>(plan.features.length ? plan.features : [""]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await onSave({
        name,
        tagline: tagline || null,
        price: isCustomPricing ? null : price === "" ? null : Number(price),
        is_custom_pricing: isCustomPricing,
        is_active: isActive,
        highlight,
        features: features.map((f) => f.trim()).filter(Boolean)
      });
      onClose();
    } catch {
      setError("Couldn't save — please try again.");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/40" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-md flex-col overflow-y-auto bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}>

        <div className="flex items-center justify-between border-b border-sand-200 px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-accent-500">{plan.tier}</p>
            <h2 className="font-display text-xl font-600 text-ink">Edit plan</h2>
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink">
            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 space-y-5 px-6 py-6">
          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50" />

          </label>

          <label className="block">
            <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Tagline</span>
            <input
              value={tagline}
              onChange={(e) => setTagline(e.target.value)}
              className="w-full rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none focus:border-accent-500/50" />

          </label>

          <label className="flex items-center justify-between rounded-xl border border-sand-200 px-3.5 py-2.5">
            <span className="text-sm font-medium text-ink">Custom pricing ("Contact us")</span>
            <input
              type="checkbox"
              checked={isCustomPricing}
              onChange={(e) => setIsCustomPricing(e.target.checked)}
              className="h-4 w-4 accent-[#2563EB]" />

          </label>

          {!isCustomPricing &&
          <label className="block">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Price (USD / month)</span>
              <div className="flex items-center gap-2 rounded-xl border border-accent-500/50 px-3.5 py-2.5">
                <span className="text-sm text-ink-muted">$</span>
                <input
                inputMode="decimal"
                value={price}
                onChange={(e) => setPrice(e.target.value.replace(/[^0-9.]/g, ""))}
                className="w-full bg-transparent text-sm text-ink outline-none" />

              </div>
            </label>
          }

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Features</span>
              <button
                onClick={() => setFeatures((f) => [...f, ""])}
                className="flex items-center gap-1 text-xs font-semibold text-accent-500 hover:underline">

                <PlusIcon className="h-3 w-3" /> Add
              </button>
            </div>
            <div className="space-y-2">
              {features.map((f, i) =>
              <div key={i} className="flex items-center gap-2">
                  <input
                  value={f}
                  onChange={(e) => setFeatures((prev) => prev.map((x, j) => j === i ? e.target.value : x))}
                  className="w-full rounded-xl border border-sand-200 px-3.5 py-2 text-sm text-ink outline-none focus:border-accent-500/50" />

                  <button
                  onClick={() => setFeatures((prev) => prev.filter((_, j) => j !== i))}
                  className="shrink-0 rounded-lg p-2 text-ink-muted transition-colors hover:bg-danger/10 hover:text-danger">

                    <Trash2Icon className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="h-4 w-4 accent-[#2563EB]" />
              Active
            </label>
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={highlight} onChange={(e) => setHighlight(e.target.checked)} className="h-4 w-4 accent-[#2563EB]" />
              Highlight as "Most popular"
            </label>
          </div>

          {error && <p className="text-sm text-danger">{error}</p>}
        </div>

        <div className="border-t border-sand-200 px-6 py-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:opacity-60">

            {saving && <Loader2Icon className="h-4 w-4 animate-spin" />}
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>);

}
