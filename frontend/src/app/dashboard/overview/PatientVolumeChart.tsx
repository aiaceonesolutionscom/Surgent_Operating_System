import { TrendingUpIcon } from "lucide-react";
import type { Session } from "../sessions/types";
import { computeDailyVolume } from "./computeVolume";

const WIDTH = 800;
const HEIGHT = 220;
const PAD = 24;

// Hand-rolled inline SVG — matches BarRow.tsx/ProgressRing.tsx's existing
// no-charting-library convention. Fed by the live sessions OverviewPage
// passes in (same source every other Overview number reads from).
export function PatientVolumeChart({ sessions }: { sessions: Session[] }) {
  const points = computeDailyVolume(sessions);
  const total = points.reduce((sum, p) => sum + p.count, 0);
  const max = Math.max(...points.map((p) => p.count), 1);

  const innerW = WIDTH - PAD * 2;
  const innerH = HEIGHT - PAD * 2;
  const step = points.length > 1 ? innerW / (points.length - 1) : 0;

  const coords = points.map((p, i) => ({
    x: PAD + (points.length > 1 ? i * step : innerW / 2),
    y: PAD + innerH - (p.count / max) * innerH
  }));

  const linePath = coords.map((c, i) => `${i === 0 ? "M" : "L"}${c.x},${c.y}`).join(" ");
  const areaPath = `${linePath} L${coords[coords.length - 1]?.x ?? PAD},${PAD + innerH} L${coords[0]?.x ?? PAD},${PAD + innerH} Z`;

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-ink">Patient Volume Analysis</p>
          <p className="mt-0.5 text-xs text-ink-muted">Sessions per day · live synchronization</p>
        </div>
        <span className="flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-semibold text-success">
          <TrendingUpIcon className="h-3.5 w-3.5" /> {total} total
        </span>
      </div>

      <div className="mt-5 w-full overflow-x-auto">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="h-[220px] w-full min-w-[480px]" preserveAspectRatio="none">
          <defs>
            <linearGradient id="volume-gradient" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#2563EB" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((f) => (
            <line
              key={f}
              x1={PAD}
              x2={WIDTH - PAD}
              y1={PAD + innerH * f}
              y2={PAD + innerH * f}
              stroke="#E2E8F0"
              strokeDasharray="4,4" />

          ))}
          {points.length > 0 && <path d={areaPath} fill="url(#volume-gradient)" />}
          {points.length > 0 && (
            <path d={linePath} fill="none" stroke="#2563EB" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
          )}
          {coords.map((c, i) => (
            <circle key={i} cx={c.x} cy={c.y} r={4} fill="#2563EB" stroke="white" strokeWidth={2} />
          ))}
        </svg>
      </div>

      <div className="mt-3 flex justify-between text-[11px] text-ink-muted">
        {points.map((p) => (
          <span key={p.label}>{p.label}</span>
        ))}
      </div>
    </div>);

}
