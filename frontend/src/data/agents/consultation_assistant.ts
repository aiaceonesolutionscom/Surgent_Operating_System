import { StethoscopeIcon } from "lucide-react";
import type { Agent } from "./types";

export const consultationAssistant: Agent = {
  slug: "consultation_assistant",
  name: "Consultation Assistant",
  desc: "Dictates, structures and drafts SOAP notes during consults and surgeries.",
  icon: StethoscopeIcon,
  categoryId: "consultation",
  tagline: "Walk out of every consult with the notes already written.",
  howItWorks:
    "Listens to the consultation room and turns loose speech into clean, structured SOAP notes, procedure plans and surgeon instructions — appended straight to the patient record. Documentation that used to take an evening now finishes before the patient reaches the desk.",
  capabilities: [
    "Transcribes consults into structured SOAP notes",
    "Drafts procedure plans and pre-op instructions",
    "Updated patient records look complete before checkout",
    "Freeing surgeon hours every week from admin",
  ],
  useCases: [
    "Back-to-back consults with zero note backlog",
    "Consistent, audit-ready documentation across all surgeons",
    "Preparation notes for upcoming surgeries",
  ],
  outcome: { stat: "3+", label: "hours of documentation saved per week per surgeon" },
};