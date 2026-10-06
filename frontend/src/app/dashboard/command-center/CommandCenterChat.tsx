import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { SparklesIcon, SendIcon, LockIcon, Loader2Icon, PlusIcon, MessageSquareIcon, CheckCircle2Icon } from "lucide-react";
import { DASHBOARD_ROUTES } from "../constants/routes";
import { usePlan } from "../plan/PlanContext";
import {
  askCommandCenterStream,
  listCommandCenterSessions,
  getCommandCenterSession,
  type CommandCenterStep,
  type CommandCenterSessionSummary
} from "../../../api/commandCenter";
import { AGENT_CATEGORIES } from "../../../data/agents";
import { minTierForCategory, planFor } from "../plan/plan";

const CATEGORY_ICON: Record<string, (typeof AGENT_CATEGORIES)[number]["agents"][number]["icon"]> = Object.fromEntries(
  AGENT_CATEGORIES.map((c) => [c.id, c.agents[0].icon])
);

interface Turn {
  id: string;
  question: string;
  allSteps: CommandCenterStep[];
  revealedCount: number;
  answer: string | null;
  error: string | null;
}

function turnsFromSession(messages: { role: "staff" | "agent"; content: string; steps: CommandCenterStep[] }[]): Turn[] {
  const turns: Turn[] = [];
  let pending: Turn | null = null;
  messages.forEach((m, i) => {
    if (m.role === "staff") {
      pending = { id: `h${i}`, question: m.content, allSteps: [], revealedCount: 0, answer: null, error: null };
      turns.push(pending);
    } else if (pending) {
      pending.allSteps = m.steps;
      pending.revealedCount = m.steps.length;
      pending.answer = m.content;
    }
  });
  return turns;
}

export function CommandCenterChat() {
  const { authedFetch, authedFetchStream } = usePlan();
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sessions, setSessions] = useState<CommandCenterSessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);

  const refreshSessions = useCallback(async () => {
    if (!authedFetch) return;
    try {
      const list = await listCommandCenterSessions(authedFetch);
      setSessions(list);
    } catch {
      // Sessions sidebar is a convenience — a failed fetch just leaves it empty, doesn't block chat.
    }
  }, [authedFetch]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

  async function openSession(id: string) {
    if (!authedFetch || id === activeSessionId) return;
    setLoadingSession(true);
    setActiveSessionId(id);
    try {
      const detail = await getCommandCenterSession(authedFetch, id);
      setTurns(turnsFromSession(detail.messages));
    } catch {
      setTurns([]);
    } finally {
      setLoadingSession(false);
    }
  }

  function startNewChat() {
    setActiveSessionId(null);
    setTurns([]);
  }

  // Takes the question as an argument rather than reading `question` from
  // state, because the suggestion chips call this directly. They used to do
  // `setQuestion(q); handleSubmit(...)` in the same tick, but a state setter
  // doesn't apply until the next render — so `handleSubmit` still closed over
  // the *previous* `question` and sent nothing (or the wrong text) whenever
  // the box was empty. Passing the text in makes the call correct regardless
  // of render timing.
  async function sendQuestion(text: string) {
    const q = text.trim();
    if (!q || sending || !authedFetchStream) return;

    const id = `t${Date.now()}`;
    setTurns((prev) => [...prev, { id, question: q, allSteps: [], revealedCount: 0, answer: null, error: null }]);
    setQuestion("");
    setSending(true);

    try {
      for await (const ev of askCommandCenterStream(authedFetchStream, q, activeSessionId)) {
        if (ev.type === "step") {
          setTurns((prev) =>
            prev.map((t) => (t.id === id ? { ...t, allSteps: [...t.allSteps, ev.step], revealedCount: t.allSteps.length + 1 } : t))
          );
        } else if (ev.type === "chunk") {
          setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, answer: (t.answer ?? "") + ev.text } : t)));
        } else if (ev.type === "done") {
          if (!activeSessionId) setActiveSessionId(ev.session_id);
          refreshSessions();
        } else if (ev.type === "error") {
          setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, error: ev.message } : t)));
        }
      }
    } catch {
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, error: "Couldn't reach the Command Center — please try again." } : t))
      );
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    void sendQuestion(question);
  }

  const lastTurnId = turns.length > 0 ? turns[turns.length - 1].id : null;

  return (
    <div className="flex h-full min-h-0 overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="hidden w-56 shrink-0 flex-col border-r border-sand-200 bg-sand-100/50 sm:flex">
        <div className="p-3">
          <button
            onClick={startNewChat}
            className="flex w-full items-center gap-2 rounded-xl bg-teal-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-teal-700">
            <PlusIcon className="h-4 w-4" /> New chat
          </button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto px-2 pb-3">
          {sessions.length === 0 && <p className="px-2 py-2 text-xs text-ink-muted">No past sessions yet.</p>}
          {sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => openSession(s.id)}
              className={`flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                s.id === activeSessionId ? "bg-teal-600/10 text-teal-700" : "text-ink-soft hover:bg-white"
              }`}>
              <MessageSquareIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{s.title}</span>
                <span className="block text-[10px] text-ink-muted">{new Date(s.updated_at).toLocaleString()}</span>
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-6 py-5">
          {loadingSession && <p className="text-sm text-ink-muted">Loading session…</p>}

          {!loadingSession && turns.length === 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="flex flex-col items-center justify-center py-12 text-center"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-600">
                <SparklesIcon className="h-7 w-7" />
              </div>
              <p className="mt-5 text-base font-medium text-ink">Ask the Main Agent anything</p>
              <p className="mt-2 max-w-md text-sm text-ink-muted">
                Try "Which patients need surgery?" or "What's overdue on billing?" — the Main Agent
                will consult the right agent(s) for you, and you'll see exactly which ones.
              </p>
              <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
                {[
                  "Which patients need attention?",
                  "What's our revenue this month?",
                  "Show me upcoming surgeries",
                  "Any recovery flags?"
                ].map((q, i) => (
                  <button
                    key={i}
                    onClick={() => { setQuestion(q); void sendQuestion(q); }}
                    disabled={sending || !authedFetchStream}
                    className="rounded-xl border border-sand-200 bg-white px-3 py-2 text-xs font-medium text-ink-soft hover:border-teal-400 hover:bg-teal-50 transition-all disabled:opacity-50"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          {!loadingSession && turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[75%] rounded-2xl bg-teal-600 px-4 py-2.5 text-sm leading-relaxed text-white">
                  {t.question}
                </div>
              </div>

              <AnimatePresence>
                {t.allSteps.slice(0, t.revealedCount).map((step, idx) => {
                  const Icon = CATEGORY_ICON[step.category_id] ?? SparklesIcon;
                  const isComplete = step.status === "consulted";
                  return (
                    <motion.div
                      key={step.category_id}
                      initial={{ opacity: 0, x: -20, y: 10 }}
                      animate={{ opacity: 1, x: 0, y: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: idx * 0.15, duration: 0.3 }}
                      className="flex justify-start"
                    >
                      <div className={`flex max-w-[85%] items-start gap-2.5 rounded-2xl px-4 py-2.5 text-sm text-ink-soft transition-all ${
                        isComplete ? "bg-teal-50 border border-teal-200" : "bg-sand-100"
                      }`}>
                        <span
                          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${
                            step.status === "locked" ? "bg-warning/10 text-warning" : isComplete ? "bg-teal-100 text-teal-600" : "bg-teal-600/10 text-teal-600"
                          }`}
                        >
                          {step.status === "locked" ? (
                            <LockIcon className="h-3.5 w-3.5" />
                          ) : isComplete ? (
                            <CheckCircle2Icon className="h-3.5 w-3.5" />
                          ) : (
                            <Icon className="h-3.5 w-3.5" />
                          )}
                        </span>
                        <div>
                          <p className="font-semibold text-ink">Asked {step.category_label}</p>
                          <p className="mt-0.5 text-ink-muted">{step.summary}</p>
                          {step.status === "locked" && (
                            <Link
                              to={DASHBOARD_ROUTES.settingsBilling}
                              className="mt-1 inline-block text-xs font-semibold text-teal-600 hover:underline"
                            >
                              Included in {planFor(minTierForCategory(step.category_id) || "enterprise").name} — upgrade
                            </Link>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>

              {sending && t.id === lastTurnId && t.answer === null && !t.error && (
                <div className="flex items-center gap-2 text-xs text-ink-muted">
                  <Loader2Icon className="h-3.5 w-3.5 animate-spin" /> Consulting…
                </div>
              )}

              {t.error && <p className="text-sm text-danger">{t.error}</p>}

              <AnimatePresence>
                {t.answer !== null && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.3 }}
                    className="flex justify-start"
                  >
                    <div className="flex max-w-[85%] items-start gap-2.5 rounded-2xl border border-teal-600/20 bg-white px-4 py-3 text-sm leading-relaxed text-ink">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white">
                        <SparklesIcon className="h-3.5 w-3.5" />
                      </span>
                      <span>
                        {t.answer}
                        {sending && t.id === lastTurnId && (
                          <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-ink-muted/60 align-middle" />
                        )}
                      </span>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex items-end gap-3 border-t border-sand-200 px-5 py-4">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={1}
            placeholder={authedFetch ? "Ask the Main Agent…" : "Sign in to use the Command Center"}
            disabled={!authedFetch || sending}
            className="w-full resize-none rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white disabled:cursor-not-allowed disabled:opacity-60" />

          <button
            type="submit"
            disabled={!authedFetch || sending || !question.trim()}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-teal-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
            {sending ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <SendIcon className="h-4 w-4" />}
            Ask
          </button>
        </form>
      </div>
    </div>
  );
}