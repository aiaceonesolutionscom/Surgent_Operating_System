import { WalletIcon } from "lucide-react";
import type { Agent } from "./types";

export const financeAgent: Agent = {
  slug: "finance_agent",
  name: "Finance & Billing Agent",
  desc: "Answers money questions — revenue, who earned what, outstanding invoices.",
  icon: WalletIcon,
  categoryId: "business",
  tagline: "Your practice's numbers on tap, in plain language, any time.",
  howItWorks:
    "Ask 'how did this month look?' or 'what's outstanding?' and the agent answers from your real books — revenue, spending, net, invoice status, what each surgeon earned and what the AI agents themselves cost. No spreadsheets, no digging through the billing tab.",
  capabilities: [
    "Month-to-date revenue, spending and net in plain numbers",
    "Outstanding invoices and payment follow-up priorities",
    "Per-surgeon earnings and procedure-level revenue breakdowns",
    "Transparent AI-agent running costs",
  ],
  useCases: [
    "The owner asking 'where do we stand this month?' at a glance",
    "Chasing the invoices that actually matter",
    "Monthly performance conversations backed by real figures",
  ],
  outcome: { stat: "Zero", label: "time spent compiling the monthly finance summary" },
};