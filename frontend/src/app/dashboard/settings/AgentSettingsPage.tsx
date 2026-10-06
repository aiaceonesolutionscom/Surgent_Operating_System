import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LockIcon, DollarSignIcon } from "lucide-react";
import { AGENT_CATEGORIES } from "../../../data/agents";
import { PageHeader } from "../components/PageHeader";
import { Toggle } from "../components/Toggle";
import { useAgentSettings } from "./useAgentSettings";
import type { AgentTone, EscalationSensitivity } from "./types";
import { usePlan } from "../plan/PlanContext";
import { minTierForCategory, planFor } from "../plan/plan";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { useAgentCosting } from "./useAgentCosting";
import { listConversations } from "../../../api/entities";
import { MarketingOffersEditor } from "./MarketingOffersEditor";

const TONE_OPTIONS: { value: AgentTone; label: string }[] = [
{ value: "professional", label: "Professional" },
{ value: "warm", label: "Warm & friendly" },
{ value: "concise", label: "Concise" }];


const SENSITIVITY_OPTIONS: { value: EscalationSensitivity; label: string }[] = [
{ value: "low", label: "Low — escalate only clear emergencies" },
{ value: "medium", label: "Medium — balanced" },
{ value: "high", label: "High — escalate anything uncertain" }];


export function AgentSettingsPage() {
  const { getSetting, updateSetting } = useAgentSettings();
  const { allowsCategory, authedFetch } = usePlan();
  const { costFor } = useAgentCosting();
  const [sessionsByAgent, setSessionsByAgent] = useState<Record<string, number>>({});

  useEffect(() => {
    if (!authedFetch) return;
    let cancelled = false;
    listConversations(authedFetch, { limit: 100 })
      .then((rows) => {
        if (cancelled) return;
        const counts: Record<string, number> = {};
        for (const row of rows) counts[row.agent_type] = (counts[row.agent_type] ?? 0) + 1;
        setSessionsByAgent(counts);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  return (
    <>
      <PageHeader
        title="Agent settings"
        subtitle="Turn agents on or off for your practice, and tune their tone and escalation sensitivity." />


      <div className="space-y-6">
        {AGENT_CATEGORIES.map((category) => {
          const locked = !allowsCategory(category.id);
          const minTier = locked ? minTierForCategory(category.id) : null;
          const plan = minTier ? planFor(minTier) : null;

          return (
            <div key={category.id} className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
              <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
                <p className={`text-sm font-bold ${locked ? "text-ink-muted" : "text-ink"}`}>{category.label}</p>
                {locked && plan &&
                <Link
                  to={DASHBOARD_ROUTES.settingsBilling}
                  className="flex items-center gap-1.5 rounded-full bg-sand-100 px-3 py-1 text-xs font-semibold text-ink-muted transition-colors hover:bg-teal-600/8 hover:text-teal-600">

                    <LockIcon className="h-3 w-3" /> Included in {plan.name} — upgrade
                  </Link>
                }
              </div>
              <div className={`divide-y divide-sand-200/70 ${locked ? "opacity-50" : ""}`}>
                {category.agents.map((agent) => {
                  const setting = getSetting(agent.slug);
                  const enabled = setting.enabled && !locked;
                  const perSession = costFor(agent.slug);
                  const sessions = sessionsByAgent[agent.slug] ?? 0;
                  const monthlyCost = perSession * sessions;

                  return (
                    <div key={agent.slug} className="flex flex-wrap items-center gap-4 px-5 py-4">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-600/8 text-teal-600">
                        <agent.icon className="h-5 w-5" />
                      </span>
                      <div className="min-w-[160px] flex-1">
                        <p className="text-sm font-semibold text-ink">{agent.name}</p>
                        <p className="text-xs text-ink-muted">{agent.desc}</p>
                      </div>

                      <div className="flex items-center gap-1.5 rounded-lg bg-sand-100 px-2.5 py-1.5" title={`$${perSession.toFixed(2)} per session × ${sessions} sessions this month`}>
                        <DollarSignIcon className="h-3.5 w-3.5 text-ink-muted" />
                        <div className="leading-tight">
                          <p className="font-mono text-xs font-semibold tabular-nums text-ink">${monthlyCost.toFixed(2)}<span className="font-sans font-normal text-ink-muted">/mo</span></p>
                          <p className="font-mono text-[10px] tabular-nums text-ink-muted">${perSession.toFixed(2)}/session</p>
                        </div>
                      </div>

                      <select
                        value={setting.tone}
                        onChange={(e) => updateSetting(agent.slug, { tone: e.target.value as AgentTone })}
                        disabled={!setting.enabled || locked}
                        className="rounded-lg border border-sand-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-soft disabled:opacity-40">

                        {TONE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>

                      <select
                        value={setting.escalationSensitivity}
                        onChange={(e) => updateSetting(agent.slug, { escalationSensitivity: e.target.value as EscalationSensitivity })}
                        disabled={!setting.enabled || locked}
                        className="rounded-lg border border-sand-200 bg-white px-2.5 py-1.5 text-xs font-medium text-ink-soft disabled:opacity-40">

                        {SENSITIVITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>

                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-semibold ${enabled ? "text-success" : "text-ink-muted"}`}>
                          {enabled ? "Enabled" : "Disabled"}
                        </span>
                        <Toggle
                          checked={enabled}
                          disabled={locked}
                          onChange={(v) => updateSetting(agent.slug, { enabled: v })}
                          label={`Toggle ${agent.name}`} />

                      </div>
                    </div>);

                })}
              </div>
            </div>);

        })}
      </div>

      <div className="mt-6">
        <MarketingOffersEditor />
      </div>

      <p className="mt-4 text-xs text-ink-muted">
        Saved to your practice via <code className="rounded bg-sand-100 px-1.5 py-0.5">GET/PUT /api/v1/agent-config</code> (the{" "}
        <code className="rounded bg-sand-100 px-1.5 py-0.5">AgentConfig</code> model) — enabled, tone, and escalation
        sensitivity apply practice-wide and are Owner-editable. Costing comes from{" "}
        <code className="rounded bg-sand-100 px-1.5 py-0.5">GET /api/v1/agent-costing</code> — real, platform-wide
        per-session pricing, not mock.
      </p>
    </>);

}
