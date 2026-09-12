import { apiFetch } from "./client";

export interface ConversationListItem {
  id: string;
  patient_id: string | null;
  patient_name: string;
  agent_type: string;
  channel: string;
  status: string;
  last_message_preview: string;
  updated_at: string;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  content_type: string;
  extra_data: Record<string, unknown>;
  created_at: string;
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageResponse[];
}

export async function listConversations(params?: {
  status?: string;
  channel?: string;
  agent_type?: string[];
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<ConversationListItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.channel) query.set("channel", params.channel);
  if (params?.agent_type) params.agent_type.forEach((t) => query.append("agent_type", t));
  if (params?.search) query.set("search", params.search);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiFetch<ConversationListItem[]>(`/api/v1/conversations${qs ? `?${qs}` : ""}`);
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/conversations/${id}`);
}

export async function resolveConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/conversations/${id}/resolve`, {
    method: "POST",
  });
}

export async function sendConversationMessage(
  id: string,
  body: string
): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function uploadConversationFile(
  id: string,
  file: File,
  caption?: string
): Promise<ConversationDetail> {
  const formData = new FormData();
  formData.append("file", file);
  if (caption) formData.append("caption", caption);

  const res = await fetch(`/api/v1/conversations/${id}/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}
