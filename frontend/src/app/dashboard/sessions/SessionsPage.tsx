import React from "react";
import { PageHeader } from "../components/PageHeader";
import { SessionsView } from "./SessionsView";
import { useSessions } from "./useSessions";


export function SessionsPage() {
  const { sessions, loading, error, refetch, resolve, loadMessages, sendMessage, toggleAi } = useSessions();

  if (loading) {
    return (
      <>
        <PageHeader title="All conversations" subtitle="Every patient session, across every agent and channel, in one inbox." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading conversations...</p>
        </div>
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="All conversations" subtitle="Every patient session, across every agent and channel, in one inbox." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="All conversations" subtitle="Every patient session, across every agent and channel, in one inbox." />
      <SessionsView sessions={sessions} onLoadMessages={loadMessages} onResolve={resolve} onSendMessage={sendMessage} onToggleAi={toggleAi} />
    </>
  );
}
