import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeftIcon, ZapIcon, InboxIcon, UsersIcon, ScissorsIcon } from "lucide-react";
import { AGENT_CATEGORIES, AGENTS_BY_SLUG } from "../../../data/agents";
import { ComingSoon } from "../components/ComingSoon";
import { EmptyState } from "../components/EmptyState";
import { SessionsView } from "../sessions/SessionsView";
import { useSessions } from "../sessions/useSessions";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import { UpgradeRequired } from "../plan/UpgradeRequired";
import { minTierForCategory } from "../plan/plan";
import { usePatients } from "../patients/usePatients";
import { listAgentConfigs, type AgentConfigResponse } from "../../../api/entities";

// The consolidated 9-agent roster is real today — receptionist (WhatsApp + landing
// chat), appointment_reminder (reminders/rescheduling), lead_qualification,
// patient_intake, consultation_assistant (dictation/SOAP), post_op_recovery,
// marketing_retention (nurturing/feedback follow-up), finance_agent (this month's
// numbers), and main_agent (command center). Older session slugs (command_center,
// post_op_followup, lead_nurturing, …) still map onto these via data/agents/index.ts.
const LIVE_AGENT_SLUGS = new Set([
  "receptionist",
  "appointment_reminder",
  "lead_qualification",
  "patient_intake",
  "consultation_assistant",
  "post_op_recovery",
  "marketing_retention",
  "finance_agent",
  "main_agent"
]);

const AGENT_LOGOS: Record<string, string> = {
  receptionist: "/agent-logos/receptionist.png"
};

export function AgentDetailPage() {
  const { categoryId, agentSlug } = useParams<{ categoryId: string; agentSlug: string }>();
  const category = AGENT_CATEGORIES.find((c) => c.id === categoryId);
  const agent = agentSlug ? AGENTS_BY_SLUG[agentSlug] : undefined;
  const { allowsCategory, loading, authedFetch } = usePlan();
  const { patients } = usePatients(authedFetch);
  const { sessions, loading: sessionsLoading, error: sessionsError, refetch } = useSessions();
  const [enabledBySlug, setEnabledBySlug] = useState<Record<string, boolean> | null>(null);

  // Live status comes from the real agent-config rows (Owner toggles them on
  // the Agent settings screen), not a hardcoded roster — a config explicitly
  // switched off shows "Configured, not yet active" even for a shipped agent.
  useEffect(() => {
    let cancelled = false;
    if (!authedFetch) return;
    listAgentConfigs(authedFetch)
      .then((configs: AgentConfigResponse[]) => {
        if (cancelled) return;
        const map: Record<string, boolean> = {};
        for (const c of configs) map[c.agent_type] = c.enabled;
        setEnabledBySlug(map);
      })
      .catch(() => {
        if (!cancelled) setEnabledBySlug({});
      });
    return () => { cancelled = true; };
  }, [authedFetch]);

  if (!category || !agent || agent.categoryId !== categoryId) {
    return <ComingSoon icon={ZapIcon} title="Agent not found" body="This agent doesn't exist in this category." phase="—" />;
  }

  if (loading) return null;

  // Defense-in-depth for a hand-typed URL to a locked agent — the category
  // page already stops the normal click-through path.
  if (!allowsCategory(category.id)) {
    return <UpgradeRequired title={category.label} tagline={category.tagline} minTier={minTierForCategory(category.id) || "enterprise"} agents={category.agents} />;
  }

  const isLive = LIVE_AGENT_SLUGS.has(agent.slug) && (enabledBySlug === null || enabledBySlug[agent.slug] !== false);
  const agentSessions = sessions.filter((s) => s.agentSlug === agent.slug);
  const routedPatients = patients.filter((p) => p.assignedAgentSlug === agent.slug);

  return (
    <>
      <Link
        to={DASHBOARD_ROUTES.agentCategory(category.id)}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to {category.label}
      </Link>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
              {AGENT_LOGOS[agent.slug] ? (
                <img src={AGENT_LOGOS[agent.slug]} alt="" className="h-9 w-9 object-contain" />
              ) : (
                <agent.icon className="h-7 w-7" />
              )}
            </span>
            <div>
              <p className="text-lg font-bold text-ink">{agent.name}</p>
              <p className="mt-0.5 max-w-md text-sm text-ink-muted">{agent.desc}</p>
            </div>
          </div>
          <span
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${
            isLive ? "bg-success/10 text-success" : "bg-warning/10 text-warning"}`
            }>

            <span className={`h-1.5 w-1.5 rounded-full ${isLive ? "bg-success" : "bg-warning"}`} />
            {isLive ? "Live" : "Configured, not yet active"}
          </span>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl bg-sand-100 px-4 py-3">
            <p className="font-mono text-2xl font-bold tabular-nums text-ink">{agentSessions.length}</p>
            <p className="text-xs text-ink-muted">Sessions on record</p>
          </div>
          <div className="rounded-xl bg-sand-100 px-4 py-3">
            <p className="font-mono text-2xl font-bold tabular-nums text-ink">
              {agentSessions.filter((s) => s.status === "needs_attention").length}
            </p>
            <p className="text-xs text-ink-muted">Escalated to staff</p>
          </div>
          <div className="rounded-xl bg-sand-100 px-4 py-3">
            <p className="font-mono text-2xl font-bold tabular-nums text-ink">
              {agentSessions.filter((s) => s.status === "resolved").length}
            </p>
            <p className="text-xs text-ink-muted">Resolved</p>
          </div>
        </div>
      </div>

      <div className="mb-6 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="mb-4 flex items-center gap-2 text-sm font-bold text-ink">
          <UsersIcon className="h-4 w-4 text-teal-600" /> Patients routed here
        </div>
        {routedPatients.length === 0 ?
        <p className="text-sm text-ink-muted">No patients assigned to {agent.name} yet — added patients are routed here automatically based on what they describe.</p> :

        <div className="space-y-2.5">
            {routedPatients.map((p) =>
          <Link
            key={p.id}
            to={DASHBOARD_ROUTES.patientDetail(p.id)}
            className="flex items-start gap-3 rounded-xl bg-sand-100 px-4 py-3 transition-colors hover:bg-teal-600/8">

                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-sm font-bold text-ink-soft">
                  {p.initial}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-ink">{p.name}</p>
                    {p.needsSurgery &&
                <span className="flex items-center gap-1 rounded-full bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning">
                        <ScissorsIcon className="h-2.5 w-2.5" /> Surgery
                      </span>
                }
                  </div>
                  <p className="truncate text-xs text-ink-muted">{p.chiefComplaint || "No details provided."}</p>
                </div>
              </Link>
          )}
          </div>
        }
      </div>

      <p className="mb-3 text-sm font-bold text-ink">Sessions handled by {agent.name}</p>
      {sessionsLoading ?
      <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading sessions...</p>
        </div> :
      sessionsError ?
      <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{sessionsError}</p>
          <button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div> :
      agentSessions.length === 0 ?
      <div className="rounded-3xl border border-sand-200 bg-white">
          <EmptyState icon={InboxIcon} title="No sessions yet" body={`Once ${agent.name} handles a conversation, it'll show up here.`} />
        </div> :

      <SessionsView sessions={agentSessions} />
      }
    </>);

}
