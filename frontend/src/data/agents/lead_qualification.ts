import { TargetIcon } from "lucide-react";
import type { Agent } from "./types";

export const leadQualification: Agent = {
  slug: "lead_qualification",
  name: "Lead Qualification",
  desc: "Scores every inbound lead in real time and routes only serious ones forward.",
  icon: TargetIcon,
  categoryId: "consultation",
  tagline: "Know which leads are ready to book before a human ever reads a message.",
  howItWorks:
    "Every WhatsApp, Instagram, call or web enquiry is analysed instantly: the lead's question, procedure interest, urgency and budget signals are scored, then the lead is routed to a warm handover with notes already attached — so no time is wasted on tyre-kickers and hot leads never sit unanswered.",
  capabilities: [
    "Scores inbound leads from every channel by intent and urgency",
    "Detects procedure of interest and readiness to book",
    "Routes hot leads to front desk with context attached",
    "Flags and quietly parks low-intent enquiries",
  ],
  useCases: [
    "A flood of Instagram DMs after a viral reel",
    "Separating serious rhinoplasty enquiries from browsers",
    "Making sure a hot lead is called back within minutes, not days",
  ],
  outcome: { stat: "2×", label: "faster response to genuinely ready-to-book leads" },
};