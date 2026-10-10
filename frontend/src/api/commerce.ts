import { apiFetch } from "./client";

// ============================================================================
// Commerce — checkout (Stripe) + demo-request lead capture. Both are public,
// unauthenticated flows on the marketing side of the app.
// ============================================================================

// --- checkout ---------------------------------------------------------------
export interface CheckoutSessionResponse {
  // Mounts Stripe's embedded payment form (there is no hosted checkout URL).
  client_secret: string;
  session_id: string;
}

export interface CheckoutSessionStatusResponse {
  paid: boolean;
  plan_tier: "solo" | "practice" | "enterprise";
  email: string;
  claimed: boolean;
}

// Matches backend/src/router/checkout/checkout_router.py's
// POST /api/v1/checkout/create-session. Called by CheckoutPage.tsx, which mounts
// the returned client_secret as Stripe's embedded payment form.
export function createCheckoutSession(email: string | undefined, planTier: "solo" | "practice") {
  return apiFetch<CheckoutSessionResponse>("/api/v1/checkout/create-session", {
    method: "POST",
    // No email: Stripe's payment form collects it and the webhook records it.
    body: JSON.stringify({ ...(email ? { email } : {}), plan_tier: planTier })
  });
}

// GET /api/v1/checkout/session/{id} — used by CheckoutSuccessPage to confirm
// payment landed before showing "Payment confirmed" (the Stripe webhook can
// race the browser redirect).
export function getCheckoutSession(sessionId: string) {
  return apiFetch<CheckoutSessionStatusResponse>(`/api/v1/checkout/session/${encodeURIComponent(sessionId)}`);
}

// --- demo requests ----------------------------------------------------------
export interface DemoRequestPayload {
  name: string;
  email: string;
  phone?: string;
  practice_name?: string;
  message?: string;
}

export interface DemoRequestResponse {
  id: string;
  name: string;
  email: string;
  status: string;
  created_at: string;
}

// Matches backend/src/router/demo/demo_router.py's POST /api/v1/demo-requests.
export function submitDemoRequest(payload: DemoRequestPayload) {
  return apiFetch<DemoRequestResponse>("/api/v1/demo-requests", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
