import React from "react";
import { Link } from "react-router-dom";
import { ArrowUpRightIcon } from "lucide-react";
import { CHANNELS } from "../../dashboard/data/channels";
import { useConnectedChannels } from "../../dashboard/settings/useConnectedChannels";
import { usePlanTier } from "../../dashboard/plan/plan";
import { DASHBOARD_ROUTES } from "../../dashboard/constants/routes";

interface StepProps {
  onNext: () => void;
  onSkip: () => void;
}

// Tier-limited — Solo's maxSocialChannels is 1 (see dashboard/plan/plan.ts),
// so this is the natural place to make that choice, not an afterthought.
export function ChannelsStep({ onNext, onSkip }: StepProps) {
  const { channels, toggle } = useConnectedChannels();
  const { tier } = usePlanTier();
  const maxAllowed = tier === "solo" ? 1 : Infinity;

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <p className="text-lg font-bold text-ink">Connect a channel</p>
      <p className="mt-1 text-sm text-ink-muted">
        {tier === "solo" ?
        "Your plan includes 1 connected channel — pick where patients reach you." :
        "Pick where patients reach you — connect as many as you use."}
      </p>

      <div className="mt-6 grid grid-cols-2 gap-2.5">
        {Object.values(CHANNELS).map((c) => {
          const selected = channels.includes(c.id);
          const disabled = !selected && channels.length >= maxAllowed;
          return (
            <button
              key={c.id}
              onClick={() => toggle(c.id, maxAllowed)}
              disabled={disabled}
              className={`flex items-center gap-2.5 rounded-xl border px-4 py-3 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              selected ? "border-teal-600 bg-teal-600/8 text-teal-600" : "border-sand-200 text-ink-soft hover:border-teal-600/40"}`
              }>

              <c.icon className="h-4 w-4" style={{ color: c.color }} />
              {c.label}
            </button>);

        })}
      </div>

      {channels.includes("whatsapp") ? (
        <Link
          to={DASHBOARD_ROUTES.settingsIntegrations}
          className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-teal-600 hover:underline">
          Connect your real WhatsApp account now <ArrowUpRightIcon className="h-3 w-3" />
        </Link>
      ) : (
        <p className="mt-3 text-xs text-ink-muted">
          WhatsApp connects for real from Settings → Integrations once you pick it here. Other channels are a later phase.
        </p>
      )}

      <div className="mt-6 flex gap-3">
        <button
          onClick={onSkip}
          className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

          Skip
        </button>
        <button
          onClick={onNext}
          className="flex-1 rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

          Continue
        </button>
      </div>
    </div>);

}
