import { useEffect, useState } from "react";
import { AlertCircleIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { AnalyticsHero } from "./AnalyticsHero";
import { RevenueProjectionsChart } from "./RevenueProjectionsChart";
import { SurgicalVolumeDonut } from "./SurgicalVolumeDonut";
import { computeAnalytics } from "./computeAnalytics";
import { getSessionAnalytics, type SessionAnalyticsResponse } from "../../../api/entities";
import { usePlan } from "../plan/PlanContext";

export function AnalyticsPage() {
  const { authedFetch } = usePlan();
  const [analytics, setAnalytics] = useState<SessionAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = async () => {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getSessionAnalytics(authedFetch);
      setAnalytics(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authedFetch]);

  if (loading) {
    return (
      <>
        <PageHeader
          title="Analytics"
          subtitle="Computed from the same session records shown in Agent Sessions — not a separate illustrative dataset." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading analytics…</p>
        </div>
      </>);

  }

  if (error || !analytics) {
    return (
      <>
        <PageHeader
          title="Analytics"
          subtitle="Computed from the same session records shown in Agent Sessions — not a separate illustrative dataset." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{error || "No analytics available yet."}</p>
          <button onClick={refetch} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div>
      </>);

  }

  const { total, byChannel, byCategory, escalationRate, resolutionRate } = computeAnalytics(analytics);

  return (
    <>
      <PageHeader
        title="Analytics"
        subtitle="Computed from the same session records shown in Agent Sessions — not a separate illustrative dataset." />

      <AnalyticsHero total={total} resolutionRate={resolutionRate} />

      <div className="mt-6 flex items-center gap-2 text-sm text-ink-muted">
        <AlertCircleIcon className="h-4 w-4 text-danger" />
        Escalation rate: <span className="font-semibold text-ink">{escalationRate}%</span>
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <RevenueProjectionsChart byChannel={byChannel} />
        <SurgicalVolumeDonut byCategory={byCategory} />
      </div>
    </>);

}