import { useState } from "react";
import { SparklesIcon, ArrowLeftIcon, MessageSquareIcon } from "lucide-react";
import type { Session } from "../sessions/types";
import { AICommandCenterCompact } from "./AICommandCenterCompact";

interface Insight {
  label: string;
  value: string;
}

function computeInsights(sessions: Session[]): Insight[] {
  const total = sessions.length;
  const active = sessions.filter((s) => s.status === "active").length;
  const needsAttention = sessions.filter((s) => s.status === "needs_attention").length;
  const resolved = sessions.filter((s) => s.status === "resolved").length;
  const resolvedRate = total > 0 ? Math.round((resolved / total) * 100) : 0;

  return [
  { label: "Live AI sessions", value: `${active} active` },
  { label: "Needs attention", value: `${needsAttention} session${needsAttention === 1 ? "" : "s"}` },
  { label: "Resolved rate", value: `${resolvedRate}% of ${total}` }];

}

// The dark "AI Insights" panel from design-references/For.UI/aiaceone_executive_dashboard.
//
// One fixed-size box (w-[340px], same rounded-[28px] bg-[#15171A] shell) for
// BOTH modes — insights and chat share this exact wrapper instead of each
// rendering their own, so opening the chat never changes the panel's width,
// height, or theme (it used to jump to a wide white card — fixed here).
// `self-start` (set by the caller, OverviewPage.tsx) keeps the box hugging
// its own content height instead of flex-stretching to match the taller
// sibling column next to it.
type PanelMode = "insights" | "chat";

export function AIInsightsPanel({ sessions }: { sessions: Session[] }) {
  const insights = computeInsights(sessions);
  const [mode, setMode] = useState<PanelMode>("insights");

  return (
    <div className="relative flex w-[340px] shrink-0 flex-col gap-5 overflow-hidden rounded-[28px] bg-[#15171A] p-6 shadow-[0_20px_50px_-20px_rgba(11,29,38,0.5)]">
      {mode === "insights" &&
      <SparklesIcon className="pointer-events-none absolute -right-4 -top-4 h-28 w-28 text-white/[0.06]" strokeWidth={1} />
      }

      <div className="relative flex items-center justify-between">
        {mode === "chat" ?
        <button
          onClick={() => setMode("insights")}
          className="flex items-center gap-1.5 text-sm font-semibold text-white/70 transition-colors hover:text-white">

            <ArrowLeftIcon className="h-4 w-4" /> Insights
          </button> :

        <h3 className="font-display text-lg font-600 text-white">AI Insights</h3>
        }
        <span className="h-2 w-2 rounded-full bg-success" />
      </div>

      {mode === "insights" ?
      <>
          <div className="relative flex flex-col gap-2.5">
            {insights.map((i) =>
          <div key={i.label} className="flex items-center justify-between rounded-2xl bg-white/[0.08] px-4 py-3.5 transition-colors hover:bg-white/[0.12]">
                <div>
                  <p className="text-xs text-white/50">{i.label}</p>
                  <p className="mt-0.5 text-sm font-semibold text-white">{i.value}</p>
                </div>
              </div>
          )}
          </div>

          {/* Opens inline inside this same box — never a modal or new page. */}
          <button
          onClick={() => setMode("chat")}
          className="relative flex items-center justify-center gap-1.5 rounded-xl bg-accent-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

            <MessageSquareIcon className="h-4 w-4" /> Open AI Command Center
          </button>
        </> :

      <AICommandCenterCompact />
      }
    </div>);

}
