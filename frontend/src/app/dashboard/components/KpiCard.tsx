import type { LucideIcon } from "lucide-react";
import { ProgressRing } from "./ProgressRing";
import { TrendingUpIcon, TrendingDownIcon } from "lucide-react";

interface KpiCardProps {
  icon: LucideIcon;
  label: string;
  value: string;
  changePercent?: number;
  trend?: "up" | "down" | "neutral";
  trendLabel?: string;
  color?: string;
  loading?: boolean;
}

export function KpiCard({
  icon: Icon,
  label,
  value,
  changePercent,
  trend = "neutral",
  trendLabel,
  color = "#2563EB",
  loading = false
}: KpiCardProps) {
  // NOTE: must stay capitalised — a lowercase JSX tag like <trendIcon> is
  // treated as a DOM element name by React, not as this variable.
  const TrendIcon = trend === "up" ? TrendingUpIcon : trend === "down" ? TrendingDownIcon : null;
  const trendColor = trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : "text-sand-400";

  if (loading) {
    return (
      <div className="rounded-[22px] border border-sand-200 bg-white/85 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] animate-pulse">
        <div className="flex items-center justify-between">
          <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-sand-100">
            <div className="h-4.5 w-4.5 bg-sand-200 rounded" />
          </span>
          <div className="h-10 w-10 bg-sand-100 rounded-full" />
        </div>
        <div className="mt-5 h-3 w-20 bg-sand-100 rounded" />
        <div className="mt-2 h-7 w-24 bg-sand-100 rounded" />
      </div>
    );
  }

  return (
    <div className="rounded-[22px] border border-sand-200 bg-white/85 p-5 shadow-[0_4px_20px_rgba(15,23,42,0.05)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_30px_rgba(15,23,42,0.08)]">
      <div className="flex items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-[10px]" style={{ backgroundColor: `${color}1F`, color }}>
          <Icon className="h-4.5 w-4.5" />
        </span>
        {changePercent != null ? (
          <ProgressRing percent={changePercent} color={color} size={38} />
        ) : TrendIcon ? (
          <span className={`flex items-center gap-1 text-xs font-semibold ${trendColor}`}>
            <TrendIcon className="h-3.5 w-3.5" />
            {trendLabel || "vs last week"}
          </span>
        ) : null}
      </div>
      <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-muted">{label}</p>
      <p className="mt-1 font-display text-[28px] font-600 tabular-nums text-ink">{value}</p>
      {trendLabel && (
        <p className="mt-2 flex items-center gap-1 text-xs font-medium text-ink-muted">
          {TrendIcon && <TrendIcon className={`h-3 w-3 ${trendColor}`} />}
          <span className={trendColor}>{trendLabel}</span>
        </p>
      )}
    </div>
  );
}
