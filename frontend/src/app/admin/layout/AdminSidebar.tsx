import React from "react";
import { NavLink } from "react-router-dom";
import { LayoutDashboardIcon, Building2Icon, CreditCardIcon, InboxIcon, UserPlusIcon, BotIcon } from "lucide-react";
import { ADMIN_ROUTES } from "../constants/routes";
import { Logo } from "../../../components/ui";

interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  end?: boolean;
}

const ITEMS: NavItem[] = [
{ label: "Overview", to: ADMIN_ROUTES.overview, icon: LayoutDashboardIcon, end: true },
{ label: "Clinics", to: ADMIN_ROUTES.clinics, icon: Building2Icon },
{ label: "New organizations", to: ADMIN_ROUTES.orgRequests, icon: UserPlusIcon },
{ label: "Plans & Pricing", to: ADMIN_ROUTES.plans, icon: CreditCardIcon },
{ label: "Sales Leads", to: ADMIN_ROUTES.salesLeads, icon: InboxIcon },
{ label: "Super Agent", to: ADMIN_ROUTES.superAgent, icon: BotIcon }];


// Dark sidebar (bg-panel) — the inverse of the doctor dashboard's light
// Sidebar.tsx, deliberately: the chrome itself should signal "this is
// platform control," not just the content. See app/admin/README.md.
export function AdminSidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-[260px] flex-col bg-panel lg:flex">
      <div className="flex h-16 items-center gap-2.5 border-b border-white/10 px-6">
        <span className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-accent-500">
          <Logo className="h-4.5 w-4.5" />
        </span>
        <div className="leading-tight">
          <p className="text-[15px] font-bold tracking-tight text-white">Aiaceone</p>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/40">Super Admin Panel</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-4 py-5">
        <div className="space-y-0.5">
          {ITEMS.map((item) =>
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
            `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
            isActive ? "bg-accent-500/15 text-accent-400" : "text-white/70 hover:bg-white/5 hover:text-white"}`
            }>

              {({ isActive }) =>
            <>
                  {isActive &&
              <span className="absolute left-0 top-1/2 h-4 w-[3px] -translate-y-1/2 rounded-full bg-accent-500" />
              }
                  <item.icon className="h-4 w-4 shrink-0" />
                  <span className="flex-1 truncate">{item.label}</span>
                </>
            }
            </NavLink>
          )}
        </div>
      </nav>
    </aside>);

}
