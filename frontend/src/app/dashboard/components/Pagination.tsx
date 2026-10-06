import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react";

/**
 * Numbered pagination bar with previous/next controls and a windowed page
 * list (1 … 4 5 6 … 12) so long tables stay navigable instead of rendering
 * hundreds of rows at once.
 */
export function Pagination({
  page,
  pageCount,
  onPageChange,
  totalItems,
  pageSize,
  itemLabel = "items"
}: {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  totalItems: number;
  pageSize: number;
  itemLabel?: string;
}) {
  if (pageCount <= 1) return null;

  const first = totalItems === 0 ? 0 : (page - 1) * pageSize + 1;
  const last = Math.min(page * pageSize, totalItems);

  const go = (next: number) => {
    if (next < 1 || next > pageCount) return;
    onPageChange(next);
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-sand-200 px-5 py-3.5">
      <p className="text-xs text-ink-muted">
        Showing <span className="font-semibold text-ink">{first}</span>–<span className="font-semibold text-ink">{last}</span> of{" "}
        <span className="font-semibold text-ink">{totalItems.toLocaleString()}</span> {itemLabel}
      </p>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => go(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-sand-200 text-ink-soft transition-colors hover:border-ink-muted/40 hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent">
          <ChevronLeftIcon className="h-4 w-4" />
        </button>

        {pageWindow(page, pageCount).map((entry, i) =>
          entry === "gap" ? (
            <span key={`gap-${i}`} className="flex h-8 w-6 items-center justify-center text-xs text-ink-muted">
              …
            </span>
          ) : (
            <button
              key={entry}
              type="button"
              onClick={() => go(entry)}
              aria-current={entry === page ? "page" : undefined}
              className={`flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-xs font-semibold transition-colors ${
                entry === page
                  ? "bg-teal-600 text-white"
                  : "border border-sand-200 text-ink-soft hover:border-ink-muted/40 hover:bg-sand-100"
              }`}>
              {entry}
            </button>
          )
        )}

        <button
          type="button"
          onClick={() => go(page + 1)}
          disabled={page >= pageCount}
          aria-label="Next page"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-sand-200 text-ink-soft transition-colors hover:border-ink-muted/40 hover:bg-sand-100 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent">
          <ChevronRightIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

/** Page numbers to render, with "gap" markers where pages are skipped. */
function pageWindow(page: number, pageCount: number): (number | "gap")[] {
  if (pageCount <= 7) return Array.from({ length: pageCount }, (_, i) => i + 1);

  const pages = new Set<number>([1, pageCount, page]);
  for (const offset of [-1, 1]) {
    const candidate = page + offset;
    if (candidate > 1 && candidate < pageCount) pages.add(candidate);
  }

  const sorted = [...pages].sort((a, b) => a - b);
  const out: (number | "gap")[] = [];
  sorted.forEach((value, i) => {
    if (i > 0 && value - sorted[i - 1] > 1) out.push("gap");
    out.push(value);
  });
  return out;
}
