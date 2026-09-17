import { useState, useEffect, useCallback } from "react";
import {
  listConversations,
  getConversation,
  resolveConversation,
  sendConversationMessage,
  toggleConversationAi,
  type ConversationListItem,
  type ConversationDetail
} from "../../../api/entities";
import { usePlan } from "../plan/PlanContext";
import { AGENTS_BY_SLUG } from "../../../data/agents";
import type { Session, SessionMessage } from "./types";

// Display name/category for a session come straight from the consolidated
// agent catalog (AGENTS_BY_SLUG includes the legacy-slug aliases, so old
// Conversation.agent_type values like "command_center" resolve onto their
// successor agent here). "patient_doctor_message" has no catalog entry — it's
// the patient portal channel, handled explicitly below.
const PORTAL_SLUG = "patient_doctor_message";

export function mapConversationToSession(c: ConversationListItem): Session {
  const name = c.patient_name || "Unknown Patient";
  const isPortal = c.agent_type === PORTAL_SLUG;
  const agent = AGENTS_BY_SLUG[c.agent_type];
  return {
    id: c.id,
    patientId: c.patient_id || "",
    patientName: name,
    patientInitial: name.charAt(0).toUpperCase(),
    avatarUrl: c.avatar_url,
    channel: c.channel as Session["channel"],
    agentSlug: isPortal ? PORTAL_SLUG : (agent?.slug ?? c.agent_type),
    agentName: isPortal ? "Patient Portal" : (agent?.name ?? c.agent_type),
    categoryId: isPortal ? "patient-messages" : (agent?.categoryId ?? "business"),
    status: c.status as Session["status"],
    lastMessagePreview: c.last_message_preview,
    updatedAt: c.updated_at,
    aiPaused: c.ai_paused,
    messages: [],
    extraData: c.extra_data || {},
    aiBookedAppointmentId: c.ai_booked_appointment_id ?? null,
  };
}

function mapRole(role: string): SessionMessage["from"] {
  if (role === "agent") return "agent";
  if (role === "patient") return "patient";
  if (role === "staff") return "staff";
  return "system";
}

function mapDetailMessages(detail: ConversationDetail): SessionMessage[] {
  return detail.messages.map((m) => ({
    id: m.id,
    from: mapRole(m.role),
    text: m.content,
    contentType: "text",
    at: m.created_at,
  }));
}

// How often to quietly re-check for new messages/status changes — a real
// WhatsApp reply from a patient, or the AI's own reply, previously only
// ever showed up after a manual navigate-away-and-back. Short enough to
// feel "live," long enough not to hammer the API for what's still a
// polling-based (not websocket) inbox.
const POLL_INTERVAL_MS = 4000;

export function useSessions(statusFilter?: string, patientId?: string) {
  const { authedFetch } = usePlan();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const fetchSessions = useCallback(
    async (opts?: { silent?: boolean }) => {
      if (!authedFetch) {
        setLoading(false);
        return;
      }
      try {
        if (!opts?.silent) setLoading(true);
        const data = await listConversations(authedFetch, { status: statusFilter, patient_id: patientId, limit: 100 });
        setSessions((prev) => {
          const next = data.map(mapConversationToSession);
          // A background poll re-applies the server-side status filter, so
          // a conversation whose status just changed (e.g. AI resumed and
          // the patient's message got handled, no longer "needs attention")
          // can legitimately drop out of a filtered list. If it's the one
          // currently open, keep showing it — and keep whatever messages
          // are already loaded for it — rather than yanking the reply box
          // out from under whoever's mid-conversation with it.
          if (selectedId && !next.some((s) => s.id === selectedId)) {
            const stillOpen = prev.find((s) => s.id === selectedId);
            if (stillOpen) return [...next, stillOpen];
          }
          // Preserve already-loaded messages for sessions that were open
          // before this poll — the list endpoint doesn't return message
          // bodies, only a preview.
          return next.map((s) => {
            const existing = prev.find((p) => p.id === s.id);
            return existing && existing.messages.length > 0 ? { ...s, messages: existing.messages } : s;
          });
        });
        setError(null);
      } catch (e: unknown) {
        if (!opts?.silent) {
          const msg = e instanceof Error ? e.message : "Failed to load sessions";
          setError(msg);
        }
      } finally {
        if (!opts?.silent) setLoading(false);
      }
    },
    [authedFetch, statusFilter, patientId, selectedId]
  );

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const loadMessages = useCallback(async (sessionId: string) => {
    setSelectedId(sessionId);
    if (!authedFetch) return;
    try {
      const detail = await getConversation(authedFetch, sessionId);
      const messages = mapDetailMessages(detail);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...mapConversationToSession(detail), messages } : s))
      );
    } catch {
      // Silently fail — messages stay empty
    }
  }, [authedFetch]);

  // Quiet background refresh: re-fetches the list (so previews/status/new
  // conversations show up) and, if a conversation is open, its messages —
  // all without the loading spinner a manual fetchSessions() would show.
  useEffect(() => {
    if (!authedFetch) return;
    const interval = setInterval(() => {
      fetchSessions({ silent: true });
      if (selectedId) {
        getConversation(authedFetch, selectedId)
          .then((detail) => {
            const messages = mapDetailMessages(detail);
            setSessions((prev) =>
              prev.map((s) => (s.id === selectedId ? { ...mapConversationToSession(detail), messages } : s))
            );
          })
          .catch(() => {
            // Transient poll failure — next tick tries again.
          });
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [authedFetch, selectedId, fetchSessions]);

  const resolve = useCallback(async (id: string) => {
    if (!authedFetch) return;
    await resolveConversation(authedFetch, id);
    setSessions((prev) =>
      prev.map((s) => (s.id === id ? { ...s, status: "resolved" as const } : s))
    );
  }, [authedFetch]);

  const applyDetail = useCallback((id: string, detail: ConversationDetail) => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === id
          ? { ...mapConversationToSession(detail), messages: mapDetailMessages(detail) }
          : s
      )
    );
  }, []);

  const sendMessage = useCallback(
    async (id: string, body: string): Promise<string | null> => {
      if (!authedFetch) return null;
      const detail = await sendConversationMessage(authedFetch, id, body);
      applyDetail(id, detail);
      // Non-null only when the reply was saved but did NOT actually reach
      // the patient over WhatsApp (see backend ConversationsService.
      // send_staff_message) — the old behavior silently swallowed this, so
      // staff had no way to know a message never arrived.
      return detail.send_warning ?? null;
    },
    [authedFetch, applyDetail]
  );

  const toggleAi = useCallback(
    async (id: string, paused: boolean) => {
      if (!authedFetch) return;
      const detail = await toggleConversationAi(authedFetch, id, paused);
      applyDetail(id, detail);
    },
    [authedFetch, applyDetail]
  );

  return { sessions, loading, error, refetch: fetchSessions, resolve, loadMessages, sendMessage, toggleAi };
}
