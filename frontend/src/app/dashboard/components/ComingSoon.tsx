import type { LucideIcon } from "lucide-react";

interface ComingSoonProps {
  icon: LucideIcon;
  title: string;
  body: string;
  phase: string;
}

// Every sidebar destination gets a real route today, even ones whose full
// build is a later phase (see app/dashboard/README.md) — this keeps the
// navigation honest instead of a dead link or a blank page.
export function ComingSoon({ icon: Icon, title, body, phase }: ComingSoonProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border border-dashed border-sand-200 bg-white px-6 py-20 text-center shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
        <Icon className="h-6 w-6" />
      </span>
      <p className="mt-4 text-base font-bold text-ink">{title}</p>
      <p className="mt-1.5 max-w-sm text-sm text-ink-muted">{body}</p>
      <span className="mt-4 rounded-full bg-sand-100 px-3 py-1 text-xs font-semibold text-ink-muted">
        {phase}
      </span>
    </div>);

}
