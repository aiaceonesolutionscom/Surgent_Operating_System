import { MessageCircleIcon } from "lucide-react";

// Dark status card matching AIInsightsPanel.tsx's shell. It states only what
// is true of the product: the receptionist answers incoming WhatsApp messages
// and hands the conversation to staff when it can't help. (It used to show an
// animated "live call" waveform and a "99.2% accuracy across 12 simultaneous
// streams" claim - neither was backed by any data, and this page is read by
// clinics deciding whether to trust the AI.)
export function VoiceEngineCard({ activeCallLabel }: { activeCallLabel: string }) {
  return (
    <div className="relative flex flex-col items-center gap-5 overflow-hidden rounded-[28px] bg-[#15171A] p-8 text-center shadow-[0_20px_50px_-20px_rgba(11,29,38,0.5)]">
      <span className="flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-xs font-semibold text-white/80">
        <span className="h-1.5 w-1.5 rounded-full bg-success" />
        {activeCallLabel}
      </span>

      <div>
        <h3 className="font-display text-2xl font-700 text-white">AI Receptionist is on</h3>
        <p className="mt-2 max-w-xs text-sm leading-relaxed text-white/50">
          Replies to incoming WhatsApp messages automatically, books appointments into free slots, and hands the
          conversation to your team when it can't help.
        </p>
      </div>

      <MessageCircleIcon className="pointer-events-none absolute -right-4 -top-4 h-24 w-24 text-white/[0.04]" strokeWidth={1} />
    </div>);

}
