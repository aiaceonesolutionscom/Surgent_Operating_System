import React, { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { ArrowLeftIcon, PlusIcon, MinusIcon, AlertTriangleIcon, EditIcon, Trash2Icon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import {
  getInventoryItem,
  listInventoryBatches,
  receiveInventoryBatch,
  consumeInventoryStock,
  updateInventoryItem,
  type InventoryItemResponse,
  type InventoryBatchResponse,
  type UpdateInventoryItemRequest
} from "../../../api/entities";
import { DASHBOARD_ROUTES } from "../constants/routes";

function formatDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

// Pydantic serialises Decimal as a JSON string (e.g. "25.00"), so coerce
// before formatting instead of trusting the declared number type.
function formatCurrency(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(n);
}

function isExpiringSoon(iso: string | null) {
  if (!iso) return false;
  const days = (new Date(iso).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
  return days >= 0 && days <= 30;
}

function isExpired(iso: string | null) {
  if (!iso) return false;
  return new Date(iso).getTime() < Date.now();
}

export function InventoryItemDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { authedFetch } = usePlan();
  const navigate = useNavigate();
  const [item, setItem] = useState<InventoryItemResponse | null>(null);
  const [batches, setBatches] = useState<InventoryBatchResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showReceive, setShowReceive] = useState(false);
  const [showConsume, setShowConsume] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refetch() {
    if (!authedFetch || !id) return;
    const [itemData, batchData] = await Promise.all([
      getInventoryItem(authedFetch, id),
      listInventoryBatches(authedFetch, id)
    ]);
    setItem(itemData);
    setBatches(batchData);
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch || !id) {
        setLoading(false);
        return;
      }
      try {
        await refetch();
      } catch {
        if (!cancelled) setItem(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, id]);

  if (loading) return null;

  if (!item) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center">
        <AlertTriangleIcon className="h-12 w-12 mx-auto text-warning" />
        <p className="mt-3 text-sm font-semibold text-ink">Inventory item not found</p>
        <p className="mt-1 text-sm text-ink-muted">The item may have been deleted or the ID is invalid.</p>
        <Link
          to={DASHBOARD_ROUTES.inventory}
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-teal-600 hover:underline"
        >
          <ArrowLeftIcon className="h-4 w-4" /> Back to inventory
        </Link>
      </div>);
  }

  async function handleUpdate(updatedData: UpdateInventoryItemRequest) {
    if (!authedFetch || !id) return;
    try {
      const updated = await updateInventoryItem(authedFetch, id, updatedData);
      setItem(updated);
      setShowEdit(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update item");
    }
  }

  async function handleDelete() {
    if (!authedFetch || !id || !item) return;
    const stockNote = item.on_hand_quantity > 0
      ? `\n\nNote: this item currently has ${item.on_hand_quantity} ${item.unit || "units"} in stock. Deleting it only archives the catalogue entry — your batch history and stock records stay intact.`
      : "";
    if (!window.confirm(`Delete "${item.name}"? It will be removed from your active inventory list.${stockNote}`)) return;
    setDeleting(true);
    setError(null);
    try {
      await updateInventoryItem(authedFetch, id, { is_active: false });
      navigate(DASHBOARD_ROUTES.inventory);
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Failed to delete item");
      setDeleting(false);
    }
  }

  return (
    <>
      <Link
        to={DASHBOARD_ROUTES.inventory}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">
        <ArrowLeftIcon className="h-4 w-4" /> Back to inventory
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <PageHeader title={item.name} subtitle={[item.sku, item.category].filter(Boolean).join(" · ") || undefined} />
        <div className="flex flex-wrap shrink-0 items-center gap-2.5">
          <button
            type="button"
            onClick={() => setShowEdit((v) => !v)}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-400 hover:bg-teal-50">
            <EditIcon className="h-4 w-4" /> Edit
          </button>
          <button
            type="button"
            onClick={() => setShowConsume((v) => !v)}
            className="flex items-center gap-1.5 rounded-xl border border-sand-200 px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-danger/40 hover:text-danger">
            <MinusIcon className="h-4 w-4" /> Record usage
          </button>
          <button
            type="button"
            onClick={() => setShowReceive((v) => !v)}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            <PlusIcon className="h-4 w-4" /> Receive stock
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="flex items-center gap-1.5 rounded-xl border border-danger/30 px-4 py-2.5 text-sm font-semibold text-danger transition-colors hover:bg-danger hover:text-white disabled:cursor-not-allowed disabled:opacity-50">
            <Trash2Icon className="h-4 w-4" /> {deleting ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      {error && !showConsume && (
        <p className="mb-4 rounded-xl bg-danger/10 px-4 py-3 text-sm font-medium text-danger">{error}</p>
      )}

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex items-center gap-6 flex-wrap">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">On hand</p>
            <p className={`mt-1 font-display text-[28px] font-600 tabular-nums ${item.is_low_stock ? "text-danger" : "text-ink"}`}>
              {item.on_hand_quantity.toLocaleString()} {item.unit || ""}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Unit cost</p>
            <p className="mt-1 font-display text-[28px] font-600 tabular-nums text-ink">
              {formatCurrency(item.unit_cost)}
            </p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Total value</p>
            <p className="mt-1 font-display text-[28px] font-600 tabular-nums text-teal-700">
              {formatCurrency(item.total_value)}
            </p>
          </div>
          {item.is_low_stock &&
          <span className="flex items-center gap-1.5 rounded-full bg-danger/10 px-3 py-1.5 text-xs font-semibold text-danger">
              <AlertTriangleIcon className="h-3.5 w-3.5" /> Low stock — below reorder threshold ({item.reorder_threshold})
            </span>
          }
          {item.on_hand_quantity === 0 &&
          <span className="flex items-center gap-1.5 rounded-full bg-danger/10 px-3 py-1.5 text-xs font-semibold text-danger">
              <AlertTriangleIcon className="h-3.5 w-3.5" /> Out of stock
            </span>
          }
        </div>
      </div>

      {showEdit &&
      <EditForm
        item={item}
        onSubmit={handleUpdate}
        onCancel={() => setShowEdit(false)} />
      }

      {showReceive &&
      <ReceiveForm
        onSubmit={async (data) => {
          if (!id || !authedFetch) return;
          await receiveInventoryBatch(authedFetch, id, data);
          await refetch();
          setShowReceive(false);
        }} />
      }

      {showConsume &&
      <ConsumeForm
        onSubmit={async (quantity) => {
          if (!id || !authedFetch) return;
          setError(null);
          try {
            await consumeInventoryStock(authedFetch, id, quantity);
            await refetch();
            setShowConsume(false);
          } catch (err: unknown) {
            setError(err instanceof Error && err.message ? err.message : "Couldn't record usage — try again.");
          }
        }}
        error={error} />
      }

      <p className="mb-3 text-sm font-bold text-ink">Batches received</p>
      {batches.length === 0 ?
      <p className="text-sm text-ink-muted">No stock received yet.</p> :

      <div className="overflow-x-auto rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                <th className="px-5 py-3">Lot</th>
                <th className="px-5 py-3">Received</th>
                <th className="px-5 py-3">Expiry</th>
                <th className="px-5 py-3">Remaining</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-sand-100">
              {batches.map((b) =>
            <tr key={b.id} className={b.quantity === 0 ? "opacity-40" : ""}>
                  <td className="px-5 py-3 text-ink-soft">{b.lot_number || "—"}</td>
                  <td className="px-5 py-3 text-ink-soft">{formatDate(b.received_at)}</td>
                  <td className="px-5 py-3">
                    <span className={isExpired(b.expiry_date) ? "font-semibold text-danger" : isExpiringSoon(b.expiry_date) ? "font-semibold text-warning" : "text-ink-soft"}>
                      {formatDate(b.expiry_date)}
                    </span>
                  </td>
                  <td className="px-5 py-3 font-medium text-ink">{b.quantity.toLocaleString()}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      }
    </>);
}

function EditForm({ item, onSubmit, onCancel }: { item: InventoryItemResponse; onSubmit: (data: UpdateInventoryItemRequest) => Promise<void>; onCancel: () => void }) {
  const [name, setName] = useState(item.name);
  const [sku, setSku] = useState(item.sku || "");
  const [category, setCategory] = useState(item.category || "");
  const [unit, setUnit] = useState(item.unit || "");
  const [reorderThreshold, setReorderThreshold] = useState(item.reorder_threshold ? String(item.reorder_threshold) : "");
  const [unitCost, setUnitCost] = useState(item.unit_cost ? String(item.unit_cost) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        name: name.trim(),
        sku: sku.trim() || null,
        category: category.trim() || null,
        unit: unit.trim() || null,
        reorder_threshold: reorderThreshold ? Number(reorderThreshold) : null,
        unit_cost: unitCost ? Number(unitCost) : null
      });
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Name *</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">SKU</span>
          <input
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Category</span>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Unit</span>
          <input
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Unit cost</span>
          <input
            type="number"
            step="0.01"
            min="0"
            value={unitCost}
            onChange={(e) => setUnitCost(e.target.value)}
            placeholder="25.00"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Low-stock at</span>
          <input
            type="number"
            min="0"
            value={reorderThreshold}
            onChange={(e) => setReorderThreshold(e.target.value)}
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
        </label>
      </div>

      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}

      <div className="mt-5 flex items-center justify-end gap-3">
        <button type="button" onClick={onCancel} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </form>
  );
}

function ReceiveForm({ onSubmit }: { onSubmit: (data: { lot_number?: string | null; quantity: number; expiry_date?: string | null }) => Promise<void> }) {
  const [lotNumber, setLotNumber] = useState("");
  const [quantity, setQuantity] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!quantity) return;
    setSaving(true);
    setError(null);
    try {
      await onSubmit({ lot_number: lotNumber.trim() || null, quantity: Number(quantity), expiry_date: expiryDate || null });
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't receive stock — try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="grid gap-4 sm:grid-cols-3">
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Quantity *</span>
          <input required type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Lot number</span>
          <input value={lotNumber} onChange={(e) => setLotNumber(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Expiry date</span>
          <input type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white" />
        </label>
      </div>
      {error && <p className="mt-3 text-sm font-medium text-danger">{error}</p>}
      <div className="mt-5 flex justify-end">
        <button type="submit" disabled={saving || !quantity} className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
          {saving ? "Saving…" : "Receive stock"}
        </button>
      </div>
    </form>
  );
}

function ConsumeForm({ onSubmit, error }: { onSubmit: (quantity: number) => Promise<void>; error: string | null }) {
  const [quantity, setQuantity] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!quantity) return;
    setSaving(true);
    await onSubmit(Number(quantity));
    setSaving(false);
  }

  return (
    <form onSubmit={handleSubmit} className="mb-6 flex items-end gap-3 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <label className="block">
        <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Quantity used *</span>
        <input required type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="w-32 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-danger/40" />
      </label>
      <button type="submit" disabled={saving || !quantity} className="rounded-xl bg-danger px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40">
        {saving ? "Recording…" : "Record usage"}
      </button>
      {error && <p className="text-sm font-medium text-danger">{error}</p>}
    </form>
  );
}