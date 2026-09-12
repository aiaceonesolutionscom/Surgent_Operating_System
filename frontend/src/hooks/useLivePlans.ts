import { useEffect, useState } from "react";
import { PLANS, type Plan } from "../data/plans";
import { listPlans } from "../api/practice";

function money(n: number) {
  return `$${n.toLocaleString()}`;
}

// Bridges the DB-backed Plan model (backend/src/models/plan.py, editable
// from /admin/plans) into data/plans.ts's display shape, so marketing
// Pricing.tsx and DemoPaymentPage.tsx show whatever an admin last set
// instead of the hardcoded PLANS array. Falls back to PLANS on load/error
// — same "static fallback while live data loads" pattern as
// useAgentCosting.ts, so nothing regresses if the API is unreachable.
export function useLivePlans(): Plan[] {
  const [plans, setPlans] = useState<Plan[]>(PLANS);

  useEffect(() => {
    let cancelled = false;
    listPlans()
    .then((rows) => {
      if (cancelled || rows.length === 0) return;
      const mapped: Plan[] = rows
      .filter((r) => r.tier !== "custom" && r.tier !== "solo")
      .sort((a, b) => a.display_order - b.display_order)
      .map((r) => ({
        id: r.tier as Plan["id"],
        name: r.name,
        tagline: r.tagline ?? "",
        price: r.is_custom_pricing || r.price == null ? "Custom" : money(r.price),
        period: r.is_custom_pricing || r.price == null ? "" : `/${r.billing_period === "monthly" ? "mo" : r.billing_period}`,
        highlight: r.highlight,
        features: r.features
      }));
      if (mapped.length) setPlans(mapped);
    })
    .catch(() => {
      // Keep the static fallback already in state.
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return plans;
}
