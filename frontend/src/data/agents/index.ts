import { receptionist } from "./receptionist";
import { appointmentReminder } from "./appointment_reminder";
import { leadQualification } from "./lead_qualification";
import { patientIntake } from "./patient_intake";
import { consultationAssistant } from "./consultation_assistant";
import { postOpRecovery } from "./post_op_recovery";
import { marketingRetention } from "./marketing_retention";
import { financeAgent } from "./finance_agent";
import { mainAgent } from "./main_agent";
import type { Agent, AgentCategory } from "./types";

export type { Agent, AgentCategory } from "./types";

// The consolidated product roster: 9 real clinic agents (down from 31 scratch
// ones), plus the platform-only Super Agent (not shown here — that one lives
// in the Super Admin panel, never the clinic dashboard). Name/desc/slug here
// are the single source of truth the plan tiers and AgentDetailPage read.
export const AGENT_CATEGORIES: AgentCategory[] = [
  {
    id: "front-desk",
    label: "Front Desk & Intake",
    tagline: "Never miss a lead, a call, or a booking — around the clock.",
    agents: [receptionist, appointmentReminder]
  },
  {
    id: "consultation",
    label: "Consultation & Screening",
    tagline: "Qualify, intake and prepare patients before they ever walk in.",
    agents: [leadQualification, patientIntake, consultationAssistant]
  },
  {
    id: "post-care",
    label: "Post-Op Care & Retention",
    tagline: "Keep patients healing and coming back — after every procedure.",
    agents: [postOpRecovery, marketingRetention]
  },
  {
    id: "business",
    label: "Business & Operations",
    tagline: "Turn every interaction into revenue and retention.",
    agents: [financeAgent, mainAgent]
  }
];

export const TOTAL_AGENTS = AGENT_CATEGORIES.reduce((n, c) => n + c.agents.length, 0);

// Legacy session slugs (older Conversation.agent_type values) alias onto their
// consolidated successor so history panels (PatientSpotlight, AgentDetailPage,
// Command Center) keep rendering after the 31→9 consolidation.
const SESSION_SLUG_ALIASES: Record<string, string> = {
  "command_center": "main_agent",
  "post_op_followup": "post_op_recovery",
  "recovery_followup": "post_op_recovery",
  "healing_monitoring": "post_op_recovery",
  "wound_care_guidance": "post_op_recovery",
  "medication_reminder": "post_op_recovery",
  "recovery_dashboard": "post_op_recovery",
  "ai_consultation": "consultation_assistant",
  "surgical_documentation": "consultation_assistant",
  "medical_history_intake": "patient_intake",
  "lead_nurturing": "marketing_retention",
  "marketing_followup": "marketing_retention",
  "patient_feedback": "marketing_retention",
  "appointment_booking": "appointment_reminder",
  "reschedule_cancellation": "appointment_reminder",
  "analytics_dashboard": "finance_agent",
  "cost_estimation": "finance_agent",
  "payment_invoice": "finance_agent",
  "insurance_verification": "finance_agent"
};

export const AGENTS_BY_SLUG: Record<string, Agent> = Object.fromEntries(
  AGENT_CATEGORIES.flatMap((c) => c.agents).map((a) => [a.slug, a])
);

for (const [alias, target] of Object.entries(SESSION_SLUG_ALIASES)) {
  const agent = AGENTS_BY_SLUG[target];
  if (agent) AGENTS_BY_SLUG[alias] = agent;
}

export const ALL_AGENT_SLUGS: string[] = Object.keys(AGENTS_BY_SLUG);