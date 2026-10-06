
import type { ReceptionistHealth } from "../../../api/entities";

function timeAgo(iso: string | null) {
  if (!iso) return "Never";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.max(1, Math.round(diffMs / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

const FALLBACK: ReceptionistHealth = {
  status: "No activity yet",
  last_activity_at: null,
  sessions_24h: 0,
  interactions_24h: 0,
};

// Real numbers only — "CPU load" / "knowledge docs" telemetry doesn't exist
// yet, so this card shows the two things the system actually measures: has
// the AI done anything recently (last activity), and how much in the last 24h.
export function SystemHealthCard({ health }: { health?: ReceptionistHealth | null }) {
  const h = health ?? FALLBACK;
  const active = h.status !== "No activity yet";
  return (
    <div className="rounded-3xl bg-gradient-to-br from-accent-700 to-accent-500 p-6 text-white shadow-[0_20px_50px_-20px_rgba(37,99,235,0.5)]">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">AI Receptionist health</p>
      <p className="mt-1.5 flex items-center gap-1.5 text-xs text-white/80">
        <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-success" : "bg-ink-muted"}`} /> {h.status}
      </p>
      <p className="mt-3 max-w-xs text-sm leading-relaxed text-white/70">
        Last AI activity: <span className="font-semibold text-white">{timeAgo(h.last_activity_at)}</span>
      </p>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-2xl bg-white/10 px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wide text-white/50">Sessions (24h)</p>
          <p className="mt-0.5 text-lg font-700 tabular-nums">{h.sessions_24h}</p>
        </div>
        <div className="rounded-2xl bg-white/10 px-3 py-2.5">
          <p className="text-[10px] uppercase tracking-wide text-white/50">Interactions (24h)</p>
          <p className="mt-0.5 text-lg font-700 tabular-nums">{h.interactions_24h}</p>
        </div>
      </div>
    </div>);

}