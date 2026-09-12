import { PhoneCallIcon } from "lucide-react";
import type { Agent } from "./types";

export const receptionist: Agent = {
  slug: "receptionist",
  name: "AI Receptionist",
  desc: "Answers every call & chat 24/7, in a warm human voice.",
  icon: PhoneCallIcon,
  categoryId: "front-desk",
  tagline: "Front-line coverage that never sleeps, hangs up, or puts a lead on hold.",
  howItWorks:
    "Every inbound call and message is answered instantly by a warm, human-sounding AI that greets the patient, captures their name and reason for calling, and offers to book a consultation with the right surgeon — all while logging each exchange back to your dashboard so no conversation is ever lost.",
  capabilities: [
    "Answers inbound calls around the clock in natural speech",
    "Collects patient name, contact details and reason for contact",
    "Offers consultation bookings and hands off clean handovers",
    "Replies to chats across WhatsApp, Instagram and web",
    "Logs every interaction for a live transcript in your dashboard",
  ],
  useCases: [
    "After-hours calls that used to go to voicemail",
    "Lunch-rush phone traffic while front desk is busy",
    "High-volume Instagram and WhatsApp enquiries",
  ],
  outcome: { stat: "100%", label: "of inbound calls answered, day and night" },
};