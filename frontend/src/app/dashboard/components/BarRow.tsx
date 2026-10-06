
interface BarRowProps {
  label: string;
  count: number;
  max: number;
  color?: string;
}

export function BarRow({ label, count, max, color = "#0B6362" }: BarRowProps) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink-soft">{label}</span>
        <span className="font-mono font-semibold tabular-nums text-ink">{count}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-sand-100">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: color }} />

      </div>
    </div>);

}
