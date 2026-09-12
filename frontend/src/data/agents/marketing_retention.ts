import { MegaphoneIcon } from "lucide-react";
import type { Agent } from "./types";

export const marketingRetention: Agent = {
  slug: "marketing_retention",
  name: "Marketing & Retention",
  desc: "Nurtures leads, follows up after care and turns happy patients into referrals.",
  icon: MegaphoneIcon,
  categoryId: "post-care",
  tagline: "Your past patients are your cheapest marketing — this agent activates them.",
  howItWorks:
    "Warm leads get a gentle, personalised nurture sequence until they book. After care, happy patients are asked for reviews and referrals at the perfect moment, and lapsed patients get prompts to return for touch-ups and maintenance — a self-feeding flow of returning revenue.",
  capabilities: [
    "Personalised nurture sequences for warm, unbooked leads",
    "Automated review and referral requests post-procedure",
    "Re-engagement nudges for lapsed and touch-up patients",
    "Follow-ups that feel personal, never spammy",
  ],
  useCases: [
    "A list of 'interested but not ready' leads that no one calls back",
    "Turning a great result into Google reviews and word-of-mouth",
    "Knitting a loyal maintenance clientele from past patients",
  ],
  outcome: { stat: "+40%", label: "more returning and referred patients per year" },
};