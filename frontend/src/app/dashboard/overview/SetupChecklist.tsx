import React from "react";
import { Link } from "react-router-dom";
import { CheckIcon, CircleIcon, SparklesIcon } from "lucide-react";
import { usePracticeProfile } from "../profile/usePracticeProfile";
import { useDoctors } from "../doctors/useDoctors";
import { usePlan } from "../plan/PlanContext";
import { DASHBOARD_ROUTES } from "../constants/routes";

interface ChecklistItem {
  label: string;
  done: boolean;
  to: string;
}

// Derived from real state, not a static onboarding flag — so it can never
// drift out of sync with what's actually filled in, and it's never a dead
// end for someone who skipped the setup wizard (or arrived here before that
// flow existed). Disappears once everything's done.
export function SetupChecklist() {
  const { authedFetch } = usePlan();
  const { profile } = usePracticeProfile(authedFetch);
  const { doctors, loading } = useDoctors(authedFetch);

  if (loading) return null;

  const items: ChecklistItem[] = [
  { label: "Set your practice name", done: profile.name !== "Your Practice", to: DASHBOARD_ROUTES.settingsProfile },
  { label: "Add your first doctor", done: doctors.length > 0, to: DASHBOARD_ROUTES.doctorNew }];


  const remaining = items.filter((i) => !i.done);
  if (remaining.length === 0) return null;

  return (
    <div className="mb-6 rounded-3xl border border-accent-500/20 bg-accent-500/[0.03] p-5 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
      <div className="flex items-center gap-2 text-sm font-bold text-ink">
        <SparklesIcon className="h-4 w-4 text-accent-500" /> Finish setting up
      </div>
      <div className="mt-3 space-y-1.5">
        {items.map((item) =>
        <Link
          key={item.label}
          to={item.to}
          className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition-colors ${
          item.done ? "text-ink-muted" : "text-ink-soft hover:bg-white"}`
          }>

            {item.done ?
          <CheckIcon className="h-4 w-4 shrink-0 text-success" /> :

          <CircleIcon className="h-4 w-4 shrink-0 text-ink-muted/40" />
          }
            <span className={item.done ? "line-through" : ""}>{item.label}</span>
          </Link>
        )}
      </div>
    </div>);

}
