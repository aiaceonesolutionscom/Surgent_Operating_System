import { useEffect, useRef, useState } from "react";
import { BotIcon, SendIcon, SparklesIcon } from "lucide-react";
import {
  askFinanceAgent, getFinanceAgentReport,
  type AskFinanceAgentResponse, type FinanceAgentReport,
} from "../../../api/financeAgent";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

const QUICK_PROMPTS = [
  "Revenue this month",
  "What each doctor earned",
  "Outstanding invoices",
  "AI agent costs",
];

// The Finance Agent chat card — ask the practice's money questions in plain
// language ("is month kis ko kitne paise mile?"). The backend answers from a
// real snapshot of invoices/expenses/doctors. Owner + Receptionist use this;
// the backend enforces the role gate.
export function FinanceAgentCard({ authedFetch }: { authedFetch: AuthedFetch }) {
  const [messages, setMessages] = useState<{ role: "staff" | "agent"; content: string }[]>([]);
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
  }, [messages]);

  async function send(text: string) {
    const value = text.trim();
    if (!authedFetch || !value || busy) return;
    setQuestion("");
    setMessages((m) => [...m, { role: "staff", content: value }]);
    setBusy(true);
    try {
      const res: AskFinanceAgentResponse = await askFinanceAgent(authedFetch, value, sessionId);
      setSessionId(res.session_id);
      setMessages((m) => [...m, { role: "agent", content: res.answer }]);
    } catch {
      setMessages((m) => [...m, { role: "agent", content: "Couldn't get an answer — try again in a moment." }]);
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
        {messages.length === 0 && (
          <p className="text-sm text-ink-muted">
            Try: <span className="text-ink">"Is month kis doctor ne kitne ka treatment kiya?"</span>
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${m.role === "staff" ? "ml-auto bg-teal-600 text-white" : "bg-sand-100 text-ink"}`}>
            <span className="whitespace-pre-wrap">{m.content}</span>
          </div>
        ))}
        {busy && <div className="w-fit rounded-2xl bg-sand-100 px-4 py-2.5 text-sm text-ink-muted">Thinking…</div>}
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