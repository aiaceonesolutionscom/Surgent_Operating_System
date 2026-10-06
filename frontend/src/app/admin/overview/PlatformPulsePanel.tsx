import { Link } from "react-router-dom";
import { SparklesIcon, ArrowUpRightIcon } from "lucide-react";
import { ADMIN_ROUTES } from "../constants/routes";

interface PlatformPulsePanelProps {
  planDistribution: Record<string, number>;
}

const TIER_LABEL: Record<string, string> = {
  solo: "Solo",
  practice: "Practice",
  enterprise: "Enterprise",
  custom: "Custom"
};

// Structural reuse of app/dashboard/overview/AIInsightsPanel.tsx's dark-card
// pattern — same shell, different content (plan mix instead of session
// insights), same "this is the one place that visually signals something
// live is happening here" role.
export function PlatformPulsePanel({ planDistribution }: PlatformPulsePanelProps) {
  const entries = Object.entries(planDistribution);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div className="relative flex w-full max-w-[340px] flex-col gap-5 overflow-hidden rounded-[28px] bg-panel p-6 shadow-[0_20px_50px_-20px_rgba(11,29,38,0.5)]">
      <SparklesIcon className="pointer-events-none absolute -right-4 -top-4 h-28 w-28 text-white/[0.06]" strokeWidth={1} />

      <div className="relative flex items-center gap-2">
        <h3 className="font-display text-lg font-600 text-white">Plan Mix</h3>
        <span className="h-2 w-2 rounded-full bg-success" />
      </div>

      <div className="relative flex flex-col gap-2.5">
        {entries.length === 0 &&
        <p className="text-sm text-white/50">No clinics yet.</p>
        }
        {entries.map(([tier, count]) =>
        <div key={tier} className="flex items-center justify-between rounded-2xl bg-white/[0.08] px-4 py-3.5">
            <div className="flex-1">
              <p className="text-xs text-white/50">{TIER_LABEL[tier] ?? tier}</p>
              <p className="mt-0.5 text-sm font-semibold text-white">{count} clinic{count === 1 ? "" : "s"}</p>
            </div>
            <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
              <div
              className="h-full rounded-full bg-cyan-400"
              style={{ width: `${total ? (count / total) * 100 : 0}%` }} />

            </div>
          </div>
        )}
      </div>

      <Link
        to={ADMIN_ROUTES.clinics}
        className="relative flex items-center justify-center gap-1.5 rounded-xl bg-accent-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

        Browse all clinics
        <ArrowUpRightIcon className="h-4 w-4" />
      </Link>
    </div>);

}
