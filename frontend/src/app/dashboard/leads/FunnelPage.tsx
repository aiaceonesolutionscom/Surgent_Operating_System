import React, { useEffect, useMemo, useState } from "react";
import {
  TrendingUpIcon,
  XCircleIcon,
  UsersIcon,
  UserCheckIcon,
  FlameIcon,
  SearchIcon,
  InboxIcon,
  PercentIcon
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { KpiCard } from "../components/KpiCard";
import { EmptyState } from "../components/EmptyState";
import { usePlan } from "../plan/PlanContext";
import { getFunnelSummary, type FunnelStageCount } from "../../../api/entities";
import { usePatients } from "../patients/usePatients";
import { FunnelStageBadge } from "./FunnelStageBadge";
import type { Patient } from "../patients/types";

// The forward-progression pipeline. "lost" is a dead-end branch, not a step
// forward, so it's reported separately instead of distorting the funnel's
// decreasing shape.
const STAGE_ORDER = [
  "inquiry",
  "contacted",
  "consult_scheduled",
  "consult_completed",
  "treatment_planned",
  "patient"
] as const;

const STAGE_LABEL: Record<Patient["lifecycleStage"], string> = {
  inquiry: "New inquiry",
  contacted: "Contacted",
  consult_scheduled: "Consult booked",
  consult_completed: "Consult done",
  treatment_planned: "Plan agreed",
  patient: "Became a patient",
  lost: "Lost"
};

const STAGE_ACCENT = [
  "#2563EB",
  "#0EA5E9",
  "#06B6D4",
  "#14B8A6",
  "#0D9488",
  "#10B981"
];

type LeadRow = {
  patient: Patient;
  stage: Patient["lifecycleStage"];
  procedure: string;
  score: number;
  source: string;
};

function formatMoney(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0
  }).format(value);
}

function percent(part: number, whole: number): string {
  if (!whole) return "—";
  return `${Math.round((part / whole) * 100)}%`;
}

function scoreTone(score: number): string {
  if (score >= 70) return "bg-success/10 text-success";
  if (score >= 40) return "bg-warning/10 text-warning";
  return "bg-sand-100 text-ink-muted";
}

export function FunnelPage() {
  const { authedFetch } = usePlan();
  const { patients, loading: patientsLoading, refetch } = usePatients(authedFetch);
  const [summary, setSummary] = useState<FunnelStageCount[] | null>(null);
  const [summaryError, setSummaryError] = useState(false);
  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState<Patient["lifecycleStage"] | "all">("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!authedFetch) return;
      try {
        const data = await getFunnelSummary(authedFetch);
        if (!cancelled) {
          setSummary(data);
          setSummaryError(false);
        }
      } catch {
        if (!cancelled) setSummaryError(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch, patients]);

  const loading = patientsLoading && !patients.length;

  // Prefer the server's authoritative counts; fall back to counting the
  // patient list client-side so the page still works if the aggregate
  // endpoint is unavailable. Both come from real rows — no mock data.
  const counts = useMemo(() => {
    const fromServer: Record<string, number> = {};
    (summary ?? []).forEach((s) => {
      fromServer[s.stage] = s.count;
    });
    const fromList: Record<string, number> = {};
    patients.forEach((p) => {
      fromList[p.lifecycleStage] = (fromList[p.lifecycleStage] ?? 0) + 1;
    });
    const result: Record<string, number> = {};
    STAGE_ORDER.forEach((stage) => {
      result[stage] = fromServer[stage] ?? fromList[stage] ?? 0;
    });
    result.lost = fromServer.lost ?? fromList.lost ?? 0;
    return result;
  }, [summary, patients]);

  const totalLeads = STAGE_ORDER.reduce((sum, stage) => sum + counts[stage], 0) + counts.lost;
  const converted = counts.patient;
  const openLeads = totalLeads - converted - counts.lost;
  const consultsBooked = counts.consult_scheduled + counts.consult_completed + counts.treatment_planned + converted;
  const consultShowRate = counts.inquiry + counts.contacted + consultsBooked;

  const leads: LeadRow[] = useMemo(
    () =>
      patients.map((patient) => ({
        patient,
        stage: patient.lifecycleStage,
        procedure:
          patient.qualification?.interestedProcedure ||
          patient.chiefComplaint ||
          (patient.procedures.length ? patient.procedures.join(", ") : ""),
        score: patient.qualification?.score ?? 0,
        source: patient.source || patient.qualification?.urgency || "Direct"
      })),
    [patients]
  );

  const visibleLeads = useMemo(() => {
    const q = query.trim().toLowerCase();
    return leads
      .filter((row) => (stageFilter === "all" ? true : row.stage === stageFilter))
      .filter((row) => {
        if (!q) return true;
        return (
          row.patient.name.toLowerCase().includes(q) ||
          row.procedure.toLowerCase().includes(q) ||
          row.source.toLowerCase().includes(q) ||
          (row.patient.phone ?? "").includes(q)
        );
      })
      .sort((a, b) => b.score - a.score);
  }, [leads, query, stageFilter]);

  const topProcedures = useMemo(() => {
    const tally = new Map<string, number>();
    leads.forEach((row) => {
      const key = row.procedure.trim() || "Not specified yet";
      tally.set(key, (tally.get(key) ?? 0) + 1);
    });
    return [...tally.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [leads]);

  const sourceSplit = useMemo(() => {
    const tally = new Map<string, number>();
    leads.forEach((row) => tally.set(row.source, (tally.get(row.source) ?? 0) + 1));
    return [...tally.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
  }, [leads]);

  if (loading) {
    return (
      <>
        <PageHeader
          title="Leads & Conversion Funnel"
          subtitle="Every enquiry from first contact through to a booked procedure."
        />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <KpiCard key={i} icon={UsersIcon} label="Loading" value="—" loading />
          ))}
        </div>
        <div className="mt-6 h-72 animate-pulse rounded-3xl border border-sand-200 bg-white/60" />
      </>
    );
  }

  if (totalLeads === 0) {
    return (
      <>
        <PageHeader
          title="Leads & Conversion Funnel"
          subtitle="Every enquiry from first contact through to a booked procedure."
        />
        <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState
            illustration="illustrated"
            icon={TrendingUpIcon}
            title="No leads in the funnel yet"
            body="As enquiries come in from your website, Instagram, WhatsApp or phone, they'll appear here automatically with their stage, score and interested procedure."
          />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Leads & Conversion Funnel"
        subtitle="Every enquiry from first contact through to a booked procedure."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          icon={UsersIcon}
          label="Total leads"
          value={totalLeads.toLocaleString()}
          color="#2563EB"
          trendLabel="Across every stage"
        />
        <KpiCard
          icon={FlameIcon}
          label="Open pipeline"
          value={openLeads.toLocaleString()}
          color="#EA580C"
          trendLabel="Still in progress"
        />
        <KpiCard
          icon={UserCheckIcon}
          label="Converted"
          value={converted.toLocaleString()}
          color="#10B981"
          trendLabel={`${percent(converted, totalLeads)} of all leads`}
        />
        <KpiCard
          icon={XCircleIcon}
          label="Lost"
          value={counts.lost.toLocaleString()}
          color="#DC2626"
          trendLabel={`${percent(counts.lost, totalLeads)} closed as lost`}
        />
      </div>

      {summaryError && (
        <p className="mt-4 rounded-2xl bg-warning/10 px-4 py-3 text-xs font-medium text-ink-soft">
          Live funnel totals are unavailable right now — the numbers below are counted from your patient list.
        </p>
      )}

      <div className="mt-6 grid gap-4 xl:grid-cols-[1.6fr,1fr]">
        {/* Funnel */}
        <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between">
            <p className="text-sm font-bold text-ink">Conversion funnel</p>
            <p className="text-xs text-ink-muted">{summaryError ? "Counted from patient list" : "Live totals"}</p>
          </div>

          <div className="mt-6 space-y-1">
            {STAGE_ORDER.map((stage, i) => {
              const count = counts[stage];
              const width = totalLeads ? (count / totalLeads) * 100 : 0;
              const prevCount = i === 0 ? totalLeads - counts.lost : counts[STAGE_ORDER[i - 1]];
              return (
                <div key={stage}>
                  {i > 0 && (
                    <div className="flex items-center gap-2 py-1.5 pl-1 text-[11px] font-medium text-ink-muted">
                      <span className="h-px w-6 bg-sand-200" />
                      {percent(count, prevCount)} carried over · {prevCount - count} dropped off
                    </div>
                  )}
                  <div className="rounded-2xl px-3 py-2.5 transition-colors hover:bg-sand-100/60">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="text-sm font-semibold text-ink">{STAGE_LABEL[stage]}</span>
                      <span className="font-mono text-sm font-semibold tabular-nums text-ink">
                        {count.toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-sand-100">
                      <div
                        className="h-full rounded-full transition-all duration-700 ease-out"
                        style={{ width: `${Math.max(width, count > 0 ? 3 : 0)}%`, backgroundColor: STAGE_ACCENT[i] }}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-5 flex items-center gap-2 border-t border-sand-100 pt-4 text-xs text-ink-muted">
            <XCircleIcon className="h-4 w-4 text-danger" />
            <span>
              <span className="font-semibold text-danger">{counts.lost.toLocaleString()}</span> lost — set from a
              patient's stage dropdown with a reason
            </span>
          </div>
        </div>

        {/* Side stats */}
        <div className="space-y-4">
          <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
            <div className="flex items-center gap-2 text-sm font-bold text-ink">
              <PercentIcon className="h-4 w-4 text-teal-600" /> Conversion rates
            </div>
            <dl className="mt-4 space-y-3 text-sm">
              <RateRow label="Inquiry → consult booked" value={percent(consultsBooked, consultShowRate)} />
              <RateRow label="Consult done → plan agreed" value={percent(counts.treatment_planned + converted, counts.consult_completed + counts.treatment_planned + converted)} />
              <RateRow label="Lead → patient" value={percent(converted, totalLeads)} />
              <RateRow label="Lead → lost" value={percent(counts.lost, totalLeads)} />
            </dl>
          </div>

          <Breakdown
            title="Most requested procedures"
            icon={FlameIcon}
            emptyLabel="No procedure data captured yet."
            rows={topProcedures}
          />

          <Breakdown title="Where leads come from" icon={InboxIcon} emptyLabel="No source data yet." rows={sourceSplit} />
        </div>
      </div>

      {/* Lead table */}
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-200 p-5">
          <div>
            <p className="text-sm font-bold text-ink">All leads</p>
            <p className="mt-0.5 text-xs text-ink-muted">
              {visibleLeads.length} of {leads.length} shown — change a stage inline to move a lead along
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search name, procedure, source…"
                className="w-64 rounded-xl border border-sand-200 bg-canvas py-2 pl-9 pr-3 text-sm text-ink outline-none focus:border-teal-400 focus:bg-white"
              />
            </div>
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value as Patient["lifecycleStage"] | "all")}
              className="rounded-xl border border-sand-200 bg-canvas px-3 py-2 text-sm font-medium text-ink outline-none focus:border-teal-400 focus:bg-white"
            >
              <option value="all">All stages</option>
              {[...STAGE_ORDER, "lost" as const].map((stage) => (
                <option key={stage} value={stage}>
                  {STAGE_LABEL[stage]} ({counts[stage] ?? 0})
                </option>
              ))}
            </select>
          </div>
        </div>

        {visibleLeads.length === 0 ? (
          <EmptyState
            icon={SearchIcon}
            title="No leads match that filter"
            body="Try a different stage or clear the search box."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="border-b border-sand-200 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3">Lead</th>
                  <th className="px-5 py-3">Interested in</th>
                  <th className="px-5 py-3">Source</th>
                  <th className="px-5 py-3">Score</th>
                  <th className="px-5 py-3">Stage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-100">
                {visibleLeads.map((row) => (
                  <tr key={row.patient.id} className="transition-colors hover:bg-sand-100/40">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-600/10 text-xs font-bold text-teal-600">
                          {row.patient.initial}
                        </span>
                        <div>
                          <p className="font-semibold text-ink">{row.patient.name}</p>
                          <p className="text-xs text-ink-muted">{row.patient.phone || row.patient.email || "—"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-ink-soft">
                      {row.procedure ? (
                        <span className="line-clamp-1">{row.procedure}</span>
                      ) : (
                        <span className="text-ink-muted">Not captured</span>
                      )}
                      {row.stage === "lost" && row.patient.lostReason && (
                        <p className="mt-0.5 text-xs text-danger">Lost: {row.patient.lostReason}</p>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-ink-soft">{row.source}</td>
                    <td className="px-5 py-3.5">
                      {row.score > 0 ? (
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-bold ${scoreTone(row.score)}`}>
                          {row.score}
                        </span>
                      ) : (
                        <span className="text-xs text-ink-muted">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <FunnelStageBadge
                        patientId={row.patient.id}
                        stage={row.stage}
                        lostReason={row.patient.lostReason}
                        onUpdated={() => {
                          void refetch();
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <p className="mt-4 text-xs text-ink-muted">
        Stock value shown on the inventory page is separate from this funnel — the two pages never share
        placeholder data. Estimated pipeline at typical consult value:{" "}
        <span className="font-semibold text-ink">{formatMoney(openLeads * 2500)}</span> (assumption: {formatMoney(2500)} per
        booked treatment).
      </p>
    </>
  );
}

function RateRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-ink-soft">{label}</dt>
      <dd className="font-mono font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

function Breakdown({
  title,
  icon: Icon,
  rows,
  emptyLabel
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  rows: [string, number][];
  emptyLabel: string;
}) {
  const max = Math.max(...rows.map(([, n]) => n), 1);
  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <Icon className="h-4 w-4 text-teal-600" /> {title}
      </div>
      {rows.length === 0 ? (
        <p className="mt-3 text-xs text-ink-muted">{emptyLabel}</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map(([label, count]) => (
            <li key={label}>
              <div className="flex items-baseline justify-between gap-3 text-sm">
                <span className="truncate text-ink-soft">{label}</span>
                <span className="font-mono text-xs font-semibold tabular-nums text-ink">{count}</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sand-100">
                <div
                  className="h-full rounded-full bg-teal-600/70 transition-all duration-700"
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
