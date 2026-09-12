export interface FinanceAgentDoctorEarning {
  doctor_name: string;
  total_earned: number;
  invoices_paid: number;
}

export interface FinanceAgentAgentCost {
  agent_slug: string;
  sessions: number;
  estimated_cost: number;
}

export interface FinanceAgentRecentInvoice {
  patient_name: string;
  status: string;
  amount: number;
}

export interface FinanceAgentReport {
  total_revenue: number;
  total_expenses: number;
  net: number;
  outstanding: number;
  invoice_count: number;
  expense_count: number;
  month_label: string;
  per_doctor: FinanceAgentDoctorEarning[];
  per_agent_cost: FinanceAgentAgentCost[];
  recent_invoices: FinanceAgentRecentInvoice[];
}

export interface AskFinanceAgentResponse {
  session_id: string;
  answer: string;
}

export interface FinanceAgentMessage {
  role: "staff" | "agent";
  content: string;
  created_at: string;
}

export interface FinanceAgentSessionSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface FinanceAgentSessionDetail {
  id: string;
  title: string;
  messages: FinanceAgentMessage[];
}

type AuthedFetch = <T>(path: string, init?: RequestInit) => Promise<T>;

// Matches backend/src/router/finance_agent/finance_agent_router.py.
export function getFinanceAgentReport(authedFetch: AuthedFetch) {
  return authedFetch<FinanceAgentReport>("/api/v1/finance-agent/report");
}

export function askFinanceAgent(authedFetch: AuthedFetch, question: string, sessionId?: string | null) {
  return authedFetch<AskFinanceAgentResponse>("/api/v1/finance-agent/ask", {
    method: "POST",
    body: JSON.stringify({ question, session_id: sessionId ?? null })
  });
}

export function listFinanceAgentSessions(authedFetch: AuthedFetch) {
  return authedFetch<FinanceAgentSessionSummary[]>("/api/v1/finance-agent/sessions");
}

export function getFinanceAgentSession(authedFetch: AuthedFetch, sessionId: string) {
  return authedFetch<FinanceAgentSessionDetail>(`/api/v1/finance-agent/sessions/${sessionId}`);
}