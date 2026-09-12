import { CalendarClockIcon } from "lucide-react";
import type { Agent } from "./types";

export const appointmentReminder: Agent = {
  slug: "appointment_reminder",
  name: "Appointment & Booking Agent",
  desc: "Books, confirms and reminds — so no-shows become rare.",
  icon: CalendarClockIcon,
  categoryId: "front-desk",
  tagline: "A booking pipeline that confirms itself while your team sleeps.",
  howItWorks:
    "Handles the entire booking lifecycle: patients request times through chat or web, the agent checks real availability, books directly into your calendar, and sends polite confirmations and smart reminders leading up to the visit so cancellations get refilled.",
  capabilities: [
    "Schedules and reschedules appointments against real availability",
    "Sends confirmation + gentle reminder sequences before visits",
    "Fills cancelled slots from the waitlist automatically",
    "Reduces double-booking with a live, synced calendar",
  ],
  useCases: [
    "Patients booking consultations at 11pm",
    "Same-day cancellations turning into same-day bookings",
    "Over-booked surgeon calendars with scattered slots",
  ],
  outcome: { stat: "-30%", label: "fewer no-shows in the first month" },
};