import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { PlanProvider } from "../plan/PlanContext";

const COLLAPSE_KEY = "aesthetixai_sidebar_collapsed";

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

// Shell for every /dashboard/* screen — sidebar + topbar per
// design-references/For.UI/clinical_ethereal/DESIGN.md (fixed 280px sidebar,
// cool-gray surface). Auth-gating is deferred to a later phase (see
// app/dashboard/README.md) — this is reachable without sign-in for now.
// PlanProvider wraps everything below here so Sidebar/Topbar/every page share
// one plan-tier resolution instead of each mounting its own (see plan/README.md).
export function DashboardLayout() {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const toggleCollapsed = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        // ignore storage failures
      }
      return next;
    });
  };

  return (
    <PlanProvider>
      <div className="min-h-screen bg-canvas font-sans text-ink">
        <Sidebar collapsed={collapsed} />
        <div className={collapsed ? "lg:pl-[72px]" : "lg:pl-[280px]"}>
          <Topbar collapsed={collapsed} onToggleCollapse={toggleCollapsed} />
          <main className="mx-auto max-w-[1440px] px-6 py-8">
            <Outlet />
          </main>
        </div>
      </div>
    </PlanProvider>);

}
