// Mirrors backend/src/services/agent_costing/agent_costing_services.py's
// DEFAULT_COSTS — same values, kept as a separate constant on purpose (see
// that file's own comment: different languages/deploys, update both
// deliberately). Used as the fallback when the real
// GET /api/v1/agent-costing call fails (backend not running, offline dev) —
// same graceful-degradation pattern used everywhere else in this dashboard.
//
// UPDATED: Now matches the consolidated 9-agent roster (was 31 old slugs).
// Legacy slugs removed: appointment_booking, reschedule_cancellation,
// multilingual_translation, ai_consultation, photo_analysis, video_consultation,
// medical_history_intake, risk_assessment, procedure_recommendation,
// pre_surgery_preparation, surgery_scheduling, surgeon_calendar,
// operating_room_scheduler, equipment_checklist, implant_inventory,
// surgical_documentation, recovery_followup, healing_monitoring,
// emergency_triage, medication_reminder, wound_care_guidance,
// recovery_dashboard, cost_estimation, payment_invoice, insurance_verification,
// analytics_dashboard, patient_feedback, marketing_followup, lead_nurturing.
export const DEFAULT_AGENT_COSTS: Record<string, number> = {
  // Front Desk & Intake — high-volume, cheap
  receptionist: 0.12,
  appointment_reminder: 0.06,
  // Consultation & Screening — multi-turn / dictation agents cost the most
  lead_qualification: 0.20,
  patient_intake: 0.25,
  consultation_assistant: 0.85,
  // Post-Op Care & Retention
  post_op_recovery: 0.25,
  marketing_retention: 0.18,
  // Business & Operations — finance/command
  finance_agent: 0.30,
  main_agent: 0.10,
};