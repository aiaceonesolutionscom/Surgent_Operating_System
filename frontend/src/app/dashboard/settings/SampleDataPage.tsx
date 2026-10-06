import { useCallback, useEffect, useState } from "react";
import {
  DatabaseIcon,
  Trash2Icon,
  Loader2Icon,
  CheckCircle2Icon,
  AlertTriangleIcon,
  SparklesIcon,
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import {
  getSampleDataCounts,
  seedSampleData,
  clearSampleData,
  type SampleDataCountsResponse,
} from "../../../api/entities";

// Owner-only panel backing backend/src/router/sample_data/sample_data_router.py.
//
// The product reason this exists: a clinic owner who came in through the free
// "Request access" path (see multiclinic.md §4) is provisioned with a Practice,
// an owner User, a trial Subscription and 9 AgentConfigs — and nothing else. So
// they land on an empty dashboard with nothing to click. This panel is the
// fastest honest way to give them something real to judge the product by.
//
// Every number on screen is `is_sample=True` data only. The backend refuses to
// touch a real row (every DELETE is scoped by BOTH practice_id and is_sample),
// and sample rows are excluded from finance/analytics aggregates — so a demo
// expense never shows up as a real burn rate.

type Row = { key: keyof Omit<SampleDataCountsResponse, "total">; label: string; note: string };

const ROWS: Row[] = [
  { key: "patients", label: "Patients", note: "Full records with complaints, intake detail and consent state" },
  { key: "appointments", label: "Appointments", note: "Upcoming and past visits, so the calendar has both" },
  { key: "conversations", label: "Conversations", note: "WhatsApp, Instagram, Facebook, SMS and web-chat threads" },
  { key: "messages", label: "Messages", note: "The replies inside those threads — removed with their thread" },
  { key: "inventory_items", label: "Stock items", note: "Consumables and injectables with unit costs" },
  { key: "expenses", label: "Expenses", note: "Rent, utilities, supplies — never counted as real money" },
];

export function SampleDataPage() {
  const { authedFetch } = usePlan();
  const [counts, setCounts] = useState<SampleDataCountsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<"seed" | "clear" | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!authedFetch) return;
    setLoading(true);
    try {
      setCounts(await getSampleDataCounts(authedFetch));
      setError(null);
    } catch {
      setCounts(null);
    } finally {
      setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleSeed() {
    if (!authedFetch || busy) return;
    setBusy("seed");
    setError(null);
    setResult(null);
    try {
      const res = await seedSampleData(authedFetch);
      setCounts(res.counts);
      setResult(res.message);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Couldn't load sample data.");
    } finally {
      setBusy(null);
    }
  }

  async function handleClear() {
    if (!authedFetch || busy) return;
    setBusy("clear");
    setError(null);
    try {
      const res = await clearSampleData(authedFetch);
      setCounts(res.counts);
      setResult(res.message);
      setConfirming(false);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : "Couldn't remove sample data.");
    } finally {
      setBusy(null);
    }
  }

  const hasData = (counts?.total ?? 0) > 0;

  return (
    <>
      <PageHeader
        title="Sample data"
        subtitle="Load a realistic example clinic so you can click through the whole product before you pay. Everything here is clearly marked demo data and you can remove all of it in one click."
      />

      <div className="mt-6 space-y-4">
        <div className="rounded-2xl border border-sand-200 bg-white p-6 shadow-soft">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-lg">
              <h2 className="flex items-center gap-2 text-base font-semibold text-ink">
                <SparklesIcon className="h-4 w-4 text-teal-600" />
                Try the product with a full clinic
              </h2>
              <p className="mt-1.5 text-sm text-ink-muted">
                Creates example patients, appointments, conversations, stock and expenses inside{" "}
                <strong>your</strong> workspace only. Another clinic can never see or delete them.
              </p>
            </div>

            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => void handleSeed()}
                disabled={busy !== null || loading}
                className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50">
                {busy === "seed" ? (
                  <Loader2Icon className="h-4 w-4 animate-spin" />
                ) : (
                  <DatabaseIcon className="h-4 w-4" />
                )}
                {hasData ? "Reload sample data" : "Load sample data"}
              </button>

              <button
                type="button"
                onClick={() => setConfirming(true)}
                disabled={busy !== null || loading || !hasData}
                className="inline-flex items-center gap-2 rounded-full border border-sand-300 px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-danger hover:text-danger disabled:cursor-not-allowed disabled:opacity-40">
                {busy === "clear" ? (
                  <Loader2Icon className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2Icon className="h-4 w-4" />
                )}
                Delete all
              </button>
            </div>
          </div>

          {result && (
            <p className="mt-4 flex items-start gap-2 rounded-xl bg-success/8 px-3.5 py-2.5 text-sm text-success">
              <CheckCircle2Icon className="mt-0.5 h-4 w-4 shrink-0" />
              {result}
            </p>
          )}
          {error && (
            <p className="mt-4 flex items-start gap-2 rounded-xl bg-danger/8 px-3.5 py-2.5 text-sm text-danger">
              <AlertTriangleIcon className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-sand-200 bg-white shadow-soft">
          <div className="border-b border-sand-200 px-6 py-4">
            <h2 className="text-base font-semibold text-ink">What&apos;s in your workspace</h2>
          </div>

          {loading ? (
            <p className="px-6 py-8 text-center text-sm text-ink-muted">Checking…</p>
          ) : (
            <ul className="divide-y divide-sand-200">
              {ROWS.map((row) => {
                const value = counts?.[row.key] ?? 0;
                // Messages are removed by cascade from their thread, so they are
                // reported but never counted toward the removable total.
                const counted = row.key === "messages" ? null : value;
                return (
                  <li key={row.key} className="flex items-center justify-between gap-4 px-6 py-4">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">{row.label}</p>
                      <p className="mt-0.5 text-xs text-ink-muted">{row.note}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="text-sm font-semibold tabular-nums text-ink">{value}</span>
                      {counted !== null && value > 0 && (
                        <span className="rounded-full bg-teal-500/10 px-2.5 py-1 text-[11px] font-medium text-teal-700">
                          demo
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          <div className="border-t border-sand-200 px-6 py-3.5">
            <p className="text-xs text-ink-muted">
              {counts?.total ?? 0} removable row{(counts?.total ?? 0) === 1 ? "" : "s"}. Deleting
              sample data never touches your real records — the server scopes every delete to your
              organisation and to demo rows only.
            </p>
          </div>
        </div>
      </div>

      {confirming && (
        <ConfirmDialog
          counts={counts}
          busy={busy === "clear"}
          onCancel={() => setConfirming(false)}
          onConfirm={() => void handleClear()}
        />
      )}
    </>
  );
}

function ConfirmDialog({
  counts,
  busy,
  onCancel,
  onConfirm,
}: {
  counts: SampleDataCountsResponse | null;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const removable = ROWS.filter((r) => r.key !== "messages" && (counts?.[r.key] ?? 0) > 0);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/50 px-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lift">
        <h2 className="text-lg font-bold text-ink">Delete all sample data?</h2>
        <p className="mt-2 text-sm text-ink-muted">This permanently removes:</p>

        {removable.length > 0 ? (
          <ul className="mt-3 space-y-1.5">
            {removable.map((row) => (
              <li key={row.key} className="flex justify-between text-sm">
                <span className="text-ink-soft">{row.label}</span>
                <span className="font-semibold tabular-nums text-ink">{counts?.[row.key]}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-ink-muted">There is no sample data to remove.</p>
        )}

        <p className="mt-4 rounded-xl bg-canvas px-3.5 py-2.5 text-xs text-ink-muted">
          Your real patients, appointments and conversations are never affected. Your integrations,
          agents and settings are untouched.
        </p>

        <div className="mt-5 flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="flex-1 rounded-full border border-sand-300 px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-ink disabled:opacity-50">
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-danger px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-danger/90 disabled:opacity-50">
            {busy && <Loader2Icon className="h-4 w-4 animate-spin" />}
            Delete everything
          </button>
        </div>
      </div>
    </div>
  );
}