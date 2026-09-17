import { useEffect, useRef, useState } from "react";
import { SendIcon, SparklesIcon } from "lucide-react";
import { askSuperAgent, type AskSuperAgentResponse } from "../../../api/admin";

const QUICK_PROMPTS = [
  "How many clinics are active right now?",
  "What's our estimated MRR?",
  "Plan mix across practices?",
  "How many org requests are pending approval?",
];

// The Aiaceone-team Super Agent — the platform-owner counterpart to a clinic
// agent. It answers questions across ALL practices (MRR, plan mix, pending
// org requests) from live data, and is only reachable from the admin panel
// (backend enforce via require_admin_token). Answers are intentionally short.
export function SuperAgentPage() {
  const [messages, setMessages] = useState<{ role: "staff" | "agent"; content: string }[]>([]);
  const [question, setQuestion] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    const value = text.trim();
    if (!value || busy) return;
    setQuestion("");
    setError(null);
    setMessages((m) => [...m, { role: "staff", content: value }]);
    setBusy(true);
    try {
      const res: AskSuperAgentResponse = await askSuperAgent(value, sessionId);
      setSessionId(res.session_id);
      setMessages((m) => [...m, { role: "agent", content: res.answer }]);
    } catch {
      setError("Couldn't get an answer from the Super Agent — try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent-500">
            <SparklesIcon className="h-3.5 w-3.5" /> Super Agent
          </p>
          <h1 className="mt-1 font-display text-2xl font-bold text-ink">Ask the platform anything</h1>
          <p className="mt-1 max-w-xl text-sm text-ink-soft">
            Business questions about the whole book of clinics — live numbers from real practice, plan and
            signup data. Answers stay short and to the point.
          </p>
        </div>
      </div>

      {error && <p className="rounded-2xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm font-medium text-danger">{error}</p>}

      <div className="overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
        <div className="flex max-h-[520px] flex-col gap-3 overflow-y-auto px-5 py-4">
          {messages.length === 0 && (
            <p className="text-sm text-ink-muted">
              Click a quick question below, or type your own — e.g. "How is the platform doing?" in short,
              direct language.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${m.role === "staff" ? "ml-auto bg-accent-500 text-white" : "bg-sand-100 text-ink"}`}
            >
              <span className="whitespace-pre-wrap">{m.content}</span>
            </div>
          ))}
          {busy && <div className="w-fit rounded-2xl bg-sand-100 px-4 py-2.5 text-sm text-ink-muted">Thinking…</div>}
          <div ref={endRef} />
        </div>

        <div className="border-t border-sand-200 px-5 py-3">
          <div className="mb-2.5 flex flex-wrap gap-2">
            {QUICK_PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                disabled={busy}
                onClick={() => send(p)}
                className="rounded-full border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-accent-500 hover:text-accent-600 disabled:opacity-40"
              >
                {p}
              </button>
            ))}
          </div>
          <form onSubmit={(e) => { e.preventDefault(); send(question); }} className="flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask the Super Agent…"
              className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none placeholder:text-ink-muted focus:border-accent-500/50 focus:bg-white"
            />
            <button
              type="submit"
              disabled={busy || !question.trim()}
              className="flex items-center gap-1.5 rounded-xl bg-accent-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-600 disabled:opacity-40"
            >
              <SendIcon className="h-4 w-4" /> Ask
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}