import { useEffect, useState } from "react";
import { CHANNELS, type ChannelId } from "../data/channels";
import { usePlan } from "../plan/PlanContext";
import { listConversations, type ConversationListItem } from "../../../api/entities";

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export function LiveTranscriptsList() {
  const { authedFetch } = usePlan();
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);

  useEffect(() => {
    if (!authedFetch) return;
    let cancelled = false;
    const load = async () => {
      try {
        const data = await listConversations(authedFetch, { limit: 10 });
        if (!cancelled) setConversations(data);
      } catch {
        // silent
      }
    };
    void load();
    const t = setInterval(() => void load(), 30_000);
    return () => { cancelled = true; clearInterval(t); };
  }, [authedFetch]);

  return (
    <div className="rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)]">
      <div className="flex items-center justify-between border-b border-sand-200 px-5 py-4">
        <p className="text-sm font-bold text-ink">Recent Conversations</p>
        <span className="text-xs font-semibold text-accent-500">All channels</span>
      </div>
      <div className="divide-y divide-sand-200">
        {conversations.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <p className="text-sm text-ink-muted">No conversations yet</p>
            <p className="mt-1 text-xs text-ink-muted">Messages from WhatsApp will appear here</p>
          </div>
        ) : (
          conversations.map((c) => {
            const channel = (c.channel || "whatsapp") as ChannelId;
            const meta = CHANNELS[channel] || CHANNELS.whatsapp;
            const Icon = meta.icon;
            const name = c.patient_name || "Unknown";
            return (
              <div key={c.id} className="flex items-start gap-3 px-5 py-4">
                <span
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
                  style={{ backgroundColor: `${meta.color}1A`, color: meta.color }}>
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-semibold text-ink">
                      {name} <span className="font-normal text-ink-muted">· {timeAgo(c.updated_at)}</span>
                    </p>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                      c.status === "active" ? "bg-success/10 text-success" :
                      c.status === "needs_attention" ? "bg-danger/10 text-danger" :
                      "bg-sand-100 text-ink-muted"
                    }`}>
                      {c.status}
                    </span>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{c.last_message_preview}</p>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
