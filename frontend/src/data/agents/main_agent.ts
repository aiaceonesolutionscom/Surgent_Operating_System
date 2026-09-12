import { CommandIcon } from "lucide-react";
import type { Agent } from "./types";

export const mainAgent: Agent = {
  slug: "main_agent",
  name: "Main Agent",
  desc: "Your clinic's command center — live status of every agent, one pane of glass.",
  icon: CommandIcon,
  categoryId: "business",
  tagline: "One conversation that sees across every part of your practice.",
  howItWorks:
    "The Main Agent is the single brain that sits above all six specialist agents. Ask it anything in plain language — 'what happened yesterday?', 'are there any red flags in recovery?' — and it pulls live answers from the right specialist, showing you each step it consulted.",
  capabilities: [
    "One chat interface across every agent and data source",
    "Consults front desk, clinical, recovery and finance automatically",
    "Shows the steps behind every answer for trust",
    "Cross-category questions answered without switching tabs",
  ],
  useCases: [
    "Firing off a rapid-fire daily briefing at morning coffee",
    "Cross-checking a new lead against an existing patient",
    "One place to see what's happening across the clinic today",
  ],
  outcome: { stat: "1", label: "place to see everything happening in your clinic" },
};