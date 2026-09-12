import { apiFetch } from "./client";
import type { PlanResponse } from "./practice";

// ============================================================================
// Super Admin — standalone username/password + JWT, deliberately independent
// of Clerk (see backend/src/services/admin/admin_auth_service.py). Every
// route here is behind require_admin_token, enforced on the backend, not just
// hidden by frontend routing. Token lives in localStorage, scoped to this one
// browser — acceptable here since this panel has no cross-site embedding and
// logout just clears it.
// ============================================================================

const STORAGE_KEY = "aiaceone_admin_token";

export interface AdminLoginResponse {
  access_token: string;
  token_type: string;
}

// Matches backend/src/router/admin/admin_router.py's POST /admin/auth/login.
export function adminLogin(username: string, password: string) {
  return apiFetch<AdminLoginResponse>("/api/v1/admin/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export function getAdminToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string) {
  try {
    localStorage.setItem(STORAGE_KEY, token);
  } catch {
    // Storage unavailable (private mode, etc.) — session just won't persist.
  }
}

export function clearAdminToken() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

// Every authenticated admin API call goes through this — attaches the stored
// JWT, and treats a missing token as an immediate 401 rather than firing a
// doomed request.
export async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken();
  return apiFetch<T>(path, {
    ...init,
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers }
  });
}

// --- admin endpoints --------------------------------------------------------
export interface AdminMeResponse {
  username: string;
  role: string;
}

export interface AdminSummaryResponse {
  total_clinics: number;
  plan_distribution: Record<string, number>;
  total_estimated_mrr: number;
  total_estimated_cost: number;
  total_estimated_margin: number;
  margin_percent: number;
  assumption_note: string;
}

export interface AdminPracticeListItem {
  id: string;
  name: string;
  email: string;
  status: "pending_approval" | "active" | "suspended";
  plan_tier: string;
  subscription_status: string;
  agents_enabled_count: number;
  estimated_monthly_cost: number;
  estimated_monthly_revenue: number;
  joined_at: string;
}

export interface AgentCostBreakdownItem {
  agent_slug: string;
  enabled: boolean;
  cost_per_session: number;
  estimated_monthly_cost: number;
}

export interface AdminPracticeDetailResponse {
  id: string;
  name: string;
  email: string;
  status: "pending_approval" | "active" | "suspended";
  phone: string | null;
  address: string | null;
  plan_tier: string;
  subscription_status: string;
  estimated_monthly_revenue: number;
  estimated_monthly_cost: number;
  agent_breakdown: AgentCostBreakdownItem[];
  joined_at: string;
}

export function getAdminMe() {
  return adminFetch<AdminMeResponse>("/api/v1/admin/me");
}

export function getAdminSummary() {
  return adminFetch<AdminSummaryResponse>("/api/v1/admin/summary");
}

export function listAdminPractices(params: { q?: string; plan_tier?: string; sort?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.plan_tier) qs.set("plan_tier", params.plan_tier);
  if (params.sort) qs.set("sort", params.sort);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return adminFetch<AdminPracticeListItem[]>(`/api/v1/admin/practices${suffix}`);
}

export function getAdminPracticeDetail(practiceId: string) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/practices/${practiceId}`);
}

export function createAdminPractice(data: { name: string; email: string; plan_tier?: string }) {
  return adminFetch<AdminPracticeDetailResponse>("/api/v1/admin/practices", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateAdminPractice(practiceId: string, data: { name?: string; email?: string; plan_tier?: string }) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/practices/${practiceId}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function updatePracticeSubscription(practiceId: string, tier: string) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/practices/${practiceId}/subscription`, {
    method: "PATCH",
    body: JSON.stringify({ tier })
  });
}

export function suspendPractice(practiceId: string) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/practices/${practiceId}/suspend`, { method: "POST" });
}

export function reactivatePractice(practiceId: string) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/practices/${practiceId}/reactivate`, { method: "POST" });
}

// --- new-organization approval queue ---------------------------------------
export interface OrgRequestListItem {
  id: string;
  email: string;
  org_name: string | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export function listOrgRequests() {
  return adminFetch<OrgRequestListItem[]>("/api/v1/admin/org-requests");
}

export function approveOrgRequest(requestId: string, planTier: "practice" | "enterprise" | null = null) {
  return adminFetch<AdminPracticeDetailResponse>(`/api/v1/admin/org-requests/${requestId}/approve`, {
    method: "POST",
    body: JSON.stringify({ plan_tier: planTier || undefined })
  });
}

export function rejectOrgRequest(requestId: string, reason?: string) {
  return adminFetch<void>(`/api/v1/admin/org-requests/${requestId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null })
  });
}

export function listAdminPlans() {
  return adminFetch<PlanResponse[]>("/api/v1/admin/plans");
}

export function updateAdminPlan(planId: string, body: Partial<PlanResponse>) {
  return adminFetch<PlanResponse>(`/api/v1/admin/plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(body)
  });
}

// Clinic-buyer leads captured by Aria on the marketing site — the platform's
// own sales pipeline (backend /admin/sales-leads). These are Aiaceone-owner
// records, deliberately NOT practice-scoped.
export interface SalesLeadResponse {
  id: string;
  full_name: string;
  email: string;
  phone: string | null;
  company: string | null;
  message: string | null;
  source: string;
  status: string;
  conversation_id: string | null;
  created_at: string;
}

export function listAdminSalesLeads(params: { q?: string } = {}) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return adminFetch<SalesLeadResponse[]>(`/api/v1/admin/sales-leads${suffix}`);
}

// --- Super Agent (platform-level, Aiaceone-team only) -----------------------
// Backend: /api/v1/admin/super-agent/* — an LLM agent that answers questions
// about the WHOLE platform (not one clinic) from live practices/plans data.
export interface AskSuperAgentResponse {
  session_id: string;
  answer: string;
}

export interface SuperAgentMessage {
  role: "staff" | "agent";
  content: string;
  created_at: string;
}

export interface SuperAgentSessionSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface SuperAgentSessionDetail {
  id: string;
  title: string;
  messages: SuperAgentMessage[];
}

export function askSuperAgent(question: string, sessionId?: string | null) {
  return adminFetch<AskSuperAgentResponse>("/api/v1/admin/super-agent/ask", {
    method: "POST",
    body: JSON.stringify({ question, session_id: sessionId ?? null })
  });
}

export function listSuperAgentSessions() {
  return adminFetch<SuperAgentSessionSummary[]>("/api/v1/admin/super-agent/sessions");
}

export function getSuperAgentSession(sessionId: string) {
  return adminFetch<SuperAgentSessionDetail>(`/api/v1/admin/super-agent/sessions/${sessionId}`);
}
