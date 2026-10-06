import { Link } from "react-router-dom";
import { LockIcon } from "lucide-react";
import type { Agent } from "../../../data/agents";
import type { PlanTier } from "../../../data/planTiers";
import { planFor } from "./plan";
import { DASHBOARD_ROUTES } from "../constants/routes";

interface UpgradeRequiredProps {
  title: string;
  tagline: string;
  minTier: PlanTier;
  agents?: Agent[];
}

// The locked-surface pattern: show the real thing (label, tagline, and the
// actual agent chips where there are any) rather than hiding it — a feature
// the customer never sees is a feature they never upgrade for. Reuses
// ComingSoon.tsx's dashed-border card language so it reads as part of the
// same system, not a different "paywall" component bolted on.
export function UpgradeRequired({ title, tagline, minTier, agents }: UpgradeRequiredProps) {
  const plan = planFor(minTier);

  return (
    <div className="rounded-3xl border border-dashed border-sand-200 bg-white px-6 py-12 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
        <LockIcon className="h-6 w-6" />
      </span>
      <p className="mt-4 text-base font-bold text-ink">{title}</p>
      <p className="mx-auto mt-1.5 max-w-sm text-sm text-ink-muted">{tagline}</p>

      {agents && agents.length > 0 &&
      <div className="mx-auto mt-5 flex max-w-lg flex-wrap justify-center gap-2">
          {agents.map((a) =>
        <span
          key={a.slug}
          className="flex items-center gap-1.5 rounded-full border border-sand-200 bg-sand-50 px-3 py-1.5 text-xs font-medium text-ink-muted opacity-70">

              <a.icon className="h-3.5 w-3.5" />
              {a.name}
            </span>
        )}
        </div>
      }

      <p className="mt-5 text-sm font-semibold text-ink">
        Included in <span className="text-teal-600">{plan.name}</span> — {plan.price}{plan.period}
      </p>
      <Link
        to={DASHBOARD_ROUTES.settingsBilling}
        className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

        Upgrade to {plan.name}
      </Link>
    </div>);

}
