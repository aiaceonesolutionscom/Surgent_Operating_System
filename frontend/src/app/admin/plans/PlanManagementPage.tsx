import { useEffect, useState } from "react";
import { Loader2Icon, PencilIcon, CheckIcon } from "lucide-react";
import { listAdminPlans, updateAdminPlan } from "../../../api/admin";
import type { PlanResponse } from "../../../api/practice";
import { PlanEditDrawer } from "./PlanEditDrawer";

export function PlanManagementPage() {
  const [plans, setPlans] = useState<PlanResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<PlanResponse | null>(null);

  function load() {
    listAdminPlans()
    .then(setPlans)
    .catch(() => setError("Couldn't load plans."));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSave(body: Partial<PlanResponse>) {
    if (!editing) return;
    await updateAdminPlan(editing.id, body);
    load();
  }

  return (
    <>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Plans & Pricing</p>
        <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">
          Change pricing without touching code
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">
          Edits here apply immediately — to what new checkouts charge and what every clinic's dashboard is gated on.
        </p>
      </div>

      {error && <p className="mt-6 text-sm text-danger">{error}</p>}
      {!plans && !error &&
      <div className="mt-10 flex justify-center">
          <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
        </div>
      }

      {plans &&
      <div className="mt-6 grid gap-5 lg:grid-cols-3">
          {plans.map((plan) =>
        <div
          key={plan.id}
          className={`relative flex flex-col gap-5 rounded-3xl border bg-white p-6 shadow-[0_4px_20px_rgba(15,23,42,0.05)] ${
          plan.highlight ? "border-accent-500" : "border-sand-200"}`
          }>

              {plan.highlight &&
          <span className="absolute -top-3 left-6 rounded-full bg-accent-500 px-3 py-1 text-[11px] font-bold text-white">
                  Most popular
                </span>
          }
              {!plan.is_active &&
          <span className="absolute right-6 top-6 rounded-full bg-ink-muted/10 px-2.5 py-1 text-[11px] font-semibold text-ink-muted">
                  Inactive
                </span>
          }

              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{plan.tier}</p>
                <h3 className="font-display text-xl font-600 text-ink">{plan.name}</h3>
                {plan.tagline && <p className="mt-1 text-sm text-ink-muted">{plan.tagline}</p>}
              </div>

              <p className="font-display text-3xl font-bold text-ink">
                {plan.is_custom_pricing || plan.price == null ?
            "Custom" :

            <>
                    ${plan.price.toLocaleString()}
                    <span className="text-base font-medium text-ink-muted">/{plan.billing_period === "monthly" ? "mo" : plan.billing_period}</span>
                  </>
            }
              </p>

              <div className="flex-1 space-y-2">
                {plan.features.map((f) =>
            <div key={f} className="flex items-start gap-2 text-sm text-ink-soft">
                    <CheckIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                    {f}
                  </div>
            )}
              </div>

              <button
            onClick={() => setEditing(plan)}
            className="flex items-center justify-center gap-2 rounded-xl border border-sand-200 py-2.5 text-sm font-semibold text-ink transition-colors hover:border-accent-500/50 hover:text-accent-700">

                <PencilIcon className="h-3.5 w-3.5" /> Edit plan
              </button>
            </div>
        )}
        </div>
      }

      {editing &&
      <PlanEditDrawer plan={editing} onClose={() => setEditing(null)} onSave={handleSave} />
      }
    </>);

}
