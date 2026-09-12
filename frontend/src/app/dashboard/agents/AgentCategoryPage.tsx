import React from "react";
import { Link, useParams } from "react-router-dom";
import { ActivityIcon } from "lucide-react";
import { AGENT_CATEGORIES } from "../../../data/agents";
import { PageHeader } from "../components/PageHeader";
import { ComingSoon } from "../components/ComingSoon";
import { SessionsView } from "../sessions/SessionsView";
import { useSessions } from "../sessions/useSessions";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import { UpgradeRequired } from "../plan/UpgradeRequired";
import { minTierForCategory } from "../plan/plan";

const CATEGORY_LOGOS: Record<string, string> = {
  "front-desk": "/agent-logos/Front Desk & Intake.png",
  "consultation": "/agent-logos/Consultation & Screening.png",
  "surgery": "/agent-logos/Surgery Management.png",
  "post-care": "/agent-logos/Post-Surgery Care.png",
  "business": "/agent-logos/Business & Operations.png",
};

// One shared template for all 5 category routes (front-desk, consultation,
// surgery, post-care, business) — matches the marketing site's
// AgentDetailPage.tsx pattern (one template + data, not 5 hand-built pages).
export function AgentCategoryPage() {
  const { categoryId } = useParams<{ categoryId: string }>();
  const category = AGENT_CATEGORIES.find((c) => c.id === categoryId);
  const { allowsCategory, loading } = usePlan();
  const { sessions: allSessions, loading: sessionsLoading, error: sessionsError, refetch } = useSessions();

  if (!category) {
    return (
      <ComingSoon icon={ActivityIcon} title="Unknown category" body="This agent category doesn't exist." phase="—" />);

  }

  if (loading) return null;

  if (!allowsCategory(category.id)) {
    return <UpgradeRequired title={category.label} tagline={category.tagline} minTier={minTierForCategory(category.id) || "enterprise"} agents={category.agents} />;
  }

  const categorySlugs = new Set(category.agents.map((a) => a.slug));
  const sessions = allSessions.filter((s) => categorySlugs.has(s.agentSlug));

  return (
    <>
      <PageHeader title={category.label} subtitle={category.tagline} imgSrc={CATEGORY_LOGOS[category.id]} />
      <div className="mb-6 flex flex-wrap gap-2">
        {category.agents.map((a) =>
        <Link
          key={a.slug}
          to={DASHBOARD_ROUTES.agentDetail(category.id, a.slug)}
          className="flex items-center gap-1.5 rounded-full border border-sand-200 bg-white px-3 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

            <a.icon className="h-3.5 w-3.5 text-teal-600" />
            {a.name}
          </Link>
        )}
      </div>
      {sessionsLoading ?
      <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading sessions...</p>
        </div> :
      sessionsError ?
      <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{sessionsError}</p>
          <button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div> :

      <SessionsView sessions={sessions} />
      }
    </>);

}
