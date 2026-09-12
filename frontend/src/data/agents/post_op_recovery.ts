import { HeartPulseIcon } from "lucide-react";
import type { Agent } from "./types";

export const postOpRecovery: Agent = {
  slug: "post_op_recovery",
  name: "Post-Op Recovery & Follow-up",
  desc: "Tracks healing, medication and check-ups after every procedure.",
  icon: HeartPulseIcon,
  categoryId: "post-care",
  tagline: "Every patient followed up, every day, without lifting a phone.",
  howItWorks:
    "After surgery the agent checks in on schedule — how's your recovery, are you taking your medication, any swelling or pain? — flags anything that needs a clinician's eyes, reminds patients of appointments, and quietly catches complications early when they're cheapest to fix.",
  capabilities: [
    "Scheduled check-ins on healing, pain and medication adherence",
    "Flags concerning responses for a clinician to review",
    "Sends medication and follow-up appointment reminders",
    "Runs the full structured post-op recovery pathway",
  ],
  useCases: [
    "Reassuring worried patients after discharge",
    "Catching a wound concern at day 3 instead of the first follow-up",
    "Every surgery's follow-up plan running automatically",
  ],
  outcome: { stat: "5×", label: "more patients completing post-op check-ins" },
};