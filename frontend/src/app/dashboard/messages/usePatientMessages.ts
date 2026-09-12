import { useCallback, useEffect, useState } from "react";
import {
  listPatientMessages,
  getPatientMessage,
  sendPatientMessage,
  resolvePatientMessage,
  type ConversationListItem,
  type ConversationDetail,
  type MessageResponse,
} from "../../../api/entities";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

// Patient Messages inbox — portal messages patients sent their assigned
// doctor (and the receptionist). The backend scopes it per role: a Doctor
// sees only their own patients, the receptionist sees all, and the Owner
// sees everything read-only (can_reply false, so the reply box simply isn't
// rendered). Quiet 30s polling mirroring the rest of the dashboard gives the
// inbox the same "near-live" feel without a websocket.
const POLL_INTERVAL_MS = 30000;

export function usePatientMessages(authedFetch: AuthedFetch) {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async (opts?: { silent?: boolean }) => {
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    try {
      if (!opts?.silent) setLoading(true);
      const data = await listPatientMessages(authedFetch, { limit: 100 });
      setConversations(data);
      setError(null);
    } catch (e) {
      if (!opts?.silent && e instanceof Error) setError(e.message);
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const loadConversation = useCallback(async (id: string) => {
    setActiveId(id);
    if (!authedFetch) return;
    try {
      const fresh = await getPatientMessage(authedFetch, id);
      setDetail(fresh);
    } catch {
      // Transient failure — thread stays as-is; next poll retries.
    }
  }, [authedFetch]);

  // Auto-open the newest conversation when the tab is first shown.
  useEffect(() => {
    if (!loading && !activeId && conversations.length > 0) {
      setActiveId(conversations[0].id);
      loadConversation(conversations[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, conversations, activeId]);

  useEffect(() => {
    if (!authedFetch) return;
    const interval = setInterval(() => {
      refetch({ silent: true });
      if (activeId) {
        getPatientMessage(authedFetch, activeId)
          .then(setDetail)
          .catch(() => {});
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [authedFetch, activeId, refetch]);

  const send = useCallback(async (body: string) => {
    if (!authedFetch || !activeId) return null;
    const fresh = await sendPatientMessage(authedFetch, activeId, body);
    setDetail(fresh);
    setConversations((prev) => {
      const listItem = {
        ...fresh,
        last_message_preview: fresh.messages[fresh.messages.length - 1]?.content ?? fresh.last_message_preview,
        updated_at: fresh.updated_at,
      };
      return [listItem, ...prev.filter((c) => c.id !== activeId)];
    });
    return fresh;
  }, [authedFetch, activeId]);

  const resolve = useCallback(async () => {
    if (!authedFetch || !activeId) return;
    const fresh = await resolvePatientMessage(authedFetch, activeId);
    setDetail(fresh);
    setConversations((prev) =>
      prev.map((c) => (c.id === activeId ? { ...c, status: "resolved" as const } : c))
    );
  }, [authedFetch, activeId]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  return {
    conversations,
    activeId,
    active,
    messages: detail?.messages ?? [],
    canReply: detail?.can_reply ?? active?.can_reply ?? true,
    loading,
    error,
    refetch,
    loadConversation,
    send,
    resolve,
  };
}

export type { MessageResponse };