import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PackageIcon, PlusIcon, AlertTriangleIcon, CalculatorIcon, SearchIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { EmptyState } from "../components/EmptyState";
import { Pagination } from "../components/Pagination";
import { usePlan } from "../plan/PlanContext";
import { useInventory } from "./useInventory";
import { DASHBOARD_ROUTES } from "../constants/routes";

const PAGE_SIZE = 20;

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 }).format(value);
}

export function InventoryPage() {
  const { authedFetch } = usePlan();
  const { items, loading, create } = useInventory(authedFetch);
  const [adding, setAdding] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [page, setPage] = useState(1);

  const categories = useMemo(() => {
    const set = new Set<string>();
    items.forEach((item) => {
      if (item.category) set.add(item.category);
    });
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [items]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items
      .filter((item) => (category === "all" ? true : item.category === category))
      .filter((item) => {
        if (!q) return true;
        return (
          item.name.toLowerCase().includes(q) ||
          (item.sku ?? "").toLowerCase().includes(q) ||
          (item.category ?? "").toLowerCase().includes(q)
        );
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [items, query, category]);

  // Any filter change can shrink the result set below the current page, so
  // snap back to page 1 rather than showing an empty table.
  useEffect(() => {
    setPage(1);
  }, [query, category, items.length]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visible = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  // Totals always reflect the whole practice, not just the visible page.
  const totalInventoryValue = items.reduce((sum, item) => sum + (item.total_value || 0), 0);
  const totalUnits = items.reduce((sum, item) => sum + item.on_hand_quantity, 0);
  const lowStockCount = items.filter((item) => item.is_low_stock).length;
  const filteredValue = filtered.reduce((sum, item) => sum + (item.total_value || 0), 0);

  return (
    <>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <PageHeader title="Inventory" subtitle="Supplies and stock — what you have on hand, and what's running low." />
          <p className="mt-2 flex items-center gap-2 text-sm font-medium text-teal-600">
            <CalculatorIcon className="h-4 w-4" />
            Total inventory value: <span className="font-semibold text-ink">{formatCurrency(totalInventoryValue)}</span>
          </p>
        </div>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          <PlusIcon className="h-4 w-4" /> Add item
        </button>
      </div>

      {adding && <AddForm onCreate={create} onDone={() => setAdding(false)} />}

      {items.length > 0 && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search item or SKU…"
                className="w-64 rounded-xl border border-sand-200 bg-canvas py-2 pl-9 pr-3 text-sm text-ink outline-none transition-colors focus:border-teal-400 focus:bg-white" />
            </div>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm font-medium text-ink outline-none transition-colors focus:border-teal-400 focus:bg-white">
              <option value="all">All categories ({items.length})</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            {(query.trim() || category !== "all") && (
              <button
                type="button"
                onClick={() => { setQuery(""); setCategory("all"); }}
                className="rounded-xl px-3 py-2 text-sm font-semibold text-teal-600 transition-colors hover:bg-sand-100">
                Clear
              </button>
            )}
          </div>
          <p className="text-xs text-ink-muted">
            {lowStockCount > 0 && (
              <span className="mr-3 inline-flex items-center gap-1 font-semibold text-danger">
                <AlertTriangleIcon className="h-3.5 w-3.5" /> {lowStockCount} low stock
              </span>
            )}
            {filtered.length.toLocaleString()} of {items.length.toLocaleString()} items
          </p>
        </div>
      )}

      <div className="mt-6">
        {loading ?
        <p className="text-sm text-ink-muted">Loading…</p> :
        items.length === 0 ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState icon={PackageIcon} title="No inventory items yet" body="Add the supplies your practice stocks, then receive stock against them to start tracking what's on hand." />
          </div> :
        visible.length === 0 ?
        <div className="rounded-3xl border border-sand-200 bg-white">
            <EmptyState icon={SearchIcon} title="No items match that filter" body="Try a different search term or category." />
          </div> :

        <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead>
                <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3">Item</th>
                  <th className="px-5 py-3">Category</th>
                  <th className="px-5 py-3">On hand</th>
                  <th className="px-5 py-3">Unit cost</th>
                  <th className="px-5 py-3">Total value</th>
                  <th className="px-5 py-3">Unit</th>
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-100">
                {visible.map((item) =>
              <tr key={item.id} className={!item.is_active ? "opacity-50" : ""}>
                    <td className="px-5 py-3">
                      <Link to={DASHBOARD_ROUTES.inventoryItemDetail(item.id)} className="font-medium text-ink hover:text-teal-600 hover:underline">
                        {item.name}
                      </Link>
                      {item.sku && <span className="ml-2 text-xs text-ink-muted">{item.sku}</span>}
                    </td>
                    <td className="px-5 py-3 text-ink-soft">{item.category || "—"}</td>
                    <td className="px-5 py-3">
                      <span className={`font-semibold ${item.is_low_stock ? "text-danger" : "text-ink"}`}>{item.on_hand_quantity.toLocaleString()}</span>
                      {item.is_low_stock &&
                  <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-semibold text-danger">
                          <AlertTriangleIcon className="h-3 w-3" /> Low
                        </span>
                  }
                    </td>
                    <td className="px-5 py-3 text-ink-soft">{formatCurrency(item.unit_cost)}</td>
                    <td className="px-5 py-3">
                      <span className={`font-semibold ${item.total_value !== null && item.total_value > 1000 ? "text-teal-700" : "text-ink"}`}>
                        {formatCurrency(item.total_value)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-ink-soft">{item.unit || "—"}</td>
                    <td className="px-5 py-3">
                      <Link to={DASHBOARD_ROUTES.inventoryItemDetail(item.id)} className="text-xs font-semibold text-teal-600 hover:underline">
                        Manage
                      </Link>
                    </td>
                  </tr>
              )}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-sand-200 bg-sand-50 font-semibold text-sm">
                  <td className="px-5 py-3" colSpan={2}>
                    {query.trim() || category !== "all"
                      ? `Filtered total (${filtered.length} items)`
                      : `All items (${items.length})`}
                  </td>
                  <td className="px-5 py-3">
                    {(query.trim() || category !== "all"
                      ? filtered.reduce((sum, i) => sum + i.on_hand_quantity, 0)
                      : totalUnits
                    ).toLocaleString()}
                  </td>
                  <td className="px-5 py-3">—</td>
                  <td className="px-5 py-3 text-teal-700">
                    {formatCurrency(query.trim() || category !== "all" ? filteredValue : totalInventoryValue)}
                  </td>
                  <td className="px-5 py-3">—</td>
                  <td className="px-5 py-3"></td>
                </tr>
              </tfoot>
            </table>
            </div>
            <Pagination
              page={safePage}
              pageCount={pageCount}
              onPageChange={setPage}
              totalItems={filtered.length}
              pageSize={PAGE_SIZE}
              itemLabel="items" />
          </div>
        }
      </div>
    </>);
}

function AddForm({ onCreate, onDone }: { onCreate: (data: { name: string; sku?: string | null; category?: string | null; unit?: string | null; reorder_threshold?: number | null; unit_cost?: number | null }) => Promise<unknown>; onDone: () => void }) {
  const [name, setName] = useState("");
  const [sku, setSku] = useState("");
  const [category, setCategory] = useState("");
  const [unit, setUnit] = useState("");
  const [reorderThreshold, setReorderThreshold] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await onCreate({
        name: name.trim(),
        sku: sku.trim() || null,
        category: category.trim() || null,
        unit: unit.trim() || null,
        reorder_threshold: reorderThreshold ? Number(reorderThreshold) : null,
        unit_cost: unitCost ? Number(unitCost) : null
      });
      onDone();
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
            placeholder="Surgical Gloves (M)"
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
            placeholder="Consumables"
            className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

        </label>
        <label className="block">
          <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Unit</span>
          <input
            value={unit}
            onChange={(e) => setUnit(e.target.value)}
            placeholder="box"
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
        <button type="button" onClick={onDone} className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving || !name.trim()}
          className="rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

          {saving ? "Saving…" : "Add item"}
        </button>
      </div>
    </form>);
}