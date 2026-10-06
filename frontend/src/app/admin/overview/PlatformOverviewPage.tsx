import { useEffect, useState } from "react";
import {
  Building2Icon,
  DollarSignIcon,
  ActivityIcon,
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
import { PlatformPulsePanel } from "./PlatformPulsePanel";

function money(n: number) {
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatAvgLatency(ms: number | null) {
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

function formatTime(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// Compact single stat tile — the overview's density comes from these: small
// label over a tabular value, in a bordered card that sits flush in a grid.
function StatTile({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "good" | "warn" | "bad";
}) {
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

// The ACTIVITY feed groups the newest audit events by clinic — same shape as
// the design (Clinic A → its recent actions), newest group first.
function groupActivity(events: ActivityEvent[], maxGroups = 3, perGroup = 4) {
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

export function PlatformOverviewPage() {
  const [summary, setSummary] = useState<AdminSummaryResponse | null>(null);
  const [metrics, setMetrics] = useState<PlatformMetricsResponse | null>(null);
  const [activity, setActivity] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    platformMetrics()
      .then((m) => {
        if (!cancelled) setMetrics(m);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load platform metrics.");
      });
    getAdminActivity(24)
      .then((a) => {
        if (!cancelled) setActivity(a);
      })
      .catch(() => {
        if (!cancelled) setActivity([]);
      });
    getAdminSummary()
      .then((s) => {
        if (!cancelled) setSummary(s);
      })
      .catch(() => {
        if (!cancelled) setError("Couldn't load platform summary.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error && !summary && !metrics) {
    return (
      <div>
        <SectionLabel>Super Admin</SectionLabel>
        <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">Platform overview</h1>
        <p className="mt-6 text-sm text-danger">{error}</p>
      </div>
    );
  }

  const groups = activity ? groupActivity(activity) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <SectionLabel>Super Admin</SectionLabel>
        <h1 className="mt-1.5 font-display text-[24px] font-600 tracking-tight text-ink sm:text-[28px]">
          Platform overview
        </h1>
        <p className="mt-1 text-[13px] text-ink-muted">
          Every clinic, its revenue and running cost, and live platform health.
        </p>
        {error && <p className="mt-2 text-sm text-danger">{error}</p>}
      </div>

      {/* Top strip: clinics / users / patients / appointments / AI — one dense row */}
      {metrics && (
        <>
          <section>
            <SectionLabel icon={Building2Icon}>Platform</SectionLabel>
            <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-6">
              <StatTile
                label="Clinics"
                value={String(metrics.clinics.total)}
                sub={`${metrics.clinics.active} active · ${metrics.clinics.trial} trial · ${metrics.clinics.suspended} suspended`}
              />
              <StatTile label="Users" value={String(metrics.total_users)} sub="staff accounts" />
              <StatTile label="Patients" value={String(metrics.total_patients)} sub="all clinics" />
              <StatTile label="Appointments" value={String(metrics.appointments_this_month)} sub="this month" />
              <StatTile label="AI runs" value={String(metrics.ai.runs_total)} sub={`avg ${formatAvgLatency(metrics.ai.avg_latency_ms)}`} />
              <StatTile label="AI cost" value={money(metrics.ai.estimated_cost_total)} sub="estimated" tone="warn" />
            </div>
          </section>

          {/* Subscriptions — one compact panel, five inline stats */}
          <section>
            <SectionLabel icon={DollarSignIcon}>Subscriptions</SectionLabel>
            <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
              <StatTile label="Active" value={String(metrics.subscriptions.active)} tone="good" />
              <StatTile label="Trial" value={String(metrics.subscriptions.trial)} tone="warn" />
              <StatTile label="Cancelling" value={String(metrics.subscriptions.cancelling)} tone="warn" />
              <StatTile label="Past due" value={String(metrics.subscriptions.past_due)} tone="bad" />
              <StatTile label="Cancelled" value={String(metrics.subscriptions.cancelled)} />
            </div>
          </section>
        </>
      )}

      {/* Revenue vs cost + plan mix — side by side */}
      {summary && (
        <section className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-sand-200 bg-white p-5 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">
            <div className="flex items-center justify-between">
              <p className="text-sm font-bold text-ink">Revenue vs running cost</p>
              <p className="font-display text-lg font-600 text-success">{summary.margin_percent.toFixed(1)}% margin</p>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3">
              <StatTile label="MRR (est.)" value={money(summary.total_estimated_mrr)} tone="good" />
              <StatTile label="Cost (est.)" value={money(summary.total_estimated_cost)} tone="bad" />
              <StatTile label="Margin" value={money(summary.total_estimated_margin)} />
            </div>
            <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-sand-100">
              <div
                className="h-full rounded-full bg-accent-500"
                style={{
                  width: `${summary.total_estimated_mrr ? Math.min(100, (summary.total_estimated_cost / summary.total_estimated_mrr) * 100) : 0}%`,
                }} />
            </div>
            <p className="mt-2 text-[11px] text-ink-muted">{summary.assumption_note}</p>
          </div>
          <div className="rounded-2xl border border-sand-200 bg-white p-5 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">
            <p className="text-sm font-bold text-ink">Plan mix</p>
            <PlatformPulsePanel planDistribution={summary.plan_distribution} />
          </div>
        </section>
      )}

      {/* SYSTEM + ACTIVITY side by side — fits one screen instead of two scrolls */}
      <section className="grid gap-4 lg:grid-cols-2">
        {metrics && (
          <div className="rounded-2xl border border-sand-200 bg-white p-5 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">
            <div className="flex items-center gap-1.5">
              <ServerIcon className="h-3.5 w-3.5 text-ink-muted" />
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-500">System</p>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2.5">
              <StatTile label="API uptime" value={formatUptime(metrics.system.uptime_seconds)} />
              <StatTile
                label="Error rate"
                value={`${metrics.system.error_rate_percent.toFixed(2)}%`}
                tone={metrics.system.error_rate_percent > 1 ? "bad" : "default"}
              />
              <StatTile
                label="DB health"
                value={
                  metrics.system.db_health_ms == null
                    ? "—"
                    : `${metrics.system.db_health_ms}ms`
                }
                sub={
                  metrics.system.db_health_ms == null
                    ? undefined
                    : metrics.system.db_health_ms < 150
                      ? "good"
                      : metrics.system.db_health_ms < 500
                        ? "slow"
                        : "poor"
                }
                tone={
                  metrics.system.db_health_ms == null
                    ? "default"
                    : metrics.system.db_health_ms < 150
                      ? "good"
                      : metrics.system.db_health_ms < 500
                        ? "warn"
                        : "bad"
                }
              />
              <StatTile label="Slow requests" value={String(metrics.system.slow_requests_total)} sub=">500ms since boot" />
            </div>
            <p className="mt-3 text-[11px] text-ink-muted">{metrics.system.scope_note}</p>
          </div>
        )}

        <div className="rounded-2xl border border-sand-200 bg-white p-5 shadow-[0_2px_10px_rgba(15,23,42,0.04)]">
          <div className="flex items-center gap-1.5">
            <ActivityIcon className="h-3.5 w-3.5 text-ink-muted" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent-500">Activity</p>
          </div>
          {activity && groups.length === 0 && (
            <p className="mt-3 text-sm text-ink-muted">No audited events yet.</p>
          )}
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
                      <span className="shrink-0 text-[11px] text-ink-muted/60">{formatTime(ev.created_at)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
