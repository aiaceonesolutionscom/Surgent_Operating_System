import React from "react";
import { PageHeader } from "../components/PageHeader";
import { SessionsView } from "./SessionsView";
import { useSessions } from "./useSessions";

export function NeedsAttentionPage() {
  const { sessions, loading, error, refetch, resolve, loadMessages, sendMessage, toggleAi } = useSessions("needs_attention");

  if (loading) {
    return (
      <>
        <PageHeader title="Needs attention" subtitle="Sessions an agent escalated to your team — sorted most recent first." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-ink-muted">Loading conversations...</p>
        </div>
      </>);

  }

  if (error) {
    return (
      <>
        <PageHeader title="Needs attention" subtitle="Sessions an agent escalated to your team — sorted most recent first." />
        <div className="rounded-3xl border border-sand-200 bg-white p-12 text-center">
          <p className="text-sm text-danger">{error}</p>
          <button onClick={() => refetch()} className="mt-3 text-sm text-teal-600 hover:underline">Retry</button>
        </div>
      </>);

  }

  return (
    <>
      <PageHeader title="Needs attention" subtitle="Sessions an agent escalated to your team — sorted most recent first." />
      <SessionsView sessions={sessions} onLoadMessages={loadMessages} onResolve={resolve} onSendMessage={sendMessage} onToggleAi={toggleAi} />
    </>);

}
