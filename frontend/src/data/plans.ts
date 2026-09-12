import type { PlanTier } from "./planTiers";

export interface Plan {
  id: PlanTier;
  name: string;
  tagline: string;
  price: string;
  period: string;
  highlight: boolean;
  features: string[];
}

// Two plans today — Practice $999/mo (unicorn, fully configured) and Enterprise
// (custom-priced, multi-location). The old "Solo $690" plan was removed; any
// stale solo tier normalizes to practice (data/planTiers.ts).
export const PLANS: Plan[] = [
{
  id: "practice",
  name: "Practice",
  tagline: "The whole AI front office for a growing clinic",
  price: "$999",
  period: "/mo",
  highlight: true,
  features: [
  "All 9 agents pre-configured",
  "Front desk, consultation, recovery & retention agents",
  "Finance agent — monthly revenue, outstanding and agent cost",
  "WhatsApp, Instagram & website chat channels",
  "Multilingual support",
  "Analytics dashboard",
  "Priority onboarding & support"]

},
{
  id: "enterprise",
  name: "Enterprise",
  tagline: "For groups & multi-location brands",
  price: "Custom",
  period: "",
  highlight: false,
  features: [
  "Everything in Practice",
  "Custom plan — priced for your operation",
  "Multi-location orchestration",
  "Custom integrations & EHR",
  "BAA & dedicated success manager"]

}];
