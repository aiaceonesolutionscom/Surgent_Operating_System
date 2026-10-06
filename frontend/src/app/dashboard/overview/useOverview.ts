import { useCallback, useEffect, useState } from "react";
import { getOverviewSummary, type OverviewSummaryResponse } from "../../../api/entities";
import { usePlan } from "../plan/PlanContext";
import { isDemoMode } from "../../../data/demoMode";

// Demo-only placeholder, used when VITE_DEMO_MODE is explicitly enabled.
// It is never a substitute for a failed request or an all-zero practice —
// showing fake clinic numbers on a real dashboard is worse than showing none.
const MOCK_OVERVIEW: OverviewSummaryResponse = {
  sessions_today: 12,
  needs_attention: 3,
  bookings_this_week: 8,
  revenue_estimate: 89450,
};

const EMPTY_OVERVIEW: OverviewSummaryResponse = {
  sessions_today: 0,
  needs_attention: 0,
  bookings_this_week: 0,
  revenue_estimate: 0,
};

export function useOverview() {
  const { authedFetch } = usePlan();
  const [summary, setSummary] = useState<OverviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!authedFetch) {
      setSummary(isDemoMode() ? MOCK_OVERVIEW : null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getOverviewSummary(authedFetch);
      setSummary(data ?? EMPTY_OVERVIEW);
      setError(null);
    } catch (e: unknown) {
      setSummary(isDemoMode() ? MOCK_OVERVIEW : null);
      setError(e instanceof Error && e.message ? e.message : "Couldn't load the overview.");
    } finally {
      setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { summary, loading, error, refetch };
}
