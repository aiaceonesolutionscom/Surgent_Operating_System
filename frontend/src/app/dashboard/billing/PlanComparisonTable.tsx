import { CheckIcon } from "lucide-react";
import { PLANS } from "../../../data/plans";
import { usePlan } from "../plan/PlanContext";

// Reuses the marketing site's own PLANS data directly — the in-app
// comparison is literally the Pricing section's copy, so it can't drift.
// "Switch to this plan" writes the local plan override, same as onboarding's
// claim step — this replaced the old Topbar DevPlanSwitcher, so plan-switching
// now lives only here, where it reads as "manage my plan."
export function PlanComparisonTable() {
  const { tier, setOverride } = usePlan();

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {PLANS.map((plan) => {
        const isCurrent = plan.id === tier;
        return (
          <div
            key={plan.id}
            className={`flex flex-col rounded-3xl border p-6 ${
            isCurrent ? "border-teal-600 bg-teal-600/[0.03] shadow-[0_4px_20px_rgba(11,29,38,0.08)]" : "border-sand-200 bg-white shadow-[0_4px_20px_rgba(11,29,38,0.05)]"}`
            }>

            <div className="flex items-center justify-between">
              <p className="text-sm font-bold text-ink">{plan.name}</p>
              {isCurrent &&
              <span className="rounded-full bg-teal-600 px-2.5 py-1 text-[11px] font-bold text-white">
                  Current plan
                </span>
              }
            </div>
            <p className="mt-1 text-xs text-ink-muted">{plan.tagline}</p>
            <p className="mt-4 font-display text-2xl font-bold text-ink">
              {plan.price}<span className="text-sm font-medium text-ink-muted">{plan.period}</span>
            </p>
            <ul className="mt-5 flex-1 space-y-2.5">
              {plan.features.map((f) =>
              <li key={f} className="flex items-start gap-2 text-sm text-ink-soft">
                  <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-teal-600" />
                  {f}
                </li>
              )}
            </ul>

            {!isCurrent &&
            <button
              onClick={() => setOverride(plan.id)}
              className="mt-5 flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-sand-200 py-2.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

                Switch to this plan
              </button>
            }
          </div>);

      })}
    </div>);

}
