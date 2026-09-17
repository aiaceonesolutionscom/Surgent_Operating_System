import React, { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { SendIcon, SparklesIcon, XIcon } from "lucide-react";
import { sendLandingChatMessage } from "../../api/entities";

export interface HeroChatSeed {
  eyebrow: string;
  title: string;
  body: string;
}

interface ChatMessage {
  id: number;
  role: "user" | "bot" | "lead";
  text: string;
}

interface LandingChatProps {
  open: boolean;
  seed: HeroChatSeed | null;
  onClose: () => void;
  onSeedConsumed: () => void;
}

// "Aria" is the landing-page AI assistant (named in
// backend/src/services/landing_chat/landing_chat_service.py). The conversation
// id + thread are kept in sessionStorage so closing/reopening the chat (or a
// page refresh) continues the same conversation.
const CONV_KEY = "aria_conv_id";
const MSGS_KEY = "aria_msgs";

function loadMessages(): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(MSGS_KEY);
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function formatSeed(seed: HeroChatSeed): string {
  return [seed.eyebrow, seed.title, seed.body].filter(Boolean).join(" — ");
}

export function LandingChat({ open, seed, onClose, onSeedConsumed }: LandingChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(loadMessages);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [convId, setConvId] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(CONV_KEY);
    } catch {
      return null;
    }
  });
  const convIdRef = useRef(convId);
  const pendingRef = useRef(false);
  const seedHandledRef = useRef<string | null>(null);
  const seedContextRef = useRef<string | undefined>(undefined);
  const greetedRef = useRef(messages.length > 0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    sessionStorage.setItem(MSGS_KEY, JSON.stringify(messages.slice(0, 60)));
  }, [messages]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending, open]);

  const send = useCallback(
    async (text: string, context?: string) => {
      // pendingRef (not the `sending` state) is the real in-flight guard so two
      // calls in the same tick (e.g. a seeded hero message) can't both pass.
      const trimmed = text.trim();
      if (!trimmed || pendingRef.current) return;
      pendingRef.current = true;
      setSending(true);
      setMessages((prev) => [...prev, { id: Date.now(), role: "user", text: trimmed }]);
      setInput("");
      try {
        const res = await sendLandingChatMessage({
          conversation_id: convIdRef.current,
          message: trimmed,
          context: convIdRef.current ? undefined : context
        });
        convIdRef.current = res.conversation_id;
        setConvId(res.conversation_id);
        sessionStorage.setItem(CONV_KEY, res.conversation_id);
        setMessages((prev) => [...prev, { id: Date.now() + 1, role: "bot", text: res.reply }]);
        if (res.booking_created) {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now() + 2,
              role: "lead",
              text: `Request received${res.lead_name ? ` — thanks, ${res.lead_name}` : ""}! Our receptionist team will reach out to book your consultation.`
            }
          ]);
        }
        if (res.sales_lead_created) {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now() + 2,
              role: "lead",
              text: `Thanks, ${res.sales_lead_name || "there"}! Your request has been logged and a member of the Aiaceone team will reach out to you shortly.`
            }
          ]);
        }
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: Date.now() + 1, role: "bot", text: "Sorry, I hit a snag — please try again in a moment." }
        ]);
      } finally {
        pendingRef.current = false;
        setSending(false);
      }
    },
    []
  );

  useEffect(() => {
    if (!open) return;
    if (!greetedRef.current) {
      greetedRef.current = true;
      setMessages((prev) =>
        prev.length === 0
          ? [
              {
                id: 0,
                role: "bot",
                text: "Hi, I'm Aria — the Aiaceone assistant. Booking a consultation, or exploring Aiaceone for your own clinic? I can help with both."
              }
            ]
          : prev
      );
    }
    if (seed && seedHandledRef.current !== seed.title) {
      seedHandledRef.current = seed.title;
      seedContextRef.current = seed.title;
      const topic = formatSeed(seed);
      void send(topic, seed.title);
      onSeedConsumed();
    }
  }, [open, seed, onSeedConsumed, send]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void send(input);
  };

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="fixed bottom-24 right-4 z-[60] flex h-[520px] max-h-[72vh] w-[min(92vw,380px)] flex-col overflow-hidden rounded-2xl border border-sand-200 bg-white shadow-2xl sm:right-6">
            <div className="flex items-center gap-3 bg-teal-600 px-4 py-3 text-white">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white/15">
                <SparklesIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-bold leading-tight">Aria</p>
                <p className="truncate text-xs text-teal-100">AI receptionist · website chat</p>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close chat"
                className="ml-auto grid h-8 w-8 place-items-center rounded-full transition-colors hover:bg-white/15">
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-canvas px-4 py-4">
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="ml-auto max-w-[82%] rounded-2xl rounded-br-md bg-teal-600 px-3.5 py-2 text-sm leading-relaxed text-white">
                    {m.text}
                  </div>
                ) : m.role === "lead" ? (
                  <div key={m.id} className="mr-auto max-w-[85%] rounded-2xl rounded-bl-md border border-teal-200 bg-teal-50 px-3.5 py-2 text-sm leading-relaxed text-teal-900">
                    {m.text}
                  </div>
                ) : (
                  <div key={m.id} className="mr-auto max-w-[85%] whitespace-pre-line rounded-2xl rounded-bl-md border border-sand-200 bg-white px-3.5 py-2 text-sm leading-relaxed text-ink">
                    {m.text}
                  </div>
                )
              )}
              {sending && (
                <div className="mr-auto flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-sand-200 bg-white px-4 py-3">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-teal-600/60" style={{ animationDelay: `${i * 0.12}s` }} />
                  ))}
                </div>
              )}
            </div>

            <form onSubmit={handleSubmit} className="flex items-center gap-2 border-t border-sand-200 bg-white px-3 py-2.5">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={sending}
                placeholder="Ask Aria anything…"
                className="min-w-0 flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={sending || !input.trim()}
                aria-label="Send message"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
                <SendIcon className="h-4 w-4" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}