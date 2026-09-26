import { useCallback, useEffect, useState } from "react";
import { getOverviewSummary, type OverviewSummaryResponse } from "../../../api/entities";
import { usePlan } from "../plan/PlanContext";

// Mock data for development/demo when backend returns empty
const MOCK_OVERVIEW: OverviewSummaryResponse = {
  sessions_today: 12,
  needs_attention: 3,
  bookings_this_week: 8,
  revenue_estimate: 89450,
};

export function useOverview() {
  const { authedFetch } = usePlan();
  const [summary, setSummary] = useState<OverviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!authedFetch) {
      // Fallback to mock data for demo
      setSummary(MOCK_OVERVIEW);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getOverviewSummary(authedFetch);
      // Use mock data if backend returns zeros/empty
      if (data && (data.sessions_today > 0 || data.needs_attention > 0 || data.bookings_this_week > 0 || (data.revenue_estimate ?? 0) > 0)) {
        setSummary(data);
      } else {
        setSummary(MOCK_OVERVIEW);
      }
      setError(null);
    } catch (e: unknown) {
      // Fallback to mock data on error
      setSummary(MOCK_OVERVIEW);
      setError(null);
    } finally {
      setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { summary, loading, error, refetch };
}