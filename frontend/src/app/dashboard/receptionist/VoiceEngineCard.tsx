import { PhoneCallIcon } from "lucide-react";

// Dark card matching AIInsightsPanel.tsx's shell. The waveform is an
// animated row of CSS-height bars — an honest-looking mock, not a real
// audio visualization (no live audio stream exists on the frontend).
const BAR_HEIGHTS = [18, 32, 45, 60, 38, 55, 70, 42, 28, 50, 65, 34, 20, 46, 58, 30, 44, 62, 36, 24];

export function VoiceEngineCard({ activeCallLabel }: { activeCallLabel: string }) {
  return (
    <div className="relative flex flex-col items-center gap-5 overflow-hidden rounded-[28px] bg-[#15171A] p-8 text-center shadow-[0_20px_50px_-20px_rgba(11,29,38,0.5)]">
      <span className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/80">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
        Live call: {activeCallLabel}
      </span>

      <div className="flex h-16 items-end gap-1">
        {BAR_HEIGHTS.map((h, i) => (
          <span
            key={i}
            className="w-1.5 rounded-full bg-accent-400"
            style={{
              height: `${h}%`,
              animation: `voice-bar 1.1s ease-in-out ${i * 0.05}s infinite alternate`
            }} />

        ))}
      </div>
      <style>{`@keyframes voice-bar { from { opacity: 0.4; transform: scaleY(0.6); } to { opacity: 1; transform: scaleY(1); } }`}</style>

      <div>
        <h3 className="font-display text-2xl font-700 text-white">Voice Engine Active</h3>
        <p className="mt-2 max-w-xs text-sm leading-relaxed text-white/50">
          Processing natural language with 99.2% accuracy across 12 simultaneous streams.
        </p>
      </div>

      <PhoneCallIcon className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 text-white/[0.04]" strokeWidth={1} />
    </div>);

}
