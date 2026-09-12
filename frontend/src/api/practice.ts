import { apiFetch } from "./client";

// ============================================================================
// Practice / clinic domain — the authed "me" + claim flow, plus the
// platform-level pricing/health/config endpoints that sit alongside it.
// ============================================================================

// --- practice (authed) ------------------------------------------------------
export interface PracticeMeResponse {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  address: string | null;
  timezone: string;
  plan_tier: "solo" | "practice" | "enterprise";
  subscription_status: string;
  role: "owner" | "doctor" | "receptionist" | "staff";
  // Only meaningful when role === "doctor" — granted permission keys from
  // backend/src/data/doctor_permissions.py. Empty for every other role.
  permissions: string[];
}

export interface ClaimPlanResponse {
  practice_id: string;
  plan_tier: "solo" | "practice" | "enterprise";
}

type AuthedFetch = <T>(path: string, init?: RequestInit) => Promise<T>;

// Matches backend/src/router/practice/practice_router.py. Takes the
// authedFetch function from useAuthedFetch() (api/authFetch.ts) rather than
// being a hook itself, so it stays a plain importable function.
export function getMyPractice(authedFetch: AuthedFetch) {
  return authedFetch<PracticeMeResponse>("/api/v1/practice/me");
}

export function claimPlan(authedFetch: AuthedFetch, sessionId: string) {
  return authedFetch<ClaimPlanResponse>("/api/v1/practice/claim", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId })
  });
}

// --- doctor signup code (owner-only) -----------------------------------------
export interface DoctorSignupCodeResponse {
  code: string;
  signup_url: string;
}

export interface ValidateDoctorCodeResponse {
  valid: boolean;
  practice_id: string | null;
  practice_name: string | null;
}

// Matches backend/src/router/practice/practice_router.py's doctor-signup-code
// endpoints — the shareable link an Owner gives out for doctors to
// self-register through (see app/dashboard/doctors/ and app/auth/DoctorApplyPage.tsx).
export function getDoctorSignupCode(authedFetch: AuthedFetch) {
  return authedFetch<DoctorSignupCodeResponse>("/api/v1/practice/doctor-signup-code");
}

export function regenerateDoctorSignupCode(authedFetch: AuthedFetch) {
  return authedFetch<DoctorSignupCodeResponse>("/api/v1/practice/doctor-signup-code/regenerate", { method: "POST" });
}

// Public/unauthenticated — a prospective doctor needs to confirm the link is
// valid before they've created any account at all.
export function validateDoctorCode(code: string) {
  return apiFetch<ValidateDoctorCodeResponse>(`/api/v1/practice/validate-doctor-code?code=${encodeURIComponent(code)}`);
}

// --- staff/receptionist signup code (owner-only) ----------------------------
// Receptionists self-register through the SAME share-link mechanism as
// doctors now (see app/dashboard/staff/StaffSignupLinkCard.tsx and
// app/auth/StaffApplyPage.tsx) — link + Owner approval, instead of the old
// Clerk email invite. Same response shape as the doctor code above.
export function getStaffSignupCode(authedFetch: AuthedFetch) {
  return authedFetch<DoctorSignupCodeResponse>("/api/v1/practice/staff-signup-code");
}

export function regenerateStaffSignupCode(authedFetch: AuthedFetch) {
  return authedFetch<DoctorSignupCodeResponse>("/api/v1/practice/staff-signup-code/regenerate", { method: "POST" });
}

export function validateStaffCode(code: string) {
  return apiFetch<ValidateDoctorCodeResponse>(`/api/v1/practice/validate-staff-code?code=${encodeURIComponent(code)}`);
}

// --- health -----------------------------------------------------------------
export interface HealthResponse {
  status: string;
  app: string;
  version: string;
}

// Matches backend/src/main.py's `/health` route exactly (status/app/version).
export function getHealth() {
  return apiFetch<HealthResponse>("/health");
}

// --- plans (public pricing) -------------------------------------------------
export interface PlanResponse {
  id: string;
  tier: "solo" | "practice" | "enterprise" | "custom";
  name: string;
  tagline: string | null;
  price: number | null;
  billing_period: string;
  is_custom_pricing: boolean;
  features: string[];
  agent_categories: string[];
  max_doctors: number | null;
  max_social_channels: number | null;
  max_locations: number | null;
  has_analytics: boolean;
  stripe_price_id: string | null;
  is_active: boolean;
  highlight: boolean;
  display_order: number;
  updated_at: string;
}

// DB-backed pricing (backend/src/models/plan.py) — the source of truth an
// admin edits from the super-admin plans page. Public/unauthenticated (matches
// GET /agent-costing's precedent): the checkout/pricing page and the
// dashboard's own plan-gating (app/dashboard/plan/plan.ts) both need this
// before any practice-auth chain necessarily exists.
export function listPlans() {
  return apiFetch<PlanResponse[]>("/api/v1/plans");
}

// --- agent config -----------------------------------------------------------
export interface AgentConfigResponse {
  id: string;
  practice_id: string;
  agent_type: string;
  enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface UpdateAgentConfigRequest {
  enabled?: boolean;
  config?: Record<string, unknown>;
}

// Matches backend/src/router/agent_config/agent_config_router.py — the
// first real reader/writer of AgentConfig.config.
export function getAgentConfig(authedFetch: AuthedFetch, agentType: string) {
  return authedFetch<AgentConfigResponse>(`/api/v1/agent-config/${agentType}`);
}

export function updateAgentConfig(authedFetch: AuthedFetch, agentType: string, data: UpdateAgentConfigRequest) {
  return authedFetch<AgentConfigResponse>(`/api/v1/agent-config/${agentType}`, {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

// --- agent costing ----------------------------------------------------------
export interface AgentCostingResponse {
  agent_slug: string;
  cost_per_session: number;
  is_active: boolean;
  total_sessions: number;
  total_earned: number;
}

// GET /api/v1/agent-costing — backend/src/router/agent_costing/. No auth:
// per-session cost is platform pricing, not practice-sensitive.
export function getAgentCosting() {
  return apiFetch<AgentCostingResponse[]>("/api/v1/agent-costing");
}
