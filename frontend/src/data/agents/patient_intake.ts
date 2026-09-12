import { ClipboardListIcon } from "lucide-react";
import type { Agent } from "./types";

export const patientIntake: Agent = {
  slug: "patient_intake",
  name: "AI Patient Intake",
  desc: "Collects full medical history before the patient ever walks in.",
  icon: ClipboardListIcon,
  categoryId: "consultation",
  tagline: "A complete, organised patient file before the first consultation.",
  howItWorks:
    "Guides each patient through a structured pre-visit questionnaire — medical history, medications, allergies, goals and consent — over chat before the appointment. The answers arrive structured and waiting in the surgeon's clinical notes, ready to review.",
  capabilities: [
    "Collects medical history, medications and allergies pre-visit",
    "Captures patient goals and treatment expectations",
    "Handles the questionnaire over chat or patient portal",
    "Delivers structured, review-ready notes to the surgeon",
  ],
  useCases: [
    "Patients arriving with zero paperwork to fill in",
    "Consistent, complete histories on every new patient",
    "Saving 10+ minutes of front-desk admin per patient",
  ],
  outcome: { stat: "10+", label: "minutes of admin saved per new patient" },
};