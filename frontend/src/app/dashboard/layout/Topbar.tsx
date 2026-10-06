import { Link } from "react-router-dom";
import { PanelLeftIcon, PanelLeftOpenIcon } from "lucide-react";
import { CommandPalette } from "./CommandPalette";
import { PlanBadge } from "../plan/PlanBadge";
import { MessagesBell } from "./MessagesBell";

// The scroll-guide avatar's photo doubles as the dashboard's account/agent
// identity — one consistent character across the marketing site and the
// product, instead of a generic new bot icon.
export function Topbar({ collapsed, onToggleCollapse }: { collapsed: boolean; onToggleCollapse: () => void }) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-sand-200/80 bg-canvas/80 px-6 backdrop-blur-md">
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={onToggleCollapse}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft transition-colors hover:bg-sand-100 hover:text-ink">
          {collapsed ? <PanelLeftOpenIcon className="h-4 w-4" /> : <PanelLeftIcon className="h-4 w-4" />}
        </button>
        <CommandPalette />
      </div>
      <div className="flex items-center gap-3">
        <MessagesBell />
        <PlanBadge />
        <Link
          to="/"
          className="hidden text-sm font-medium text-ink-muted transition-colors hover:text-ink sm:inline">

          Back to site
        </Link>
        <img
          src="/lets-scroll/avatar-doctor.png"
          alt="Practice account"
          className="h-9 w-9 rounded-full border border-sand-200 object-cover" />

      </div>
    </header>);

}
