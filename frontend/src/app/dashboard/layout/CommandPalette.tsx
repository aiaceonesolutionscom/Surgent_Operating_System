import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SearchIcon, LockIcon } from "lucide-react";
import { AGENT_CATEGORIES } from "../../../data/agents";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";

interface Command {
  label: string;
  hint: string;
  to: string;
  locked?: boolean;
}


// A real, working Cmd+K launcher (per design-references/.../DESIGN.md's
// "Command Palette" spec) — not a decorative shortcut hint.
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const navigate = useNavigate();
  const { allowsCategory, can } = usePlan();

  const COMMANDS: Command[] = useMemo(() => [
  { label: "Overview", hint: "Dashboard home", to: DASHBOARD_ROUTES.overview },
  { label: "All conversations", hint: "Agent sessions", to: DASHBOARD_ROUTES.sessionsAll },
  { label: "Needs attention", hint: "Escalated sessions", to: DASHBOARD_ROUTES.sessionsNeedsAttention },
  { label: "Patients", hint: "Patient records", to: DASHBOARD_ROUTES.patients },
  ...AGENT_CATEGORIES.map((c) => ({
    label: c.label,
    hint: "Agent category",
    to: DASHBOARD_ROUTES.agentCategory(c.id),
    locked: !allowsCategory(c.id)
  })),
  { label: "Analytics", hint: "Practice metrics", to: DASHBOARD_ROUTES.analytics, locked: !can("analytics") },
  { label: "Agent settings", hint: "Configure agents", to: DASHBOARD_ROUTES.settingsAgents },
  { label: "Profile", hint: "Practice & account", to: DASHBOARD_ROUTES.settingsProfile },
  { label: "Plan & billing", hint: "Current plan", to: DASHBOARD_ROUTES.settingsBilling }],
  [allowsCategory, can]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setActiveIndex(0);
    }
  }, [open]);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return COMMANDS;
    return COMMANDS.filter((c) => c.label.toLowerCase().includes(q));
  }, [query]);

  const go = (to: string) => {
    navigate(to);
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="flex items-center gap-2.5 rounded-lg border border-sand-200 bg-white px-3.5 py-2 text-sm text-ink-muted transition-colors hover:border-accent-500/30 hover:text-ink">

        <SearchIcon className="h-4 w-4" />
        <span className="hidden sm:inline">Search patients, sessions, settings…</span>
        <span className="ml-1 hidden rounded border border-sand-200 px-1.5 py-0.5 text-[11px] font-semibold text-ink-muted sm:inline">
          ⌘K
        </span>
      </button>);

  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/40 pt-[15vh]" onClick={() => setOpen(false)}>
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-white/60 bg-white/90 shadow-2xl backdrop-blur-xl"
        onClick={(e) => e.stopPropagation()}>

        <div className="flex items-center gap-2.5 border-b border-sand-200 px-4 py-3.5">
          <SearchIcon className="h-4.5 w-4.5 text-ink-muted" />
          <input
            autoFocus
            value={query}
            onChange={(e) => {setQuery(e.target.value);setActiveIndex(0);}}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {e.preventDefault();setActiveIndex((i) => Math.min(i + 1, results.length - 1));}
              if (e.key === "ArrowUp") {e.preventDefault();setActiveIndex((i) => Math.max(i - 1, 0));}
              if (e.key === "Enter" && results[activeIndex]) go(results[activeIndex].to);
            }}
            placeholder="Search patients, sessions, settings…"
            className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />

        </div>
        <div className="max-h-80 overflow-y-auto p-2">
          {results.length === 0 &&
          <p className="px-3 py-6 text-center text-sm text-ink-muted">No matches.</p>
          }
          {results.map((c, i) =>
          <button
            key={c.to}
            onClick={() => go(c.to)}
            onMouseEnter={() => setActiveIndex(i)}
            className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
            i === activeIndex ? "bg-accent-500/8 text-ink" : "text-ink-soft"}`
            }>

              <span className={`font-medium ${c.locked ? "text-ink-muted" : ""}`}>{c.label}</span>
              <span className="flex items-center gap-1 text-xs text-ink-muted">
                {c.locked && <LockIcon className="h-3 w-3" />}
                {c.locked ? "Upgrade required" : c.hint}
              </span>
            </button>
          )}
        </div>
      </div>
    </div>);

}
