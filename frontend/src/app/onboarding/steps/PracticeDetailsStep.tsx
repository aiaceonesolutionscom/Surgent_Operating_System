import { useState } from "react";
import { BuildingIcon, PhoneIcon } from "lucide-react";
import { usePracticeProfile } from "../../dashboard/profile/usePracticeProfile";

interface StepProps {
  onNext: () => void;
  onSkip: () => void;
}

// A field subset of dashboard/profile/ProfilePage.tsx — the rest (timezone,
// address) stays editable there later, this just gets the essentials in
// before first landing on the dashboard.
export function PracticeDetailsStep({ onNext, onSkip }: StepProps) {
  const { profile, update } = usePracticeProfile();
  const [name, setName] = useState(profile.name === "Your Practice" ? "" : profile.name);
  const [phone, setPhone] = useState(profile.onCallPhone);

  function handleContinue() {
    update({ name: name.trim() || profile.name, onCallPhone: phone });
    onNext();
  }

  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <p className="text-lg font-bold text-ink">What's your practice called?</p>
      <p className="mt-1 text-sm text-ink-muted">This shows up across your dashboard and in patient-facing messages.</p>

      <label className="mt-6 block">
        <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          <BuildingIcon className="h-3.5 w-3.5" /> Practice name
        </span>
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Meridian Surgery Group"
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

      </label>

      <label className="mt-4 block">
        <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          <PhoneIcon className="h-3.5 w-3.5" /> On-call phone
        </span>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+1 (555) 000-0000"
          className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />

      </label>

      <div className="mt-6 flex gap-3">
        <button
          onClick={onSkip}
          className="rounded-xl border border-sand-200 px-5 py-2.5 text-sm font-semibold text-ink-soft transition-colors hover:border-ink-muted/40">

          Skip
        </button>
        <button
          onClick={handleContinue}
          disabled={!name.trim()}
          className="flex-1 rounded-xl bg-teal-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">

          Continue
        </button>
      </div>
    </div>);

}
