
interface ChannelBar {
  id: string;
  label: string;
  color: string;
  count: number;
}

interface RevenueProjectionsChartProps {
  byChannel: ChannelBar[];
}

// Vertical bar-chart card in the reference's visual style, fed by real data —
// sessions per channel (computeAnalytics().byChannel), not fabricated
// quarterly revenue (no such data source exists in this codebase).
export function RevenueProjectionsChart({ byChannel }: RevenueProjectionsChartProps) {
  const max = Math.max(...byChannel.map((c) => c.count), 1);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <p className="text-sm font-bold text-ink">Sessions by Channel</p>
      <p className="mt-0.5 text-xs text-ink-muted">Where patients are reaching your AI team</p>

      <div className="mt-6 flex h-[180px] items-end justify-between gap-3">
        {byChannel.map((c) => (
          <div key={c.id} className="flex flex-1 flex-col items-center gap-2">
            <span className="text-xs font-semibold tabular-nums text-ink">{c.count}</span>
            <div className="flex h-[130px] w-full items-end overflow-hidden rounded-lg bg-sand-100">
              <div
                className="w-full rounded-lg transition-all duration-700 ease-out"
                style={{ height: `${(c.count / max) * 100}%`, backgroundColor: c.color }} />

            </div>
            <span className="text-[11px] text-ink-muted">{c.label}</span>
          </div>
        ))}
      </div>
    </div>);

}
