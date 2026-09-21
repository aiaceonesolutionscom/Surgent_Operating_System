import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useUser } from "@clerk/clerk-react";
import { PhoneCallIcon, AlertCircleIcon, CalendarCheckIcon, DollarSignIcon, ArrowRightIcon, CalendarIcon, PlusIcon } from "lucide-react";
import { KpiCard } from "../components/KpiCard";
import { SessionListItem } from "../sessions/SessionListItem";
import { EmptyState } from "../components/EmptyState";
import { useSessions } from "../sessions/useSessions";
import { useOverview } from "./useOverview";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { SetupChecklist } from "./SetupChecklist";
import { AIInsightsPanel } from "./AIInsightsPanel";
import { PatientSpotlight } from "./PatientSpotlight";
import { PatientVolumeChart } from "./PatientVolumeChart";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

// Same split as ProfilePage: useUser() throws without a mounted ClerkProvider,
// so the greeting falls back to a name-less form when Clerk isn't configured.
function Greeting() {
  if (!clerkEnabled) return <>Good morning</>;
  return <GreetingWithUser />;
}

function GreetingWithUser() {
  const { user } = useUser();
  const firstName = user?.firstName || "";
  return <>Good morning{firstName ? `, ${firstName}` : ""}</>;
}

export function OverviewPage() {
  const navigate = useNavigate();
  const { sessions, loading: sessionsLoading, error: sessionsError, refetch: refetchSessions } = useSessions();
  const { summary, loading: overviewLoading, error: overviewError, refetch: refetchOverview } = useOverview();

  const loading = sessionsLoading || overviewLoading;
  const error = sessionsError || overviewError;

  const retry = () => {
    refetchSessions();
    refetchOverview();
  };

  const needsAttention = sessions.filter((s) => s.status === "needs_attention");
  const recent = [...sessions].sort((a, b) => +new Date(b.updatedAt) - +new Date(a.updatedAt));
  const activeCount = sessions.filter((s) => s.status === "active").length;

  const sessionsToday = summary?.sessions_today ?? 0;
  const bookingsThisWeek = summary?.bookings_this_week ?? 0;
  const revenue = summary?.revenue_estimate;
  const revenueValue = revenue != null ? `$${revenue.toLocaleString()}` : "—";

  // Real, from the practice's own records — not a fabricated lead count.
  const statusLine = activeCount === 0 && sessionsToday === 0
    ? "No patient conversations to report yet — the AI team is standing by."
    : `The AI Receptionist is currently managing ${activeCount} active conversation${activeCount === 1 ? "" : "s"} across ${sessionsToday} session${sessionsToday === 1 ? "" : "s"} today, and ${bookingsThisWeek} booking${bookingsThisWeek === 1 ? "" : "s"} were created this week.`;

  return (
    <>
      <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-500">Operational overview</p>
          <h1 className="mt-2 font-display text-[28px] font-600 tracking-tight text-ink sm:text-[32px]">
            <Greeting />
          </h1>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-muted">{statusLine}</p>
        </div>
        <div className="flex shrink-0 gap-3">
          <Link
            to={DASHBOARD_ROUTES.frontDesk}
            className="flex items-center gap-2 rounded-xl border border-sand-200 bg-white px-5 py-3 text-sm font-semibold text-ink shadow-[0_1px_2px_rgba(11,29,38,0.04)] transition-colors hover:border-accent-500/30">
            <CalendarIcon className="h-4 w-4 text-accent-500" /> View schedule
          </Link>
          <Link
            to={DASHBOARD_ROUTES.bookAppointment}
            className="flex items-center gap-2 rounded-xl bg-accent-500 px-5 py-3 text-sm font-semibold text-white shadow-[0_8px_20px_-8px_rgba(37,99,235,0.5)] transition-colors hover:bg-accent-600">
            <PlusIcon className="h-4 w-4" /> New consultation
          </Link>
        </div>
      </div>

      {loading ?
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading overview…</p>
        </div> :
      error ?
      <div className="mt-6 rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={retry} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div> :
      <>
          <div className="mt-6">
            <SetupChecklist />
          </div>

          {/* All four numbers come from GET /api/v1/analytics/overview. No
              fabricated "vs last week" deltas — the backend has no comparison
              source yet, so the rings are omitted rather than invented. */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard icon={PhoneCallIcon} label="Sessions today" value={String(sessionsToday)} />
            <KpiCard icon={AlertCircleIcon} label="Needs attention" value={String(summary?.needs_attention ?? 0)} color="#EF4444" />
            <KpiCard icon={CalendarCheckIcon} label="Bookings created" value={String(bookingsThisWeek)} color="#10B981" />
            <KpiCard icon={DollarSignIcon} label="Revenue attributed" value={revenueValue} color="#06B6D4" />
          </div>

          <div className="mt-6 flex flex-col gap-6 lg:flex-row lg:items-start">
            <div className="flex flex-1 flex-col gap-6">
              <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
                <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
                  <p className="text-sm font-bold text-ink">Needs attention</p>
                  <Link to={DASHBOARD_ROUTES.sessionsNeedsAttention} className="flex items-center gap-1 text-xs font-semibold text-accent-500 hover:underline">
                    View all <ArrowRightIcon className="h-3 w-3" />
                  </Link>
                </div>
                {needsAttention.length === 0 ?
                <EmptyState icon={AlertCircleIcon} title="All clear" body="No sessions currently need staff review." /> :

                <div>
                    {needsAttention.map((s) =>
                  <SessionListItem key={s.id} session={s} active={false} onClick={() => navigate(DASHBOARD_ROUTES.sessionsNeedsAttention)} />
                  )}
                  </div>
                }
              </div>

              <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
                <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
                  <p className="text-sm font-bold text-ink">Recent activity</p>
                  <Link to={DASHBOARD_ROUTES.sessionsAll} className="flex items-center gap-1 text-xs font-semibold text-accent-500 hover:underline">
                    View all <ArrowRightIcon className="h-3 w-3" />
                  </Link>
                </div>
                <div>
                  {recent.slice(0, 6).map((s) =>
                  <SessionListItem key={s.id} session={s} active={false} onClick={() => navigate(DASHBOARD_ROUTES.sessionsAll)} />
                  )}
                </div>
              </div>
            </div>

            <AIInsightsPanel sessions={sessions} />
          </div>

          <div className="mt-8">
            <PatientVolumeChart sessions={sessions} />
          </div>

          <div className="mt-8">
            <PatientSpotlight />
          </div>
        </>
      }
    </>);

}