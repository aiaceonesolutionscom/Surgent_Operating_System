import React, { useState, useCallback, useEffect, useRef } from "react";
import { InboxIcon, ArrowLeftIcon } from "lucide-react";
import type { Session } from "./types";
import { SessionListItem } from "./SessionListItem";
import { SessionDetailPane } from "./SessionDetailPane";
import { EmptyState } from "../components/EmptyState";

interface SessionsViewProps {
  sessions: Session[];
  onLoadMessages?: (sessionId: string) => void;
  onResolve?: (sessionId: string) => void;
  onSendMessage?: (sessionId: string, body: string) => Promise<string | null>;
  onToggleAi?: (sessionId: string, paused: boolean) => Promise<void>;
}

export function SessionsView({ sessions, onLoadMessages, onResolve, onSendMessage, onToggleAi }: SessionsViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(sessions[0]?.id ?? null);
  const selected = sessions.find((s) => s.id === selectedId) ?? null;

  // The first session is auto-selected via the useState initializer above,
  // but that never goes through handleSelect — so its messages were never
  // fetched, leaving "Loading messages..." stuck forever until the user
  // clicked away and back. Fire the load once for whatever's selected on
  // mount.
  const didInitialLoad = useRef(false);
  useEffect(() => {
    if (!didInitialLoad.current && selectedId && onLoadMessages) {
      didInitialLoad.current = true;
      onLoadMessages(selectedId);
    }
  }, [selectedId, onLoadMessages]);

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
    // Load messages when selecting a conversation
    if (onLoadMessages) {
      onLoadMessages(id);
    }
  }, [onLoadMessages]);

  if (sessions.length === 0) {
    return (
      <div className="rounded-3xl border border-sand-200 bg-white">
        <EmptyState
          icon={InboxIcon}
          title="No sessions here"
          body="Once patients start reaching out via WhatsApp, Facebook, or Instagram, their conversations will show up here." />
      </div>
    );
  }

  return (
    <div className="grid h-[calc(100vh-9rem)] grid-cols-1 overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_4px_20px_rgba(15,23,42,0.05)] lg:grid-cols-[340px_1fr]">
      {/* Below the lg breakpoint this is a single-pane master/detail view —
          the list and an open conversation used to just swap visibility via
          "hidden lg:block" with no narrow-screen equivalent at all, so
          selecting a conversation on anything less than a maximized wide
          window showed literally nothing: no messages, no reply box. */}
      <div className={`overflow-y-auto border-sand-200 lg:border-r ${selected ? "hidden lg:block" : "block"}`}>
        {sessions.map((s) => (
          <SessionListItem
            key={s.id}
            session={s}
            active={s.id === selectedId}
            onClick={() => handleSelect(s.id)} />
        ))}
      </div>
      <div className={selected ? "flex min-h-0 flex-col lg:block" : "hidden lg:block"}>
        {selected ? (
          <>
            <button
              type="button"
              onClick={() => setSelectedId(null)}
              className="flex items-center gap-1.5 border-b border-sand-100 px-4 py-2.5 text-xs font-semibold text-ink-muted transition-colors hover:text-ink lg:hidden">
              <ArrowLeftIcon className="h-3.5 w-3.5" /> Back to conversations
            </button>
            <div className="min-h-0 flex-1 lg:h-full">
              <SessionDetailPane session={selected} onResolve={onResolve} onSendMessage={onSendMessage} onToggleAi={onToggleAi} />
            </div>
          </>
        ) : (
          <EmptyState icon={InboxIcon} title="Select a conversation" body="Pick a session from the list to see the full transcript." />
        )}
      </div>
    </div>
  );
}
