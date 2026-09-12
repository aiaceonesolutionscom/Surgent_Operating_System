import React, { useEffect, useRef, useState } from "react";
import {
  InboxIcon,
  SendIcon,
  CheckCircle2Icon,
  MessageCircleIcon,
  LockIcon,
  LoaderIcon,
} from "lucide-react";
import { EmptyState } from "../components/EmptyState";
import type { ConversationListItem } from "../../../api/entities";

function formatTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function initials(name: string | null) {
  return (name || "?")[0]?.toUpperCase() || "?";
}

export function PatientMessagesTab({
  conversations,
  active,
  messages,
  canReply,
  loading,
  onSelect,
  onSend,
  onResolve,
}: {
  conversations: ConversationListItem[];
  active: ConversationListItem | null;
  messages: Array<{ id: string; role: string; content: string; created_at: string }>;
  canReply: boolean;
  loading: boolean;
  onSelect: (id: string) => void;
  onSend: (body: string) => Promise<unknown>;
  onResolve: () => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [resolving, setResolving] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, active?.id]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setSending(true);
    try {
      await onSend(draft.trim());
      setDraft("");
    } finally {
      setSending(false);
    }
  }

  async function handleResolve() {
    setResolving(true);
    try {
      await onResolve();
    } finally {
      setResolving(false);
    }
  }

  return (
    <div className="grid h-full grid-cols-[340px_1fr]">
      {/* --- Left: patient list --- */}
      <aside className="flex flex-col overflow-hidden border-r border-sand-200">
        <div className="flex items-center justify-between border-b border-sand-200 px-4 py-3.5">
          <p className="text-sm font-bold text-ink">Patients</p>
          <span className="rounded-full bg-sand-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            {conversations.length}
          </span>
        </div>
        <div className="flex-1 divide-y divide-sand-100 overflow-y-auto">
          {loading ?
          <p className="px-4 py-6 text-center text-sm text-ink-muted">Loading…</p> :
          conversations.length === 0 ?
          <div className="flex h-full items-center justify-center p-4">
            <EmptyState icon={InboxIcon} title="No patient messages yet" body="Portal messages your patients send their doctor will appear here." />
          </div> :
          conversations.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelect(c.id)}
              className={`flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors ${active?.id === c.id ? "bg-teal-600/[0.06]" : "hover:bg-sand-50"}`}>
              <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold ${active?.id === c.id ? "bg-teal-600/15 text-teal-600" : "bg-sand-200 text-ink-soft"}`}>
                {initials(c.patient_name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-ink">{c.patient_name}</span>
                  {c.status === "needs_attention" && <span className="h-2 w-2 shrink-0 rounded-full bg-danger" />}
                </span>
                <span className="block truncate text-xs text-ink-muted">{c.last_message_preview || "No messages yet"}</span>
              </span>
              <span className="shrink-0 text-[11px] text-ink-muted">{formatTime(c.updated_at)}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* --- Right: thread --- */}
      <main className="flex min-w-0 flex-col overflow-hidden bg-white">
        {active ? (
          <>
            <div className="flex items-center gap-3 border-b border-sand-200 px-5 py-4">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-600/10 text-sm font-bold text-teal-600">
                {initials(active.patient_name)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-ink">{active.patient_name}</p>
                <p className="truncate text-xs text-ink-muted">
                  {active.status === "needs_attention" ? "Needs attention" : "Active"}
                  {!canReply && " · Read-only for you"}
                </p>
              </div>
              {active.status === "needs_attention" && canReply && (
                <button
                  type="button"
                  disabled={resolving}
                  onClick={handleResolve}
                  className="flex items-center gap-1.5 rounded-lg border border-sand-200 px-3 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:border-success/40 hover:text-success disabled:opacity-50">
                  <CheckCircle2Icon className="h-3.5 w-3.5" /> {resolving ? "Marking…" : "Mark resolved"}
                </button>
              )}
            </div>

            <div className="flex-1 space-y-1 overflow-y-auto bg-sand-50/40 px-5 py-4">
              {messages.length === 0 ?
              <div className="flex h-full items-center justify-center">
                <EmptyState icon={MessageCircleIcon} title="No messages yet" body={`${active.patient_name} hasn't messaged you yet.`} />
              </div> :
              messages.map((m) => {
                const fromPatient = m.role === "patient";
                return (
                  <div key={m.id} className={`flex ${fromPatient ? "justify-start" : "justify-end"} mt-2.5`}>
                    <div className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${fromPatient ? "border border-sand-200 bg-white text-ink" : "bg-teal-600 text-white"}`}>
                      {!fromPatient && m.role === "staff" && <p className="mb-0.5 text-[10px] font-semibold text-white/70">Staff</p>}
                      <p className="text-sm leading-relaxed">{m.content}</p>
                      <p className={`mt-1 text-[10px] ${fromPatient ? "text-ink-muted" : "text-white/70"}`}>
                        {new Date(m.created_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}
                      </p>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>

            {!canReply ? (
              <div className="flex items-center gap-2 border-t border-sand-200 bg-sand-50/60 px-5 py-3.5">
                <LockIcon className="h-4 w-4 text-ink-muted" />
                <p className="text-xs text-ink-muted">You have read-only access — the assigned doctor or receptionist answers this patient.</p>
              </div>
            ) : (
              <form onSubmit={submit} className="flex items-center gap-2.5 border-t border-sand-200 px-4 py-3.5">
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="Reply to this patient…"
                  className="flex-1 rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-600/40 focus:bg-white" />
                <button
                  type="submit"
                  disabled={sending || !draft.trim()}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-teal-600 text-white transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-40">
                  <SendIcon className="h-4 w-4" />
                </button>
              </form>
            )}
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center p-6">
            {conversations.length > 0 ?
            <EmptyState icon={MessageCircleIcon} title="Pick a patient" body="Select a patient on the left to read and reply to their message." /> :
            <EmptyState icon={LoaderIcon} title="No patient messages" body="When your patients message you from the portal, they'll land here and in their Communication tab." />
            }
          </div>
        )}
      </main>
    </div>
  );
}