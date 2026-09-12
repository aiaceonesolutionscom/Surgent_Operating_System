import React from "react";
import type { Session } from "./types";
import { ChannelIcon } from "./ChannelIcon";

const STATUS_DOT: Record<Session["status"], string> = {
  active: "bg-accent-500",
  needs_attention: "bg-danger",
  resolved: "bg-success"
};

function timeAgo(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diffMs / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.round(hrs / 24)}d ago`;
}

export function SessionListItem({
  session,
  active,
  onClick
}: { session: Session; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-start gap-3 border-b border-sand-200/70 px-4 py-3.5 text-left transition-colors ${
      active ? "bg-accent-500/6" : "hover:bg-sand-100"}`
      }>

      <span className="relative mt-0.5">
        {session.avatarUrl ?
        <img src={session.avatarUrl} alt="" className="h-9 w-9 rounded-full object-cover" /> :

        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-sand-200 text-sm font-bold text-ink-soft">
            {session.patientInitial}
          </span>
        }
        <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${STATUS_DOT[session.status]}`} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-semibold text-ink">{session.patientName}</span>
          <span className="shrink-0 text-xs text-ink-muted">{timeAgo(session.updatedAt)}</span>
        </span>
        <span className="mt-0.5 flex items-center gap-1.5">
          <ChannelIcon channel={session.channel} size={10} />
          <span className="text-xs text-ink-muted">{session.agentName}</span>
{session.aiBookedAppointmentId &&
  <span className="inline-flex items-center gap-0.5 rounded-full bg-teal-600/10 px-1.5 py-0.5 text-[10px] font-semibold text-teal-600">
    Booked
  </span>
}
        </span>
        <span className="mt-1 block truncate text-xs text-ink-muted">{session.lastMessagePreview}</span>
      </span>
    </button>);

}