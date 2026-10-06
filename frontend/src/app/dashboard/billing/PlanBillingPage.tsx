import { CreditCardIcon, HeadsetIcon, EyeIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePlan } from "../plan/PlanContext";
import { planFor } from "../plan/plan";
import { PlanComparisonTable } from "./PlanComparisonTable";
import type { Role } from "../../../data/roles";

const SUPPORT_LABEL: Record<string, string> = {
  email: "Email support",
  priority: "Priority support",
  dedicated: "Dedicated success manager"
};

const ROLE_PREVIEW_OPTIONS: { role: Role; label: string }[] = [
{ role: "owner", label: "Owner" },
{ role: "doctor", label: "Doctor" }];


export function PlanBillingPage() {
  const { tier, role, capabilities, setRoleOverride, source } = usePlan();
  const plan = planFor(tier);

  return (
    <>
      <PageHeader title="Plan & billing" subtitle="Your current plan, what it includes, and what upgrading unlocks." />

      <div className="mb-6 flex flex-wrap items-center gap-4 rounded-3xl border border-sand-200 bg-white p-6 shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-teal-600/8 text-teal-600">
          <CreditCardIcon className="h-6 w-6" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-ink">
            You're on the {plan.name} plan — {plan.price}{plan.period}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-muted">
            <HeadsetIcon className="h-3.5 w-3.5" /> {SUPPORT_LABEL[capabilities.supportLevel]}
          </p>
        </div>
        <p className="text-xs text-ink-muted">
          Real billing management (invoices, payment method, cancel) connects once Stripe's customer portal is wired up.
        </p>
      </div>

      <PlanComparisonTable />

      {source !== "api" &&
      <div className="mt-6 rounded-3xl border border-dashed border-sand-200 bg-white p-6">
          <div className="flex items-center gap-2 text-sm font-bold text-ink">
            <EyeIcon className="h-4 w-4 text-accent-500" /> Preview as
          </div>
          <p className="mt-1 text-xs text-ink-muted">
            Local-only — switches the dashboard's role-based nav/pages without a real login. No effect on any real
            account or data; disappears once a real signed-in session resolves a role.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {ROLE_PREVIEW_OPTIONS.map((opt) =>
          <button
            key={opt.role}
            type="button"
            onClick={() => setRoleOverride(opt.role)}
            className={`rounded-xl border px-4 py-2 text-xs font-semibold transition-colors ${
            role === opt.role ?
            "border-accent-500 bg-accent-500/10 text-accent-700" :
            "border-sand-200 text-ink-soft hover:border-accent-500/40 hover:text-accent-600"}`
            }>

                {opt.label}
              </button>
          )}
          </div>
        </div>
      }
    </>);

}
