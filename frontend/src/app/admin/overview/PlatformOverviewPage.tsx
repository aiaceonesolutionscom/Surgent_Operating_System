import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIcon,
  BotIcon,
  Building2Icon,
  DollarSignIcon,
  RefreshCwIcon,
  ServerIcon,
} from "lucide-react";
import {
  getAdminSummary,
  platformMetrics,
  getAdminActivity,
  type AdminSummaryResponse,
  type PlatformMetricsResponse,
  type ActivityEvent,
} from "../../../api/admin";

// Everything on this page is read from the API on every refresh — no number
// here is hardcoded. Counts come from the clinic tables; AI and API-health
// figures come from persisted telemetry (llm_calls / system_metric_buckets),
// so they survive an API restart and cover every instance.
const REFRESH_MS = 30_000;

const TIER_LABEL: Record<string, string> = { solo: "Solo", practice: "Practice", enterprise: "Enterprise", custom: "Custom" };

function count(n: number) {
  return n.toLocaleString();
}

function money(n: number) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

// AI spend is often a few cents — show cents until it is worth rounding.
function moneyPrecise(n: number) {
  return n >= 100 ? money(n) : `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function compact(n: number) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function latency(ms: number | null) {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatUptime(seconds: number) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

// audit action "patient.view" → "Patient viewed" — display only; unknown
// actions still render readably via the generic fallback.
function formatAction(action: string) {
  const [resource, verb] = action.split(".");
  const nice = (s: string) => s.replace(/_/g, " ");
  return verb ? `${nice(resource)} ${nice(verb)}` : nice(action);
}

function timeAgo(iso: string | number) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diffMs / 1000);
  if (secs < 10) return "just now";
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

type Tone = "default" | "good" | "warn" | "bad";

// Compact single stat tile — the overview's density comes from these: small
// label over a tabular value, in a bordered card that sits flush in a grid.
function StatTile({ label, value, sub, tone = "default" }: { label: string; value: string; sub?: string; tone?: Tone }) {
  const valueClass =
    tone === "good" ? "text-success" : tone === "warn" ? "text-warning" : tone === "bad" ? "text-danger" : "text-ink";
  return (
    <div className="rounded-xl border border-sand-200 bg-white px-4 py-3 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-muted">{label}</p>
      <p className={`mt-0.5 font-display text-[20px] font-600 tabular-nums leading-tight ${valueClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] text-ink-muted">{sub}</p>}
    </div>
  );
}

function SectionLabel({ icon: Icon, children }: { icon?: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5">
      {Icon && <Icon className="h-3.5 w-3.5 text-ink-muted" />}
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-500">{children}</p>
    </div>
  );
}

function Panel({ children }: { children: React.ReactNode }) {
  return <div className="rounded-2xl border border-sand-200 bg-white p-5 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">{children}</div>;
}

// The ACTIVITY feed groups the newest audit events by clinic — same shape as
// the design (Clinic A → its recent actions), newest group first.
function groupActivity(events: ActivityEvent[], maxGroups = 4, perGroup = 4) {
  const groups: { practice: string; events: ActivityEvent[] }[] = [];
  for (const ev of events) {
    const key = ev.practice_name ?? "Platform-wide";
    let group = groups.find((g) => g.practice === key);
    if (!group) {
      if (groups.length >= maxGroups) break;
      group = { practice: key, events: [] };
      groups.push(group);
    }
    if (group.events.length < perGroup) group.events.push(ev);
  }
  return groups;
}

function PlanMix({ distribution }: { distribution: Record<string, number> }) {
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, n]) => sum + n, 0);
  if (entries.length === 0) return <p className="mt-3 text-sm text-ink-muted">No clinics yet.</p>;
  return (
    <ul className="mt-3 space-y-2.5">
      {entries.map(([tier, n]) => (
        <li key={tier}>
          <div className="flex items-baseline justify-between text-[13px]">
            <span className="font-medium text-ink">{TIER_LABEL[tier] ?? tier}</span>
            <span className="tabular-nums text-ink-muted">
              {count(n)} clinic{n === 1 ? "" : "s"}
            </span>
          </div>
          <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-sand-100">
            <div className="h-full rounded-full bg-accent-500" style={{ width: `${total ? (n / total) * 100 : 0}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function PlatformOverviewPage() {
  const [summary, setSummary] = useState<AdminSummaryResponse | null>(null);
  const [metrics, setMetrics] = useState<PlatformMetricsResponse | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [, setTick] = useState(0);
  const alive = useRef(true);

  const load = useCallback(async () => {
    setRefreshing(true);
    const [m, s, a] = await Promise.allSettled([platformMetrics(), getAdminSummary(), getAdminActivity(40)]);
    if (!alive.current) return;
    // A failed refresh keeps the last good numbers on screen and says so,
    // rather than blanking the page or showing zeros.
    if (m.status === "fulfilled") setMetrics(m.value);
    if (s.status === "fulfilled") setSummary(s.value);
    if (a.status === "fulfilled") setActivity(a.value);
    else setActivity((prev) => prev ?? []);
    const failed = [m, s].some((r) => r.status === "rejected");
    setError(failed ? "Couldn't refresh some platform figures — showing the last values loaded." : null);
    if (m.status === "fulfilled" || s.status === "fulfilled") setUpdatedAt(Date.now());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    alive.current = true;
    void load();
    const refresh = window.setInterval(() => void load(), REFRESH_MS);
    const clock = window.setInterval(() => setTick((t) => t + 1), 5_000); // keeps "updated Xs ago" honest
    return () => {
      alive.current = false;
      window.clearInterval(refresh);
      window.clearInterval(clock);
    };
  }, [load]);

  const groups = activity ? groupActivity(activity) : [];
  const ai = metrics?.ai;
  const sys = metrics?.system;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <SectionLabel>Super Admin</SectionLabel>
          <h1 className="mt-1.5 font-display text-[24px] font-600 tracking-tight text-ink sm:text-[28px]">Platform overview</h1>
          <p className="mt-1 text-[13px] text-ink-muted">Every clinic, its revenue and AI spend, and live platform health.</p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={refreshing}
          className="flex items-center gap-1.5 rounded-lg border border-sand-200 bg-white px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-accent-500/50 hover:text-accent-700 disabled:opacity-60">
          <span className={`h-1.5 w-1.5 rounded-full ${error ? "bg-warning" : "bg-success"}`} />
          {updatedAt ? `Live · updated ${timeAgo(updatedAt)}` : "Loading…"}
          <RefreshCwIcon className={`h-3 w-3 ${refreshing ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}
      {!metrics && !summary && !error && <p className="text-sm text-ink-muted">Loading platform figures…</p>}

      {/* CLINICS / USERS / PATIENTS / APPOINTMENTS */}
      {metrics && (
        <section>
          <SectionLabel icon={Building2Icon}>Platform</SectionLabel>
          <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-8">
            <StatTile label="Clinics" value={count(metrics.clinics.total)} sub="total" />
            <StatTile label="Active" value={count(metrics.clinics.active)} tone="good" />
            <StatTile label="Trial" value={count(metrics.clinics.trial)} tone="warn" />
            <StatTile label="Suspended" value={count(metrics.clinics.suspended)} tone={metrics.clinics.suspended > 0 ? "bad" : "default"} />
            <StatTile
              label="Not subscribed"
              value={count(metrics.clinics.unsubscribed)}
              sub="no live plan"
              tone={metrics.clinics.unsubscribed > 0 ? "warn" : "default"}
            />
            <StatTile label="Users" value={count(metrics.total_users)} sub="staff accounts" />
            <StatTile label="Patients" value={count(metrics.total_patients)} sub="all clinics" />
            <StatTile label="Appointments" value={count(metrics.appointments_this_month)} sub="this month" />
          </div>
        </section>
      )}

      {/* AI */}
      {ai && (
        <section>
          <SectionLabel icon={BotIcon}>AI</SectionLabel>
          <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
            <StatTile label="Runs (24h)" value={count(ai.calls_24h)} sub={`${count(ai.calls_month)} this month`} />
            <StatTile
              label="Avg latency"
              value={latency(ai.avg_latency_ms_24h)}
              sub={ai.p95_latency_ms_24h != null ? `p95 ${latency(ai.p95_latency_ms_24h)} · 24h` : "24h"}
            />
            <StatTile label="Cost (month)" value={moneyPrecise(ai.cost_month_usd)} sub="list price" tone="warn" />
            <StatTile label="Tokens (month)" value={compact(ai.tokens_month)} />
            <StatTile
              label="Failed calls"
              value={`${ai.error_rate_percent_24h.toFixed(1)}%`}
              sub="24h, incl. rate limits"
              tone={ai.error_rate_percent_24h > 5 ? "bad" : "default"}
            />
            <StatTile label="Agent actions" value={count(ai.agent_actions_30d)} sub="last 30 days" />
          </div>
          {ai.top_sources.length > 0 && (
            <p className="mt-2 text-[11px] text-ink-muted">
              Biggest AI spend this month:{" "}
              {ai.top_sources.slice(0, 4).map((s, i) => (
                <span key={s.source}>
                  {i > 0 && " · "}
                  <span className="font-medium text-ink-soft">{s.source.replace(/_/g, " ")}</span> {moneyPrecise(s.cost_usd)} ({count(s.calls)} runs)
                </span>
              ))}
            </p>
          )}
        </section>
      )}

      {/* SUBSCRIPTIONS */}
      {metrics && (
        <section>
          <SectionLabel icon={DollarSignIcon}>Subscriptions</SectionLabel>
          <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            <StatTile label="Active" value={count(metrics.subscriptions.active)} tone="good" />
            <StatTile label="Trial" value={count(metrics.subscriptions.trial)} tone="warn" />
            <StatTile label="Past due" value={count(metrics.subscriptions.past_due)} tone={metrics.subscriptions.past_due > 0 ? "bad" : "default"} />
            <StatTile label="Cancelling" value={count(metrics.subscriptions.cancelling)} tone="warn" />
            <StatTile label="Cancelled" value={count(metrics.subscriptions.cancelled)} />
          </div>
        </section>
      )}

      {/* Revenue vs AI spend + plan mix */}
      {summary && (
        <section className="grid gap-4 lg:grid-cols-2">
          <Panel>
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold text-ink">Revenue vs AI spend</p>
              <p className={`font-display text-lg font-600 ${summary.margin >= 0 ? "text-success" : "text-danger"}`}>
                {summary.mrr > 0 ? `${summary.margin_percent.toFixed(1)}% margin` : "No paying clinics yet"}
              </p>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="MRR" value={money(summary.mrr)} sub="active plans" tone="good" />
              <StatTile label="AI cost" value={moneyPrecise(summary.ai_cost_month)} sub="this month" tone="bad" />
              <StatTile label="Margin" value={money(summary.margin)} />
              <StatTile label="In trial" value={money(summary.trial_pipeline_mrr)} sub="not yet billing" />
            </div>
            <p className="mt-3 text-[11px] text-ink-muted">{summary.cost_basis}</p>
          </Panel>
          <Panel>
            <p className="text-sm font-bold text-ink">Plan mix</p>
            <PlanMix distribution={summary.plan_distribution} />
          </Panel>
        </section>
      )}

      {/* SYSTEM + ACTIVITY side by side — fits one screen instead of two scrolls */}
      <section className="grid gap-4 lg:grid-cols-2">
        {sys && (
          <Panel>
            <div className="flex items-center gap-1.5">
              <ServerIcon className="h-3.5 w-3.5 text-ink-muted" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-500">System</p>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2.5">
              <StatTile
                label="API uptime"
                value={formatUptime(sys.uptime_seconds)}
                sub={sys.restarts_24h > 0 ? `${sys.restarts_24h} restart${sys.restarts_24h === 1 ? "" : "s"} in 24h` : "no restarts in 24h"}
                tone={sys.restarts_24h > 2 ? "warn" : "default"}
              />
              <StatTile
                label="Error rate"
                value={`${sys.error_rate_percent.toFixed(2)}%`}
                sub={`${count(sys.requests_24h)} requests · 24h`}
                tone={sys.error_rate_percent > 1 ? "bad" : "good"}
              />
              <StatTile
                label="DB health"
                value={sys.db_health_ms == null ? "—" : `${sys.db_health_ms}ms`}
                sub={sys.db_health_ms == null ? undefined : sys.db_health_ms < 150 ? "healthy" : sys.db_health_ms < 500 ? "slow" : "poor"}
                tone={sys.db_health_ms == null ? "default" : sys.db_health_ms < 150 ? "good" : sys.db_health_ms < 500 ? "warn" : "bad"}
              />
              <StatTile
                label="Slow queries"
                value={count(sys.slow_queries_24h)}
                sub={`${count(sys.slow_requests_24h)} slow requests · avg ${latency(sys.avg_response_ms_24h)}`}
                tone={sys.slow_queries_24h > 20 ? "warn" : "default"}
              />
            </div>
            {sys.top_slow_queries.length > 0 && (
              <div className="mt-3">
                <p className="text-[11px] font-semibold text-ink-soft">Slowest queries (24h)</p>
                <ul className="mt-1 space-y-1">
                  {sys.top_slow_queries.slice(0, 3).map((q) => (
                    <li key={q.statement} className="rounded-lg bg-sand-50 px-2.5 py-1.5">
                      <p className="truncate font-mono text-[11px] text-ink-soft" title={q.statement}>
                        {q.statement}
                      </p>
                      <p className="text-[10px] text-ink-muted">
                        {count(q.count)}× · max {q.max_ms}ms · avg {q.avg_ms}ms
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-3 text-[11px] text-ink-muted">{sys.scope_note}</p>
          </Panel>
        )}

        <Panel>
          <div className="flex items-center gap-1.5">
            <ActivityIcon className="h-3.5 w-3.5 text-ink-muted" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-500">Activity</p>
          </div>
          {activity && groups.length === 0 && <p className="mt-3 text-sm text-ink-muted">No audited events yet.</p>}
          <div className="mt-3 space-y-3">
            {groups.map((group) => (
              <div key={group.practice}>
                <p className="text-xs font-bold text-ink">{group.practice}</p>
                <ul className="mt-1 space-y-0.5">
                  {group.events.map((ev) => (
                    <li key={ev.id} className="flex items-baseline justify-between gap-2 text-[13px] text-ink-muted">
                      <span className="truncate">
                        {formatAction(ev.action)}
                        {ev.actor_email && <span className="text-ink-muted/60"> · {ev.actor_email}</span>}
                      </span>
                      <span className="shrink-0 text-[11px] text-ink-muted/60">{timeAgo(ev.created_at)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Panel>
      </section>
    </div>
  );
}
