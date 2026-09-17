import { useEffect, useState } from "react";
import { SearchIcon, Loader2Icon, InboxIcon } from "lucide-react";
import { listAdminSalesLeads, type SalesLeadResponse } from "../../../api/admin";

const STATUS_CLASS: Record<string, string> = {
  new: "bg-accent-500/10 text-accent-700",
  contacted: "bg-success/10 text-success",
  converted: "bg-success/10 text-success",
  lost: "bg-ink-muted/10 text-ink-muted"
};

function when(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit"
    });
  } catch {
    return iso;
  }
}

export function SalesLeadsPage() {
  const [rows, setRows] = useState<SalesLeadResponse[] | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    listAdminSalesLeads({ q: q || undefined })
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load sales leads.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  return (
    <>
      <div className="flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Sales pipeline</p>
        <h1 className="font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">Clinic-buyer leads from the website chat</h1>
        <p className="max-w-2xl text-sm text-ink-muted">
          Clinic owners evaluating Aiaceone who talked to Aria on the marketing site and left their details. Following
          up with these is the Aiaceone sales team's job — patients belong to clinics, these belong to us.
        </p>
      </div>

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2 rounded-xl border border-sand-200 bg-white px-3.5 py-2.5 sm:w-80">
          <SearchIcon className="h-4 w-4 text-ink-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name or email…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />
        </div>
        {rows && rows.length > 0 && (
          <p className="text-xs font-medium text-ink-muted">{rows.length} lead{rows.length === 1 ? "" : "s"}</p>
        )}
      </div>

      <div className="mt-5 overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        {error && <p className="p-6 text-sm text-danger">{error}</p>}
        {!rows && !error && (
          <div className="flex justify-center py-16">
            <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
          </div>
        )}
        {rows && rows.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <InboxIcon className="h-8 w-8 text-ink-muted/40" />
            <p className="text-sm text-ink-muted">No leads yet — when a clinic buyer gives Aria their details, they land here.</p>
          </div>
        )}
        {rows && rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-sand-200 text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3.5">Lead</th>
                  <th className="px-5 py-3.5">Clinic / company</th>
                  <th className="px-5 py-3.5">What they need</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Captured</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-sand-100 last:border-0 hover:bg-sand-50">
                    <td className="px-5 py-4">
                      <p className="font-semibold text-ink">{r.full_name}</p>
                      <p className="text-xs text-ink-muted">{r.email} {r.phone ? `· ${r.phone}` : ""}</p>
                    </td>
                    <td className="px-5 py-4 text-ink-soft">{r.company || "—"}</td>
                    <td className="max-w-[280px] px-5 py-4 text-ink-soft">{r.message || "—"}</td>
                    <td className="px-5 py-4">
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${STATUS_CLASS[r.status] ?? STATUS_CLASS.new}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-5 py-4 whitespace-nowrap text-xs text-ink-muted">{when(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}