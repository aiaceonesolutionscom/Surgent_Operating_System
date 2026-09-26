import { AGENTS_BY_SLUG } from "../../../data/agents";

// A lightweight, fully-local "AI triage" — no LLM call, just keyword
// matching against what a patient would actually say (not the agents' own
// marketing copy, which uses different vocabulary). Real classification
// (an actual LLM call) is a natural swap for classify() below once a
// backend endpoint exists — the return shape (agentSlug/categoryId/reasoning)
// wouldn't need to change.
//
// KEYWORDS ONLY FOR EXISTING AGENTS (9 real + 19 legacy aliases).
// Stale slugs from the old 31-agent taxonomy (multilingual_translation,
// photo_analysis, video_consultation, risk_assessment, procedure_recommendation,
// pre_surgery_preparation, surgery_scheduling, surgeon_calendar,
// operating_room_scheduler, equipment_checklist, implant_inventory,
// emergency_triage) are REMOVED — they crash because AGENTS_BY_SLUG[slug]
// is undefined. Their keywords are folded into the closest real agent below.
const AGENT_KEYWORDS: Record<string, string[]> = {
  // Front Desk & Intake
  receptionist: ["hello", "hi", "question", "call", "speak to someone", "help", "translate", "language", "speak spanish", "speak urdu", "don't speak english"],
  appointment_reminder: ["book", "schedule", "appointment", "consult", "consultation", "available", "remind", "reminder", "forgot my appointment", "reschedule", "cancel", "change my appointment", "move my appointment", "postpone"],
  // Consultation & Screening
  lead_qualification: ["thinking about", "considering", "not sure yet", "just looking", "interested in", "options", "what should i do", "advice"],
  patient_intake: ["medical history", "allergies", "medications i take", "past surgery", "health conditions"],
  consultation_assistant: ["consult", "which procedure", "recommend", "what procedure", "best option", "suggest", "risk", "am i a candidate", "safe for me", "complication", "pre-existing", "prepare for surgery", "before my surgery", "pre-op", "what to do before", "photo", "picture", "image", "look at my", "before and after", "video call", "video consult", "zoom", "virtual visit", "online consultation", "surgical record", "operative report", "documentation"],
  // Post-Surgery Care
  post_op_recovery: ["recovery", "how am i healing", "check in", "follow up", "follow-up", "healing", "swelling going down", "bruising", "progress photo", "emergency", "urgent", "severe pain", "bleeding", "fever", "infection", "can't breathe", "worried", "medication", "pills", "prescription", "when do i take", "wound", "dressing", "bandage", "incision", "scar care", "stitches", "recovery progress", "healing timeline"],
  marketing_retention: ["promotion", "offer", "discount", "deal", "feedback", "review", "complaint about service", "how was my visit"],
  // Business & Operations
  finance_agent: ["cost", "price", "how much", "quote", "estimate", "afford", "invoice", "bill", "payment", "pay my bill", "receipt", "insurance", "covered", "coverage", "claim", "metrics", "analytics", "reporting"],
  main_agent: ["schedule surgery", "surgery date", "book surgery", "surgery appointment", "operation date", "surgeon availability", "when is dr", "surgeon schedule", "operating room", "or availability", "surgery slot", "equipment", "tools ready", "implant", "implant size", "implant availability"],
};

// Surgery-adjacent agents get a boost when the patient explicitly needs
// surgery — even a vaguely-worded complaint should lean surgical, not land
// on a generic front-desk agent. Only includes REAL agent slugs.
const SURGERY_BOOST_SLUGS = [
  "main_agent",
  "consultation_assistant",
  "patient_intake",
  "lead_qualification"
];


export interface ClassificationResult {
  agentSlug: string;
  categoryId: string;
  reasoning: string;
}

function getValidAgent(slug: string) {
  const agent = AGENTS_BY_SLUG[slug];
  if (agent) return agent;
  return AGENTS_BY_SLUG.receptionist;
}

export function classifyPatient(complaint: string, needsSurgery: boolean): ClassificationResult {
  const text = complaint.toLowerCase();
  const scores: Record<string, { score: number; matched: string[] }> = {};

  for (const [slug, keywords] of Object.entries(AGENT_KEYWORDS)) {
    const matched = keywords.filter((k) => text.includes(k));
    let score = matched.length;
    if (needsSurgery && SURGERY_BOOST_SLUGS.includes(slug)) score += 1.5;
    if (score > 0) scores[slug] = { score, matched };
  }

  const ranked = Object.entries(scores).sort((a, b) => b[1].score - a[1].score);

  if (ranked.length === 0) {
    const fallbackSlug = needsSurgery ? "main_agent" : "receptionist";
    const agent = getValidAgent(fallbackSlug);
    return {
      agentSlug: fallbackSlug,
      categoryId: agent.categoryId,
      reasoning: needsSurgery
        ? "No specific keywords matched, but surgery was indicated — routed to Main Agent as a safe default."
        : "No specific keywords matched — routed to the AI Receptionist as the default first point of contact."
    };
  }

  const [bestSlug, { matched }] = ranked[0];
  const agent = getValidAgent(bestSlug);
  const matchedText = matched.length > 0 ? `matched "${matched.join('", "')}"` : "surgery flag";
  return {
    agentSlug: bestSlug,
    categoryId: agent.categoryId,
    reasoning: `${matchedText} → routed to ${agent.name}${needsSurgery ? " (surgery indicated)" : ""}.`
  };
}
