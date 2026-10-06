
interface ProgressRingProps {
  percent: number; // 0-100
  size?: number;
  color?: string;
  trackColor?: string; // override for dark surfaces — default suits light cards only
}

// Thick stroke, rounded caps — per DESIGN.md's "Charts & Progress Rings" spec.
export function ProgressRing({ percent, size = 44, color = "#0B6362", trackColor = "#E7E0D3" }: ProgressRingProps) {
  const stroke = 5;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.min(Math.max(percent, 0), 100) / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={trackColor} strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        style={{ transition: "stroke-dashoffset 0.6s ease-out" }} />

    </svg>);

}
