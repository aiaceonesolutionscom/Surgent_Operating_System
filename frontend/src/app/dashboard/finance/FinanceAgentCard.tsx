import { useEffect, useRef, useState } from "react";
import { BotIcon, SendIcon, SparklesIcon, Loader2Icon } from "lucide-react";
import {
  askFinanceAgentStream, getFinanceAgentReport,
  type FinanceAgentReport, type FinanceAgentStep,
} from "../../../api/financeAgent";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;
type AuthedFetchStream = (<T = Record<string, unknown>>(path: string, init?: RequestInit) => AsyncGenerator<T>) | null;

const QUICK_PROMPTS = [
  "Revenue this month",
  "What each doctor earned",
  "Outstanding invoices",
  "AI agent costs",
];

interface ChatTurn {
  id: number;
  role: "staff" | "agent";
  content: string;
  steps: FinanceAgentStep[];
  streaming?: boolean;
}

// The Finance Agent chat card — ask the practice's money questions in plain
// language ("is month kis ko kitne paise mile?"). The backend picks which
// get_* tool(s) actually answer the question (not one giant snapshot every
// time — see finance_agent_services.py) and streams the answer live via
// SSE, same "consulting X…" step reveal + token-by-token pattern as Command
// Center. Owner + Receptionist use this; the backend enforces the role gate.
export function FinanceAgentCard({ authedFetch, authedFetchStream }: { authedFetch: AuthedFetch; authedFetchStream: AuthedFetchStream }) {
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [report, setReport] = useState<FinanceAgentReport | null>(null);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!authedFetch) return;
    getFinanceAgentReport(authedFetch).then(setReport).catch(() => setReport(null));
  }, [authedFetch]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function send(text: string) {
    const value = text.trim();
    if (!authedFetchStream || !value || busy) return;
    setQuestion("");
    setTurns((t) => [...t, { id: Date.now(), role: "staff", content: value, steps: [] }]);
    const agentId = Date.now() + 1;
    setTurns((t) => [...t, { id: agentId, role: "agent", content: "", steps: [], streaming: true }]);
    setBusy(true);
    try {
      for await (const ev of askFinanceAgentStream(authedFetchStream, value, sessionId)) {
        if (ev.type === "step") {
          setTurns((t) => t.map((turn) => (turn.id === agentId ? { ...turn, steps: [...turn.steps, ev.step] } : turn)));
        } else if (ev.type === "chunk") {
          setTurns((t) => t.map((turn) => (turn.id === agentId ? { ...turn, content: turn.content + ev.text } : turn)));
        } else if (ev.type === "done") {
          setSessionId(ev.session_id);
          setTurns((t) => t.map((turn) => (turn.id === agentId ? { ...turn, streaming: false } : turn)));
        } else if (ev.type === "error") {
          setTurns((t) => t.map((turn) => (turn.id === agentId ? { ...turn, content: ev.message, streaming: false } : turn)));
        }
      }
    } catch {
      setTurns((t) =>
        t.map((turn) => (turn.id === agentId ? { ...turn, content: "Couldn't get an answer — try again in a moment.", streaming: false } : turn))
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mt-6 overflow-hidden rounded-3xl border border-sand-200 bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-sand-100 bg-gradient-to-r from-teal-600/8 to-transparent px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-teal-600/10 text-teal-600">
            <BotIcon className="h-5 w-5" />
          </span>
          <div>
            <p className="flex items-center gap-1.5 text-sm font-bold text-ink">
              Finance Agent <SparklesIcon className="h-3.5 w-3.5 text-teal-600" />
            </p>
            <p className="text-xs text-ink-muted">
              Ask about revenue, spending, outstanding invoices, each doctor's earnings or AI costs —
              {report ? ` ${report.month_label}: revenue ${fmt(report.total_revenue)}, net ${fmt(report.net)}.` : " powered by your live practice data."}
            </p>
          </div>
        </div>
      </div>

      <div className="flex max-h-80 flex-col gap-3 overflow-y-auto px-5 py-4">
        {turns.length === 0 && (
          <p className="text-sm text-ink-muted">
            Try: <span className="text-ink">"Is month kis doctor ne kitne ka treatment kiya?"</span>
          </p>
        )}
        {turns.map((t) => (
          <div key={t.id} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${t.role === "staff" ? "ml-auto bg-teal-600 text-white" : "bg-sand-100 text-ink"}`}>
            {t.role === "agent" && t.steps.length > 0 && (
              <div className="mb-1.5 flex flex-wrap gap-1.5">
                {t.steps.map((s, i) => (
                  <span key={i} className="rounded-full bg-teal-600/10 px-2 py-0.5 text-[11px] font-semibold text-teal-700">
                    {s.tool_label}
                  </span>
                ))}
              </div>
            )}
            {t.role === "agent" && t.streaming && !t.content && t.steps.length === 0 ? (
              <span className="flex items-center gap-1.5 text-ink-muted">
                <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> Thinking…
              </span>
            ) : (
              <span className="whitespace-pre-wrap">
                {t.content}
                {t.streaming && <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-ink-muted/60 align-middle" />}
              </span>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="border-t border-sand-100 px-5 py-3">
        <div className="mb-2.5 flex flex-wrap gap-2">
          {QUICK_PROMPTS.map((p) => (
            <button
              key={p}
              type="button"
              disabled={busy}
              onClick={() => send(p)}
              className="rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600 disabled:opacity-40"
            >
              {p}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); send(question); }}
          className="flex gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask the Finance Agent…"
            className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal-600/40 focus:bg-white"
          />
          <button
            type="submit"
            disabled={busy || !question.trim()}
            className="flex items-center gap-1.5 rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-40"
          >
            <SendIcon className="h-4 w-4" /> Ask
          </button>
        </form>
      </div>
    </section>
  );
}

function fmt(n: number) {
  return "$" + (n || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}