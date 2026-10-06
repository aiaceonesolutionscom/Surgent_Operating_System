
const COLORS = ["#2563EB", "#06B6D4", "#10B981"];

// Same hand-rolled width-bar convention as BarRow.tsx, decreasing width per
// funnel stage instead of a shared max. Data is always real — ReceptionistMonitorPage
// passes the AI-receptionist pipeline (from GET /ai-receptionist/overview) and
// FunnelPage passes patient-funnel stages (from GET /patients/funnel-summary).
export interface PipelineStage {
  label: string;
  count: number;
}

export function BookingPipelineFunnel({ stages, title = "Booking Pipeline" }: { stages: PipelineStage[]; title?: string }) {
  const max = Math.max(...stages.map((s) => s.count), 1);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <p className="text-sm font-bold text-ink">{title}</p>
      <div className="mt-5 space-y-4">
        {stages.map((stage, i) => (
          <div key={stage.label}>
            <div className="flex items-center justify-between text-sm">
              <span className="text-ink-soft">{stage.label}</span>
              <span className="font-mono font-semibold tabular-nums text-ink">{stage.count.toLocaleString()}</span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-sand-100">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{ width: `${(stage.count / max) * 100}%`, backgroundColor: COLORS[i % COLORS.length] }} />

            </div>
          </div>
        ))}
      </div>
    </div>);

}
