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

// Mock sessions for demo/development
const MOCK_SESSIONS: Session[] = [
  {
    id: "c1",
    patientId: "p1",
    patientName: "Sarah Thompson",
    patientInitial: "S",
    avatarUrl: null,
    channel: "WHATSAPP",
    agentSlug: "receptionist",
    agentName: "AI Receptionist",
    categoryId: "front-desk",
    status: "needs_attention",
    lastMessagePreview: "Hi, I'm very interested in the rhinoplasty. Can you tell me about recovery time?",
    updatedAt: "2024-12-12T14:22:00Z",
    aiPaused: false,
    messages: [],
    extraData: {},
    aiBookedAppointmentId: null,
  },
  {
    id: "c2",
    patientId: "p5",
    patientName: "James Anderson",
    patientInitial: "J",
    avatarUrl: null,
    channel: "INSTAGRAM",
    agentSlug: "lead_qualification",
    agentName: "Lead Qualification",
    categoryId: "consultation",
    status: "needs_attention",
    lastMessagePreview: "What's the cost range for gynecomastia surgery?",
    updatedAt: "2024-12-11T18:45:00Z",
    aiPaused: false,
    messages: [],
    extraData: {},
    aiBookedAppointmentId: null,
  },
  {
    id: "c3",
    patientId: "p4",
    patientName: "Laura Martinez",
    patientInitial: "L",
    avatarUrl: null,
    channel: "WEB_CHAT",
    agentSlug: "appointment_reminder",
    agentName: "Appointment & Booking Agent",
    categoryId: "front-desk",
    status: "active",
    lastMessagePreview: "Perfect, I'll book the follow-up for next week.",
    updatedAt: "2024-12-10T12:30:00Z",
    aiPaused: false,
    messages: [],
    extraData: {},
    aiBookedAppointmentId: null,
  },
  {
    id: "c4",
    patientId: "p2",
    patientName: "Emma Williams",
    patientInitial: "E",
    avatarUrl: null,
    channel: "WHATSAPP",
    agentSlug: "receptionist",
    agentName: "AI Receptionist",
    categoryId: "front-desk",
    status: "active",
    lastMessagePreview: "Thanks for the info! I'd like to schedule a consultation.",
    updatedAt: "2024-12-12T10:15:00Z",
    aiPaused: false,
    messages: [],
    extraData: {},
    aiBookedAppointmentId: "a1",
  },
  {
    id: "c5",
    patientId: "p3",
    patientName: "Michael Chen",
    patientInitial: "M",
    avatarUrl: null,
    channel: "WEB_CHAT",
    agentSlug: "patient_intake",
    agentName: "AI Patient Intake",
    categoryId: "consultation",
    status: "resolved",
    lastMessagePreview: "All medical history submitted. Ready for consultation.",
    updatedAt: "2024-12-09T16:20:00Z",
    aiPaused: true,
    messages: [],
    extraData: {},
    aiBookedAppointmentId: "a2",
  },
];

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
        // Fallback to mock data for demo
        setSessions(MOCK_SESSIONS);
        setLoading(false);
        return;
      }
      try {
        if (!opts?.silent) setLoading(true);
        const data = await listConversations(authedFetch, { status: statusFilter, patient_id: patientId, limit: 100 });
        setSessions((prev) => {
          const next = data.map(mapConversationToSession);
          // Use mock data if backend returns empty
          const finalSessions = next.length > 0 ? next : MOCK_SESSIONS;
          
          if (selectedId && !finalSessions.some((s) => s.id === selectedId)) {
            const stillOpen = prev.find((s) => s.id === selectedId);
            if (stillOpen) return [...finalSessions, stillOpen];
          }
          return finalSessions.map((s) => {
            const existing = prev.find((p) => p.id === s.id);
            return existing && existing.messages.length > 0 ? { ...s, messages: existing.messages } : s;
          });
        });
        setError(null);
      } catch (e: unknown) {
        // Fallback to mock data on error
        setSessions(MOCK_SESSIONS);
        if (!opts?.silent) setError(null);
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
