import { usePlan } from "./PlanContext";
import { planFor } from "./plan";

export function PlanBadge() {
  const { tier } = usePlan();
  const plan = planFor(tier);

  return (
    <span className="rounded-full bg-accent-500/8 px-3 py-1 text-xs font-semibold text-accent-500">
      {plan.name} plan
    </span>);

}
