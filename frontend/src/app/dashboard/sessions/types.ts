import type { ChannelId } from "../data/channels";

export type SessionStatus = "active" | "needs_attention" | "resolved";

export interface SessionMessage {
  id: string;
  from: "patient" | "agent" | "staff" | "system";
  text: string;
  contentType: string;
  extraData?: Record<string, unknown>;
  at: string; // ISO timestamp
}

export interface Session {
  id: string;
  patientId: string;
  patientName: string;
  patientInitial: string;
  avatarUrl: string | null;
  channel: ChannelId;
  agentSlug: string;
  agentName: string;
  categoryId: string;
  status: SessionStatus;
  lastMessagePreview: string;
  updatedAt: string; // ISO timestamp
  aiPaused: boolean;
  messages: SessionMessage[];
  extraData?: Record<string, unknown>;
  aiBookedAppointmentId?: string | null;
}
