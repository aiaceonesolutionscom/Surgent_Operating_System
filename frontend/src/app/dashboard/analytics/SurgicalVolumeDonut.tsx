
interface CategorySlice {
  id: string;
  label: string;
  count: number;
}

interface SurgicalVolumeDonutProps {
  byCategory: CategorySlice[];
}

// Sessions by agent category — the honest substitute for "surgical volume by
// procedure" (no real procedure/surgery-volume data source exists in this
// codebase). ProgressRing only draws a single value, so this is a genuinely
// new small multi-arc SVG donut (stacked stroke-dasharray segments).
const SLICE_COLORS = ["#2563EB", "#06B6D4", "#C9A24B", "#10B981", "#F59E0B"];

const SIZE = 160;
const STROKE = 22;
const R = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * R;

export function SurgicalVolumeDonut({ byCategory }: SurgicalVolumeDonutProps) {
  const total = byCategory.reduce((sum, c) => sum + c.count, 0);
  let offset = 0;

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <p className="text-sm font-bold text-ink">Sessions by Agent Category</p>
      <p className="mt-0.5 text-xs text-ink-muted">Breakdown across the 5 agent categories</p>

      <div className="mt-4 flex items-center gap-6">
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} className="-rotate-90 shrink-0">
          <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="none" stroke="#F2F4F6" strokeWidth={STROKE} />
          {byCategory.map((c, i) => {
            const frac = total > 0 ? c.count / total : 0;
            const len = frac * CIRCUMFERENCE;
            const dashoffset = -offset;
            offset += len;
            if (len === 0) return null;
            return (
              <circle
                key={c.id}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={R}
                fill="none"
                stroke={SLICE_COLORS[i % SLICE_COLORS.length]}
                strokeWidth={STROKE}
                strokeDasharray={`${len} ${CIRCUMFERENCE - len}`}
                strokeDashoffset={dashoffset}
                strokeLinecap="butt" />

            );
          })}
          <text
            x={SIZE / 2}
            y={SIZE / 2}
            transform={`rotate(90 ${SIZE / 2} ${SIZE / 2})`}
            textAnchor="middle"
            dominantBaseline="middle"
            className="font-bold"
            style={{ fontSize: 22, fill: "#0F172A" }}>

            {total}
          </text>
        </svg>

        <div className="flex-1 space-y-2">
          {byCategory.map((c, i) => (
            <div key={c.id} className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-ink-soft">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: SLICE_COLORS[i % SLICE_COLORS.length] }} />
                {c.label}
              </span>
              <span className="font-semibold tabular-nums text-ink">{c.count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>);

}
