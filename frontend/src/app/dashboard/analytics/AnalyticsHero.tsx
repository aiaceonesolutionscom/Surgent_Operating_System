import { SparklesIcon } from "lucide-react";
import { ProgressRing } from "../components/ProgressRing";

interface AnalyticsHeroProps {
  total: number;
  resolutionRate: number;
}

// Dark hero banner matching AIInsightsPanel.tsx's established dark-card
// language (bg-[#15171A], rounded-[28px]) for visual consistency across the
// dashboard's "premium" surfaces. Both stats are real (computeAnalytics()),
// not fabricated — no revenue-time-series data source exists in this
// codebase, so this deliberately doesn't invent a currency figure.
export function AnalyticsHero({ total, resolutionRate }: AnalyticsHeroProps) {
  return (
    <div className="relative overflow-hidden rounded-[28px] bg-[#15171A] p-8 shadow-[0_20px_50px_-20px_rgba(11,29,38,0.5)]">
      <SparklesIcon className="pointer-events-none absolute -right-6 -top-6 h-36 w-36 text-white/[0.05]" strokeWidth={1} />

      <div className="relative flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-lg">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-400">Annual performance report</p>
          <h2 className="mt-2 font-display text-[28px] font-600 leading-tight tracking-tight text-white">
            Exceptional outcomes driven by precision.
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            A rolling snapshot of how your AI team is performing across every channel this period.
          </p>
        </div>

        <div className="flex gap-8">
          <div className="flex flex-col items-center gap-2">
            <p className="font-display text-3xl font-700 tabular-nums text-white">{total}</p>
            <p className="text-center text-[11px] font-semibold uppercase tracking-wide text-white/40">Total sessions</p>
          </div>
          <div className="flex flex-col items-center gap-2">
            <div className="relative flex h-16 w-16 items-center justify-center">
              <ProgressRing percent={resolutionRate} size={64} color="#22D3EE" trackColor="rgba(255,255,255,0.12)" />
              <span className="absolute font-display text-sm font-700 text-white">{resolutionRate}%</span>
            </div>
            <p className="text-center text-[11px] font-semibold uppercase tracking-wide text-white/40">Resolution rate</p>
          </div>
        </div>
      </div>
    </div>);

}
