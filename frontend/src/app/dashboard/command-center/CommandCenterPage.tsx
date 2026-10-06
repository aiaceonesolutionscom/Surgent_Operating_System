import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { CommandCenterChat } from "./CommandCenterChat";

// Full-page fallback for direct navigation to /dashboard/command-center
// (deep links, typed URLs). The primary entry point is now
// AIInsightsPanel's button, which opens CommandCenterModal in place instead
// of routing here — see command-center/README.md.
export function CommandCenterPage() {
  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <Link
        to={DASHBOARD_ROUTES.overview}
        className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors hover:text-ink">

        <ArrowLeftIcon className="h-4 w-4" /> Back to overview
      </Link>

      <PageHeader
        title="AI Command Center"
        subtitle="Ask the Main Agent anything — it consults the right sub-agent(s) and relays a real answer." />


      <div className="min-h-0 flex-1">
        <CommandCenterChat />
      </div>
    </div>);

}
