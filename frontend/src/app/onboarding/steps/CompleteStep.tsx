import React from "react";
import { useNavigate } from "react-router-dom";
import { CheckCircle2Icon } from "lucide-react";
import { usePlanTier, planFor, capabilitiesFor } from "../../dashboard/plan/plan";
import { AGENT_CATEGORIES, TOTAL_AGENTS } from "../../../data/agents";

export function CompleteStep() {
  const navigate = useNavigate();
  const { tier } = usePlanTier();
  const plan = planFor(tier);
  const capabilities = capabilitiesFor(tier);
  const unlockedAgents = AGENT_CATEGORIES.filter((c) => capabilities.agentCategoryIds.includes(c.id)).reduce((n, c) => n + c.agents.length, 0);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/10 text-success">
        <CheckCircle2Icon className="h-7 w-7" />
      </span>
      <p className="mt-4 text-lg font-bold text-ink">You're all set</p>
      <p className="mt-1.5 text-sm text-ink-muted">
        Your <span className="font-semibold text-teal-600">{plan.name}</span> plan includes {unlockedAgents} of {TOTAL_AGENTS} agents
        across {capabilities.agentCategoryIds.length} categories.
      </p>

      <div className="mx-auto mt-5 max-w-xs space-y-1.5 text-left">
        {AGENT_CATEGORIES.map((c) =>
        <div key={c.id} className="flex items-center justify-between rounded-lg bg-sand-100 px-3 py-1.5 text-xs">
            <span className={capabilities.agentCategoryIds.includes(c.id) ? "text-ink" : "text-ink-muted"}>{c.label}</span>
            <span className={capabilities.agentCategoryIds.includes(c.id) ? "font-semibold text-success" : "text-ink-muted"}>
              {capabilities.agentCategoryIds.includes(c.id) ? "Included" : "Locked"}
            </span>
          </div>
        )}
      </div>

      <button
        onClick={() => navigate("/dashboard")}
        className="mt-6 w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

        Go to your dashboard
      </button>
    </div>);

}
