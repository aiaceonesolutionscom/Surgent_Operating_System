import { useCallback, useEffect, useState } from "react";
import {
  listStaffMessages,
  sendStaffMessage,
  sendStaffFile,
  type StaffMessageResponse
} from "../../../api/entities";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

// Messages within one 1:1 conversation. `conversationId` is legitimately
// undefined while no thread is open — the hook then just stays empty.
export function useStaffMessages(authedFetch: AuthedFetch, conversationId?: string) {
  const [messages, setMessages] = useState<StaffMessageResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    if (!authedFetch || !conversationId) {
      setMessages([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await listStaffMessages(authedFetch, conversationId);
      setMessages(data);
    } catch {
      setMessages([]);
    } finally {
      setLoading(false);
    }
  }, [authedFetch, conversationId]);

  useEffect(() => {
    setMessages([]);
    refetch();
  }, [refetch]);

  const send = useCallback(
    async (body: string) => {
      if (!authedFetch || !conversationId) return null;
      const message = await sendStaffMessage(authedFetch, conversationId, body);
      setMessages((prev) => [...prev, message]);
      return message;
    },
    [authedFetch, conversationId]
  );

  const sendFile = useCallback(
    async (file: File) => {
      if (!authedFetch || !conversationId) return null;
      const message = await sendStaffFile(authedFetch, conversationId, file);
      setMessages((prev) => [...prev, message]);
      return message;
    },
    [authedFetch, conversationId]
  );

  return { messages, loading, refetch, send, sendFile };
}
