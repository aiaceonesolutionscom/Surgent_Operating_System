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
import { isDemoMode } from "../../../data/demoMode";
import { toChannelId } from "../data/channels";
import type { Session, SessionMessage, SessionStatus } from "./types";

// Demo-only sessions, used when VITE_DEMO_MODE is explicitly enabled so a
// sales demo has something to show. Never used to cover a real API failure —
// these had UPPERCASE channels, which don't match the ChannelId keys in
// data/channels.ts and used to crash the sessions page on every render.
const MOCK_SESSIONS: Session[] = [
  {
    id: "c1",
    patientId: "p1",
    patientName: "Sarah Thompson",
    patientInitial: "S",
    avatarUrl: null,
    channel: "whatsapp",
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
    channel: "instagram",
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
    channel: "web_chat",
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
    channel: "whatsapp",
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
    channel: "web_chat",
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

/** The API stores statuses UPPERCASE ("NEEDS_ATTENTION"); the UI keys are lowercase. */
function toSessionStatus(raw: unknown): SessionStatus {
  const key = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (key === "needs_attention") return "needs_attention";
  if (key === "resolved" || key === "closed" || key === "archived") return "resolved";
  return "active";
}

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
    channel: toChannelId(c.channel),
    agentSlug: isPortal ? PORTAL_SLUG : (agent?.slug ?? c.agent_type),
    agentName: isPortal ? "Patient Portal" : (agent?.name ?? c.agent_type),
    categoryId: isPortal ? "patient-messages" : (agent?.categoryId ?? "business"),
    status: toSessionStatus(c.status),
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
    // Carry the backend's real content_type through. Hardcoding "text" here
    // meant SessionDetailPane's MessageContent always fell through to the
    // plain-text branch, so WhatsApp photos, voice notes, videos and
    // documents (PDF etc.) showed up as raw body text — for a PDF, usually
    // just the "[Document]" placeholder — with no image, player or download
    // link, even though the backend had already uploaded the file and sent
    // image_url / file_url / audio_url / video_url in extra_data.
    contentType: m.content_type || "text",
    extraData: m.extra_data || {},
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
        setSessions(isDemoMode() ? MOCK_SESSIONS : []);
        setLoading(false);
        return;
      }
      try {
        if (!opts?.silent) setLoading(true);
        const data = await listConversations(authedFetch, { status: statusFilter, patient_id: patientId, limit: 100 });
        setSessions((prev) => {
          const next = data.map(mapConversationToSession);
          // An empty result is a real answer ("no sessions need attention"),
          // not a reason to invent some. Only demo mode may substitute data.
          const finalSessions = next.length === 0 && isDemoMode() ? MOCK_SESSIONS : next;
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
        // Never mask a failed request with fake sessions — the UI shows the
        // error instead, so a broken backend is visible rather than silently
        // rendering fiction the clinic might act on.
        setSessions([]);
        setError(e instanceof Error && e.message ? e.message : "Couldn't load conversations.");
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
