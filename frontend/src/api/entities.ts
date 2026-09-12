// ============================================================================
// Entities — the practice-domain resource records (patients, doctors,
// appointments, conversations). All of these are authed (take authedFetch) —
// backend/src/router/conversations/conversations_router.py requires
// get_current_practice_user like every other domain here.
// ============================================================================

import { BASE_URL, ApiError } from "./client";

type AuthedFetch = <T>(path: string, init?: RequestInit) => Promise<T>;

// --- patients ---------------------------------------------------------------
export interface PatientResponse {
  id: string;
  practice_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  additional_phones: Array<{ number?: string; label?: string }>;
  date_of_birth: string | null;
  chief_complaint: string | null;
  needs_surgery: boolean;
  consent_status: boolean;
  ai_agent_assigned: string | null;
  agent_status: string;
  has_upcoming_appointment: boolean;
  has_completed_appointment: boolean;
  lifecycle_stage: string;
  lost_reason: string | null;
  source: string | null;
  // --- profile depth (Week 2) ---
  gender: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  allergies: Array<{ name?: string; severity?: string; reaction?: string }>;
  surgical_history: Array<{ procedure?: string; year?: number; facility?: string; notes?: string }>;
  current_medications: Array<{ name?: string; dosage?: string; frequency?: string }>;
  smoking_status: string | null;
  previous_cosmetic_procedures: Array<{ procedure?: string; year?: number; provider?: string }>;
  referral_source: string | null;
  preferred_language: string | null;
  communication_preferences: Record<string, boolean>;
  insurance_provider: string | null;
  insurance_number: string | null;
  // --- AI workflows (Week 4) ---
  qualification: {
    interested_procedure: string | null;
    budget_signal: string;
    urgency: string;
    score: number;
    summary: string;
  } | null;
  intake_summary: string | null;
  portal_id: string | null;
  portal_enabled: boolean;
  // --- Clinical ownership + lifecycle ---
  assigned_doctor_id: string | null;
  assigned_doctor_name: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreatePatientRequest {
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  additional_phones?: Array<{ number?: string; label?: string }>;
  date_of_birth?: string | null;
  gender?: string | null;
  chief_complaint?: string | null;
  needs_surgery?: boolean;
  ai_agent_assigned?: string | null;
  source?: string | null;
}

// Matches backend/src/router/patients/patients_router.py — a plain function
// that takes authedFetch rather than being a hook.
export function createPatient(authedFetch: AuthedFetch, data: CreatePatientRequest) {
  return authedFetch<PatientResponse>("/api/v1/patients", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listPatients(authedFetch: AuthedFetch, includeArchived = false) {
  return authedFetch<PatientResponse[]>(`/api/v1/patients${includeArchived ? "?include_archived=true" : ""}`);
}

// The raw, un-cached single-patient fetch — used by sections that need the
// full profile-depth fields (Week 2) that usePatients()'s mapped client-side
// Patient type doesn't carry, same reasoning as ClinicalSection/
// PatientPhotosGallery being self-fetching rather than reading the parent's
// cached list.
export function getPatientById(authedFetch: AuthedFetch, id: string) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${id}`);
}

export interface UpdatePatientRequest {
  first_name?: string;
  last_name?: string;
  email?: string | null;
  phone?: string | null;
  additional_phones?: Array<{ number?: string; label?: string }>;
  chief_complaint?: string | null;
  needs_surgery?: boolean;
  source?: string | null;
  gender?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  allergies?: Array<{ name?: string; severity?: string; reaction?: string }>;
  surgical_history?: Array<{ procedure?: string; year?: number; facility?: string; notes?: string }>;
  current_medications?: Array<{ name?: string; dosage?: string; frequency?: string }>;
  smoking_status?: string | null;
  previous_cosmetic_procedures?: Array<{ procedure?: string; year?: number; provider?: string }>;
  referral_source?: string | null;
  preferred_language?: string | null;
  communication_preferences?: Record<string, boolean>;
  insurance_provider?: string | null;
  insurance_number?: string | null;
}

export function updatePatient(authedFetch: AuthedFetch, id: string, data: UpdatePatientRequest) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- leads / CRM funnel -------------------------------------------------------
// Matches the funnel-stage additions to backend/src/router/patients/patients_router.py.
export interface FunnelStageCount {
  stage: string;
  count: number;
}

export function updatePatientStage(authedFetch: AuthedFetch, id: string, stage: string, lostReason?: string | null) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${id}/stage`, {
    method: "PATCH",
    body: JSON.stringify({ stage, lost_reason: lostReason ?? null })
  });
}

export function getFunnelSummary(authedFetch: AuthedFetch) {
  return authedFetch<FunnelStageCount[]>("/api/v1/patients/funnel-summary");
}

// --- doctor assignment + archive (Patient Management redesign) --------------
// Matches backend/src/router/patients/patients_router.py's assign-doctor/
// archive/restore/audit-log endpoints.

export function assignPatientDoctor(authedFetch: AuthedFetch, patientId: string, doctorId: string | null) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${patientId}/assign-doctor`, {
    method: "PATCH",
    body: JSON.stringify({ doctor_id: doctorId })
  });
}

export function archivePatient(authedFetch: AuthedFetch, patientId: string, reason?: string | null) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${patientId}/archive`, {
    method: "POST",
    body: JSON.stringify({ reason: reason ?? null })
  });
}

export function restorePatient(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PatientResponse>(`/api/v1/patients/${patientId}/restore`, {
    method: "POST"
  });
}

export interface PatientAuditLogEntry {
  id: string;
  action: string;
  actor_name: string | null;
  actor_type: string;
  resource_type: string | null;
  created_at: string;
}

export function getPatientAuditLog(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PatientAuditLogEntry[]>(`/api/v1/patients/${patientId}/audit-log`);
}

// --- doctors ----------------------------------------------------------------
export interface DoctorResponse {
  id: string;
  practice_id: string;
  user_id: string | null;
  name: string;
  email: string;
  phone: string | null;
  specialty: string | null;
  license_number: string | null;
  bio: string | null;
  photo_url: string | null;
  capabilities: string[];
  qualifications: Array<{ degree: string; institution: string | null; year: number | null }>;
  specializations: string[];
  working_hours: Record<string, Array<{ start: string; end: string }>>;
  commission_percent: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateDoctorRequest {
  name: string;
  email: string;
  phone?: string | null;
  specialty?: string | null;
  license_number?: string | null;
  bio?: string | null;
  capabilities?: string[];
}

export interface UpdateDoctorRequest {
  name?: string;
  email?: string;
  phone?: string | null;
  specialty?: string | null;
  license_number?: string | null;
  bio?: string | null;
  capabilities?: string[];
  is_active?: boolean;
}

export function createDoctor(authedFetch: AuthedFetch, data: CreateDoctorRequest) {
  return authedFetch<DoctorResponse>("/api/v1/doctors", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listDoctors(authedFetch: AuthedFetch) {
  return authedFetch<DoctorResponse[]>("/api/v1/doctors");
}

export function getDoctor(authedFetch: AuthedFetch, id: string) {
  return authedFetch<DoctorResponse>(`/api/v1/doctors/${id}`);
}

export function getMyDoctor(authedFetch: AuthedFetch) {
  return authedFetch<DoctorResponse>("/api/v1/doctors/me");
}

export function updateDoctor(authedFetch: AuthedFetch, id: string, data: UpdateDoctorRequest) {
  return authedFetch<DoctorResponse>(`/api/v1/doctors/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function inviteDoctor(authedFetch: AuthedFetch, id: string) {
  return authedFetch<DoctorResponse>(`/api/v1/doctors/${id}/invite`, {
    method: "POST"
  });
}

// --- appointments -----------------------------------------------------------
export interface AppointmentResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  doctor_id: string | null;
  appointment_type: string;
  status: string;
  start_time: string;
  end_time: string;
  checked_in_at: string | null;
  with_doctor_at: string | null;
  ready_for_checkout_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  patient_name: string | null;
}

export interface CreateAppointmentRequest {
  patient_id: string;
  doctor_id?: string | null;
  appointment_type: string;
  start_time: string;
  end_time: string;
  notes?: string | null;
}

export interface RescheduleAppointmentRequest {
  start_time: string;
  end_time: string;
}

export interface CancelAppointmentRequest {
  reason?: string | null;
}

// Matches backend/src/router/appointments/appointments_router.py. "me"
// resolves server-side to the caller's own linked Doctor row.
export function listMyAppointments(authedFetch: AuthedFetch) {
  return authedFetch<AppointmentResponse[]>("/api/v1/appointments?doctor_id=me");
}

// scope=practice — every doctor's appointments (Owner/Receptionist front-desk
// view), as opposed to listMyAppointments' own-schedule-only scope.
export function listPracticeAppointments(authedFetch: AuthedFetch) {
  return authedFetch<AppointmentResponse[]>("/api/v1/appointments?scope=practice");
}

// One patient's appointments, filtered server-side so a big practice never
// ships its entire appointment table to a page that only shows one patient's
// history. scope="practice" mirrors listPracticeAppointments (Owner/
// Receptionist); the default mirrors listMyAppointments (Doctor sees only
// their own schedule for that patient).
export function listPatientAppointments(authedFetch: AuthedFetch, patientId: string, scope: "practice" | "me" = "me") {
  const scopeParam = scope === "practice" ? "scope=practice" : "doctor_id=me";
  return authedFetch<AppointmentResponse[]>(`/api/v1/appointments?${scopeParam}&patient_id=${patientId}`);
}

// --- doctor personal time blocks --------------------------------------------
// A doctor's own private calendar note/block — no booking-engine effect,
// visible only to them. Matches backend/src/router/doctors/doctors_router.py's
// /me/time-blocks endpoints.
export interface DoctorTimeBlockResponse {
  id: string;
  doctor_id: string;
  title: string;
  note: string | null;
  start_time: string;
  end_time: string;
  created_at: string;
}

export interface CreateDoctorTimeBlockRequest {
  title: string;
  note?: string | null;
  start_time: string;
  end_time: string;
}

export function listMyTimeBlocks(authedFetch: AuthedFetch) {
  return authedFetch<DoctorTimeBlockResponse[]>("/api/v1/doctors/me/time-blocks");
}

export function createTimeBlock(authedFetch: AuthedFetch, data: CreateDoctorTimeBlockRequest) {
  return authedFetch<DoctorTimeBlockResponse>("/api/v1/doctors/me/time-blocks", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function deleteTimeBlock(authedFetch: AuthedFetch, id: string) {
  return authedFetch<void>(`/api/v1/doctors/me/time-blocks/${id}`, {
    method: "DELETE"
  });
}

export function createAppointment(authedFetch: AuthedFetch, data: CreateAppointmentRequest) {
  return authedFetch<AppointmentResponse>("/api/v1/appointments", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function rescheduleAppointment(authedFetch: AuthedFetch, id: string, data: RescheduleAppointmentRequest) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/reschedule`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function cancelAppointment(authedFetch: AuthedFetch, id: string, data: CancelAppointmentRequest) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/cancel`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function checkInAppointment(authedFetch: AuthedFetch, id: string) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/check-in`, {
    method: "PATCH"
  });
}

export function startWithDoctor(authedFetch: AuthedFetch, id: string) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/start-with-doctor`, {
    method: "PATCH"
  });
}

export function markReadyForCheckout(authedFetch: AuthedFetch, id: string) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/ready-for-checkout`, {
    method: "PATCH"
  });
}

export function completeAppointment(authedFetch: AuthedFetch, id: string) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/complete`, {
    method: "PATCH"
  });
}

export function markNoShow(authedFetch: AuthedFetch, id: string) {
  return authedFetch<AppointmentResponse>(`/api/v1/appointments/${id}/no-show`, {
    method: "PATCH"
  });
}

// --- waitlist -----------------------------------------------------------
export interface WaitlistEntryResponse {
  id: string;
  practice_id: string;
  patient_id: string | null;
  patient_name: string;
  phone: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  requested_date: string | null;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CreateWaitlistEntryRequest {
  patient_id?: string | null;
  patient_name: string;
  phone?: string | null;
  doctor_id?: string | null;
  requested_date?: string | null;
  notes?: string | null;
}

export function listWaitlist(authedFetch: AuthedFetch) {
  return authedFetch<WaitlistEntryResponse[]>("/api/v1/waitlist");
}

export function addToWaitlist(authedFetch: AuthedFetch, data: CreateWaitlistEntryRequest) {
  return authedFetch<WaitlistEntryResponse>("/api/v1/waitlist", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function fulfillWaitlistEntry(authedFetch: AuthedFetch, id: string) {
  return authedFetch<WaitlistEntryResponse>(`/api/v1/waitlist/${id}/fulfill`, {
    method: "PATCH"
  });
}

export function cancelWaitlistEntry(authedFetch: AuthedFetch, id: string) {
  return authedFetch<WaitlistEntryResponse>(`/api/v1/waitlist/${id}/cancel`, {
    method: "PATCH"
  });
}

// --- doctor "today at a glance" ------------------------------------------
export interface WaitingRoomEntry {
  appointment_id: string;
  patient_id: string;
  patient_name: string;
  appointment_type: string;
  status: string;
  checked_in_at: string | null;
  with_doctor_at: string | null;
}

export interface PendingNoteEntry {
  note_id: string;
  patient_id: string;
  patient_name: string;
  appointment_id: string | null;
  created_at: string;
}

export interface DoctorAlertEntry {
  type: string;
  patient_id: string;
  patient_name: string;
  message: string;
  since: string;
}

export interface DoctorTodayResponse {
  waiting_room: WaitingRoomEntry[];
  pending_notes: PendingNoteEntry[];
  pending_consent_count: number;
  alerts: DoctorAlertEntry[];
}

export function getMyToday(authedFetch: AuthedFetch) {
  return authedFetch<DoctorTodayResponse>("/api/v1/doctors/me/today");
}

// --- doctor applications ------------------------------------------------------
export interface DocumentEntry {
  name: string;
  url: string;
  uploaded_at: string;
}

export interface SubmitDoctorApplicationRequest {
  name: string;
  email: string;
  phone?: string | null;
  specialty?: string | null;
  license_number?: string | null;
  bio?: string | null;
  photo_url?: string | null;
  documents?: DocumentEntry[];
}

export interface DoctorApplicationResponse {
  id: string;
  practice_id: string;
  name: string;
  email: string;
  phone: string | null;
  specialty: string | null;
  license_number: string | null;
  bio: string | null;
  photo_url: string | null;
  documents: DocumentEntry[];
  status: "pending" | "approved" | "rejected";
  rejected_reason: string | null;
  doctor_id: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export interface ApplicationUploadResponse {
  url: string;
  name: string;
}

// Matches backend/src/router/doctor_applications/doctor_applications_router.py.
// Self-service endpoints (me/*) work while the applicant's account is still
// inactive (pending Owner review) — they're gated by get_current_user_record,
// not the stricter get_current_practice_user every other authed call uses.
export function uploadApplicationFile(authedFetch: AuthedFetch, file: File) {
  const form = new FormData();
  form.append("file", file);
  return authedFetch<ApplicationUploadResponse>("/api/v1/doctor-applications/me/upload", {
    method: "POST",
    body: form
  });
}

export function submitMyApplication(authedFetch: AuthedFetch, data: SubmitDoctorApplicationRequest) {
  return authedFetch<DoctorApplicationResponse>("/api/v1/doctor-applications/me", {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

export function getMyApplication(authedFetch: AuthedFetch) {
  return authedFetch<DoctorApplicationResponse>("/api/v1/doctor-applications/me");
}

// ============================================================================
// Org requests — the free "new organization" self-signup path (plain
// /sign-up, no invite/apply code). Matches backend/src/router/practice/
// practice_router.py's request-org/my-org-request endpoints — a Super Admin
// reviews these from the /super-admin/org-requests queue.
// ============================================================================
export interface OrgRequestResponse {
  id: string;
  email: string;
  org_name: string | null;
  status: "pending" | "approved" | "rejected";
  rejected_reason: string | null;
}

export function submitOrgRequest(authedFetch: AuthedFetch, orgName: string) {
  return authedFetch<OrgRequestResponse>("/api/v1/practice/request-org", {
    method: "POST",
    body: JSON.stringify({ org_name: orgName })
  });
}

export function getMyOrgRequest(authedFetch: AuthedFetch) {
  return authedFetch<OrgRequestResponse>("/api/v1/practice/my-org-request");
}

// ============================================================================
// Green API (WhatsApp) self-connect — Owner-only. Matches backend/src/router/
// practice/practice_router.py's /practice/settings/green-api endpoints.
// ============================================================================
export interface GreenApiSettingsResponse {
  connected: boolean;
  instance_id: string | null;
  state: string | null;
  error: string | null;
}

export function getGreenApiSettings(authedFetch: AuthedFetch) {
  return authedFetch<GreenApiSettingsResponse>("/api/v1/practice/settings/green-api");
}

export function updateGreenApiSettings(authedFetch: AuthedFetch, instanceId: string, apiToken: string) {
  return authedFetch<GreenApiSettingsResponse>("/api/v1/practice/settings/green-api", {
    method: "PATCH",
    body: JSON.stringify({ instance_id: instanceId, api_token: apiToken })
  });
}

export function disconnectGreenApi(authedFetch: AuthedFetch) {
  return authedFetch<void>("/api/v1/practice/settings/green-api", { method: "DELETE" });
}

// ============================================================================
// Meta (Instagram/Facebook) self-connect — Owner-only. `configured` reflects
// whether the PLATFORM has a real Facebook App set up at all (not something
// any individual Owner can fix) — see backend/src/services/channels/meta_service.py.
// ============================================================================
export interface MetaSettingsResponse {
  configured: boolean;
  connected: boolean;
  page_id: string | null;
  page_name: string | null;
  ig_business_id: string | null;
}

export function getMetaSettings(authedFetch: AuthedFetch) {
  return authedFetch<MetaSettingsResponse>("/api/v1/practice/settings/meta");
}

export function getMetaConnectUrl(authedFetch: AuthedFetch, redirectUri: string) {
  return authedFetch<{ url: string; state: string }>(`/api/v1/practice/settings/meta/connect-url?redirect_uri=${encodeURIComponent(redirectUri)}`);
}

export function completeMetaConnect(authedFetch: AuthedFetch, code: string, state: string, redirectUri: string) {
  return authedFetch<MetaSettingsResponse>("/api/v1/practice/settings/meta/callback", {
    method: "POST",
    body: JSON.stringify({ code, state, redirect_uri: redirectUri })
  });
}

export function disconnectMeta(authedFetch: AuthedFetch) {
  return authedFetch<void>("/api/v1/practice/settings/meta", { method: "DELETE" });
}

// Owner-only below (require_role(OWNER) server-side).
export function listApplications(authedFetch: AuthedFetch, status?: string) {
  const qs = status ? `?status=${status}` : "";
  return authedFetch<DoctorApplicationResponse[]>(`/api/v1/doctor-applications${qs}`);
}

export function getApplication(authedFetch: AuthedFetch, id: string) {
  return authedFetch<DoctorApplicationResponse>(`/api/v1/doctor-applications/${id}`);
}

export function approveApplication(authedFetch: AuthedFetch, id: string, permissions: string[]) {
  return authedFetch<DoctorResponse>(`/api/v1/doctor-applications/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ permissions })
  });
}

export function rejectApplication(authedFetch: AuthedFetch, id: string, reason?: string) {
  return authedFetch<DoctorApplicationResponse>(`/api/v1/doctor-applications/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function deleteApplication(authedFetch: AuthedFetch, id: string) {
  return authedFetch<void>(`/api/v1/doctor-applications/${id}`, {
    method: "DELETE"
  });
}

// --- receptionist applications ----------------------------------------------
// The receptionist mirror of the doctor self-application flow above — link
// sign-up, then an Owner approves before the account activates. Matches
// backend/src/router/staff_applications/staff_applications_router.py.
// Self-service endpoints (me/*) work while the applicant's account is still
// inactive (pending Owner review) — same get_current_user_record gating.

export interface SubmitStaffApplicationRequest {
  name: string;
  email: string;
  phone?: string | null;
}

export interface StaffApplicationResponse {
  id: string;
  practice_id: string;
  name: string;
  email: string;
  phone: string | null;
  status: "pending" | "approved" | "rejected";
  rejected_reason: string | null;
  user_id: string | null;
  submitted_at: string;
  reviewed_at: string | null;
}

export function submitMyStaffApplication(authedFetch: AuthedFetch, data: SubmitStaffApplicationRequest) {
  return authedFetch<StaffApplicationResponse>("/api/v1/staff-applications/me", {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

export function getMyStaffApplication(authedFetch: AuthedFetch) {
  return authedFetch<StaffApplicationResponse>("/api/v1/staff-applications/me");
}

// Owner-only below (require_role(OWNER) server-side).
export function listStaffApplications(authedFetch: AuthedFetch, status?: string) {
  const qs = status ? `?status=${status}` : "";
  return authedFetch<StaffApplicationResponse[]>(`/api/v1/staff-applications${qs}`);
}

export function approveStaffApplication(authedFetch: AuthedFetch, id: string, permissions: string[]) {
  return authedFetch<StaffResponse>(`/api/v1/staff-applications/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ permissions })
  });
}

export function rejectStaffApplication(authedFetch: AuthedFetch, id: string, reason?: string) {
  return authedFetch<StaffApplicationResponse>(`/api/v1/staff-applications/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

// --- attendance ---------------------------------------------------------------
export interface AttendanceRecordResponse {
  id: string;
  practice_id: string;
  user_id: string;
  doctor_id: string | null;
  work_date: string;
  check_in_at: string;
  check_out_at: string | null;
  worked_minutes: number | null;
  status: "checked_in" | "checked_out";
}

// Matches backend/src/router/attendance/attendance_router.py.
export function checkIn(authedFetch: AuthedFetch) {
  return authedFetch<AttendanceRecordResponse>("/api/v1/attendance/check-in", { method: "POST" });
}

export function checkOut(authedFetch: AuthedFetch) {
  return authedFetch<AttendanceRecordResponse>("/api/v1/attendance/check-out", { method: "POST" });
}

export function listMyAttendance(authedFetch: AuthedFetch, month?: string) {
  return authedFetch<AttendanceRecordResponse[]>(`/api/v1/attendance/me${month ? `?month=${month}` : ""}`);
}

export interface TeamPresenceItem {
  user_id: string | null;
  name: string;
  role: "doctor" | "receptionist";
  doctor_id: string | null;
  status: "checked_in" | "checked_out" | "absent";
  check_in_at: string | null;
  check_out_at: string | null;
  worked_minutes: number | null;
  scheduled_today: boolean;
  scheduled_start: string | null;
  scheduled_end: string | null;
  late_minutes: number | null;
}

export function listTeamAttendance(authedFetch: AuthedFetch, date?: string) {
  return authedFetch<TeamPresenceItem[]>(`/api/v1/attendance/team${date ? `?date=${date}` : ""}`);
}

export interface AttendanceDayRecord {
  work_date: string;
  check_in_at: string;
  check_out_at: string | null;
  worked_minutes: number | null;
  late_minutes: number | null;
}

export interface TeamMonthMember {
  user_id: string | null;
  name: string;
  role: "doctor" | "receptionist";
  doctor_id: string | null;
  records: AttendanceDayRecord[];
  present_days: number;
  total_minutes: number;
}

export interface TeamMonthResponse {
  month: string;
  members: TeamMonthMember[];
}

export function listTeamMonthRecords(authedFetch: AuthedFetch, month: string) {
  return authedFetch<TeamMonthResponse>(`/api/v1/attendance/team/records?month=${month}`);
}

// --- conversations ----------------------------------------------------------
export interface ConversationListItem {
  id: string;
  patient_id: string | null;
  patient_name: string;
  agent_type: string;
  channel: string;
  status: string;
  last_message_preview: string;
  updated_at: string;
  avatar_url: string | null;
  ai_paused: boolean;
  ai_booked_appointment_id: string | null;
  extra_data?: Record<string, unknown>;
  // Set by backend for Patient Messages (owner read-only); effectively false
  // on those conversations for the Owner, true everywhere else.
  can_reply: boolean;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: string;
  content: string;
  content_type: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationListItem {
  messages: MessageResponse[];
}

export async function listConversations(
  authedFetch: AuthedFetch,
  params?: {
    status?: string;
    channel?: string;
    agent_type?: string[];
    search?: string;
    patient_id?: string;
    limit?: number;
    offset?: number;
  }
): Promise<ConversationListItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.channel) query.set("channel", params.channel);
  if (params?.agent_type) params.agent_type.forEach((t) => query.append("agent_type", t));
  if (params?.search) query.set("search", params.search);
  if (params?.patient_id) query.set("patient_id", params.patient_id);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));
  const qs = query.toString();
  return authedFetch<ConversationListItem[]>(`/api/v1/conversations${qs ? `?${qs}` : ""}`);
}

export async function getConversation(authedFetch: AuthedFetch, id: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/${id}`);
}

export async function resolveConversation(authedFetch: AuthedFetch, id: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/${id}/resolve`, {
    method: "POST",
  });
}

// A staff member replying directly (sends over WhatsApp/etc. if the
// conversation has a real channel, and pauses AI auto-reply for it).
export async function sendConversationMessage(authedFetch: AuthedFetch, id: string, body: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function toggleConversationAi(authedFetch: AuthedFetch, id: string, paused: boolean): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/${id}/toggle-ai`, {
    method: "POST",
    body: JSON.stringify({ paused }),
  });
}

// --- Patient Messages (portal: patient → assigned doctor) ---------------

// Conversations a patient sent their own doctor through the portal, in the
// dedicated Patient Messages inbox (MessagesPage's "Patient messages" tab,
// plus the doctor's per-patient Communication tab). Backend access: assigned
// doctor + receptionist can reply; owner sees them read-only; other doctors
// don't see them at all.

export async function listPatientMessages(
  authedFetch: AuthedFetch,
  params?: { limit?: number; offset?: number }
): Promise<ConversationListItem[]> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  const query = qs.toString();
  return authedFetch<ConversationListItem[]>(`/api/v1/conversations/patient-messages${query ? `?${query}` : ""}`);
}

export async function getPatientMessage(authedFetch: AuthedFetch, id: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/patient-messages/${id}`);
}

export async function sendPatientMessage(authedFetch: AuthedFetch, id: string, body: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/patient-messages/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}

export async function resolvePatientMessage(authedFetch: AuthedFetch, id: string): Promise<ConversationDetail> {
  return authedFetch<ConversationDetail>(`/api/v1/conversations/patient-messages/${id}/resolve`, {
    method: "POST",
  });
}

// --- analytics ----------------------------------------------------------------
export interface OverviewSummaryResponse {
  sessions_today: number;
  needs_attention: number;
  bookings_this_week: number;
  // Sum of completed TreatmentPlanItems' actual/estimated price — real,
  // clinically-linked revenue. null (not 0) when nothing is completed yet,
  // so the UI can show an honest "not enough data" state.
  revenue_estimate: number | null;
}

export interface ChannelCount {
  channel: string;
  count: number;
}

export interface CategoryCount {
  category: string;
  count: number;
}

export interface SessionAnalyticsResponse {
  total_conversations: number;
  active_count: number;
  needs_attention_count: number;
  resolved_count: number;
  by_channel: ChannelCount[];
  by_category: CategoryCount[];
}

// Matches backend/src/router/analytics/analytics_router.py — real aggregates
// over Conversation/Appointment, replacing MOCK_SESSIONS-derived numbers.
export function getOverviewSummary(authedFetch: AuthedFetch) {
  return authedFetch<OverviewSummaryResponse>("/api/v1/analytics/overview");
}

export function getSessionAnalytics(authedFetch: AuthedFetch) {
  return authedFetch<SessionAnalyticsResponse>("/api/v1/analytics/sessions");
}

// --- staff (receptionists) ---------------------------------------------------
// Matches backend/src/router/staff/staff_router.py. Owner-only — permissions
// live directly on the User row (data/receptionist_permissions.py), not a
// separate roster entity like Doctor.
export interface StaffResponse {
  id: string;
  practice_id: string;
  email: string;
  name: string | null;
  phone: string | null;
  role: string;
  permissions: string[];
  is_active: boolean;
  work_schedule: Record<string, Array<{ start: string; end: string }>>;
  created_at: string;
  updated_at: string;
}

export interface InviteStaffRequest {
  email: string;
  permissions?: string[];
}

export interface InviteStaffResponse {
  email: string;
  permissions: string[];
}

export interface UpdateStaffRequest {
  permissions?: string[];
  is_active?: boolean;
}

export function inviteStaff(authedFetch: AuthedFetch, data: InviteStaffRequest) {
  return authedFetch<InviteStaffResponse>("/api/v1/staff", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listStaff(authedFetch: AuthedFetch) {
  return authedFetch<StaffResponse[]>("/api/v1/staff");
}

export function updateStaff(authedFetch: AuthedFetch, id: string, data: UpdateStaffRequest) {
  return authedFetch<StaffResponse>(`/api/v1/staff/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// The Owner's "help them log back in" lever — resends the original Clerk
// invite to this receptionist's email, for when their session/account is
// gone (e.g. a wiped local Clerk dev instance) rather than a permissions
// change. Backend relinks the SAME User row on completion, never a duplicate.
export function resendStaffAccess(authedFetch: AuthedFetch, id: string) {
  return authedFetch<StaffResponse>(`/api/v1/staff/${id}/resend-access`, { method: "POST" });
}

// A staff member's own profile — self-service is limited to the recurring
// weekly schedule (name/role/permissions are Owner-owned on the backend).
export function getMyStaff(authedFetch: AuthedFetch) {
  return authedFetch<StaffResponse>("/api/v1/staff/me");
}

export function updateMySchedule(authedFetch: AuthedFetch, work_schedule: StaffResponse["work_schedule"]) {
  return authedFetch<StaffResponse>("/api/v1/staff/me", {
    method: "PATCH",
    body: JSON.stringify({ work_schedule })
  });
}

// A staff member's own profile — self-service covers the recurring weekly
// schedule and phone number only (name/email/role are Owner-owned).
export interface UpdateMyStaffRequest {
  work_schedule?: StaffResponse["work_schedule"];
  phone?: string | null;
}

export function updateMyStaff(authedFetch: AuthedFetch, data: UpdateMyStaffRequest) {
  return authedFetch<StaffResponse>("/api/v1/staff/me", {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// A doctor's own recurring weekly schedule (working_hours only).
export function updateMyDoctorSchedule(authedFetch: AuthedFetch, working_hours: Record<string, Array<{ start: string; end: string }>>) {
  return authedFetch<unknown>("/api/v1/doctors/me", {
    method: "PATCH",
    body: JSON.stringify({ working_hours })
  });
}

// A doctor's own profile — contact, education, license, and schedule are
// self-service. Name and photo are deliberately NOT in this shape; those stay
// Owner-owned (backend UpdateMyDoctorRequest whitelists them out).
export interface UpdateMyDoctorProfileRequest {
  email?: string;
  phone?: string | null;
  specialty?: string | null;
  bio?: string | null;
  license_number?: string | null;
  qualifications?: DoctorResponse["qualifications"];
  specializations?: string[];
  working_hours?: Record<string, Array<{ start: string; end: string }>>;
}

export function updateMyDoctorProfile(authedFetch: AuthedFetch, data: UpdateMyDoctorProfileRequest) {
  return authedFetch<DoctorResponse>("/api/v1/doctors/me", {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- procedures ---------------------------------------------------------------
// Matches backend/src/router/procedures/procedures_router.py — the practice's
// own procedure/pricing catalog. No seeded data; the Owner enters their own.
export interface ProcedureResponse {
  id: string;
  practice_id: string;
  name: string;
  category: string | null;
  description: string | null;
  base_price: number | null;
  duration_minutes: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateProcedureRequest {
  name: string;
  category?: string | null;
  description?: string | null;
  base_price?: number | null;
  duration_minutes?: number | null;
}

export interface UpdateProcedureRequest {
  name?: string;
  category?: string | null;
  description?: string | null;
  base_price?: number | null;
  duration_minutes?: number | null;
  is_active?: boolean;
}

export function createProcedure(authedFetch: AuthedFetch, data: CreateProcedureRequest) {
  return authedFetch<ProcedureResponse>("/api/v1/procedures", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listProcedures(authedFetch: AuthedFetch, activeOnly = false) {
  return authedFetch<ProcedureResponse[]>(`/api/v1/procedures${activeOnly ? "?active_only=true" : ""}`);
}

export function updateProcedure(authedFetch: AuthedFetch, id: string, data: UpdateProcedureRequest) {
  return authedFetch<ProcedureResponse>(`/api/v1/procedures/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- clinical (consultation notes + treatment plans) --------------------------
// Matches backend/src/router/clinical/clinical_router.py. Owner/Doctor only —
// deliberately excludes Receptionist (see the router's own comment).
export interface ConsultationNoteResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  doctor_id: string;
  appointment_id: string | null;
  chief_complaint: string | null;
  subjective: string | null;
  objective: string | null;
  assessment: string | null;
  plan: string | null;
  status: "draft" | "final";
  created_at: string;
  updated_at: string;
}

export interface CreateConsultationNoteRequest {
  patient_id: string;
  appointment_id?: string | null;
  chief_complaint?: string | null;
  subjective?: string | null;
  objective?: string | null;
  assessment?: string | null;
  plan?: string | null;
  status?: "draft" | "final";
}

export interface UpdateConsultationNoteRequest {
  chief_complaint?: string | null;
  subjective?: string | null;
  objective?: string | null;
  assessment?: string | null;
  plan?: string | null;
  status?: "draft" | "final";
}

export function createConsultationNote(authedFetch: AuthedFetch, data: CreateConsultationNoteRequest) {
  return authedFetch<ConsultationNoteResponse>("/api/v1/clinical/notes", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listConsultationNotes(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<ConsultationNoteResponse[]>(`/api/v1/clinical/notes?patient_id=${patientId}`);
}

export function updateConsultationNote(authedFetch: AuthedFetch, id: string, data: UpdateConsultationNoteRequest) {
  return authedFetch<ConsultationNoteResponse>(`/api/v1/clinical/notes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- Consultation Assistant (Week 4 AI workflow) ---

export interface AIConsultationDraftRequest {
  patient_id: string;
  raw_notes: string;
}

export interface AIConsultationDraftResponse {
  subjective: string;
  objective: string;
  assessment: string;
  plan: string;
  follow_up_tasks: string[];
}

export function aiDraftConsultationNote(authedFetch: AuthedFetch, data: AIConsultationDraftRequest) {
  return authedFetch<AIConsultationDraftResponse>("/api/v1/clinical/notes/ai-draft", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export interface TranscriptionResponse {
  text: string;
}

export function transcribeDictation(authedFetch: AuthedFetch, audioBlob: Blob, filename: string) {
  const form = new FormData();
  form.append("file", audioBlob, filename);
  return authedFetch<TranscriptionResponse>("/api/v1/clinical/notes/transcribe", {
    method: "POST",
    body: form
  });
}

export interface TreatmentPlanItemResponse {
  id: string;
  treatment_plan_id: string;
  procedure_id: string;
  phase_order: number;
  estimated_price: number | null;
  status: "planned" | "scheduled" | "completed" | "cancelled";
  scheduled_appointment_id: string | null;
  performed_at: string | null;
  actual_price: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TreatmentPlanResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  doctor_id: string;
  consultation_note_id: string | null;
  title: string;
  status: "draft" | "proposed" | "accepted" | "completed" | "cancelled";
  items: TreatmentPlanItemResponse[];
  created_at: string;
  updated_at: string;
}

export interface CreateTreatmentPlanItemRequest {
  procedure_id: string;
  phase_order?: number;
  estimated_price?: number | null;
  notes?: string | null;
}

export interface CreateTreatmentPlanRequest {
  patient_id: string;
  consultation_note_id?: string | null;
  title: string;
  items?: CreateTreatmentPlanItemRequest[];
}

export interface UpdateTreatmentPlanRequest {
  title?: string;
  status?: TreatmentPlanResponse["status"];
}

export interface UpdateTreatmentPlanItemRequest {
  status?: TreatmentPlanItemResponse["status"];
  estimated_price?: number | null;
  actual_price?: number | null;
  scheduled_appointment_id?: string | null;
  notes?: string | null;
}

export function createTreatmentPlan(authedFetch: AuthedFetch, data: CreateTreatmentPlanRequest) {
  return authedFetch<TreatmentPlanResponse>("/api/v1/clinical/treatment-plans", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listTreatmentPlans(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<TreatmentPlanResponse[]>(`/api/v1/clinical/treatment-plans?patient_id=${patientId}`);
}

export function getTreatmentPlan(authedFetch: AuthedFetch, id: string) {
  return authedFetch<TreatmentPlanResponse>(`/api/v1/clinical/treatment-plans/${id}`);
}

export function updateTreatmentPlan(authedFetch: AuthedFetch, id: string, data: UpdateTreatmentPlanRequest) {
  return authedFetch<TreatmentPlanResponse>(`/api/v1/clinical/treatment-plans/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function updateTreatmentPlanItem(authedFetch: AuthedFetch, id: string, data: UpdateTreatmentPlanItemRequest) {
  return authedFetch<TreatmentPlanItemResponse>(`/api/v1/clinical/treatment-plan-items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- patient photos -----------------------------------------------------------
// Matches backend/src/router/patient_photos/patient_photos_router.py.
// Owner/Doctor only (clinical photography), like clinical notes.
export type PhotoStage = "before" | "day7" | "day14" | "1mo" | "3mo" | "6mo" | "1yr" | "other";
export const PHOTO_STAGES: { value: PhotoStage; label: string }[] = [
  { value: "before", label: "Before" },
  { value: "day7", label: "Day 7" },
  { value: "day14", label: "Day 14" },
  { value: "1mo", label: "1 month" },
  { value: "3mo", label: "3 months" },
  { value: "6mo", label: "6 months" },
  { value: "1yr", label: "1 year" },
  { value: "other", label: "Other" }
];

export interface PatientPhotoResponse {
  id: string;
  patient_id: string;
  cloudinary_url: string;
  photo_type: string | null;
  notes: string | null;
  stage: PhotoStage | null;
  body_area: string | null;
  procedure_id: string | null;
  is_marketing_approved: boolean;
  created_at: string;
}

export function uploadPatientPhoto(
  authedFetch: AuthedFetch,
  patientId: string,
  file: File,
  photoType?: string,
  notes?: string,
  stage?: string,
  bodyArea?: string,
  procedureId?: string
) {
  const form = new FormData();
  form.append("file", file);
  if (photoType) form.append("photo_type", photoType);
  if (notes) form.append("notes", notes);
  if (stage) form.append("stage", stage);
  if (bodyArea) form.append("body_area", bodyArea);
  if (procedureId) form.append("procedure_id", procedureId);
  return authedFetch<PatientPhotoResponse>(`/api/v1/patients/${patientId}/photos`, {
    method: "POST",
    body: form
  });
}

export function listPatientPhotos(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PatientPhotoResponse[]>(`/api/v1/patients/${patientId}/photos`);
}

export interface UpdatePatientPhotoRequest {
  stage?: string | null;
  body_area?: string | null;
  procedure_id?: string | null;
  is_marketing_approved?: boolean | null;
  notes?: string | null;
}

export function updatePatientPhoto(authedFetch: AuthedFetch, photoId: string, data: UpdatePatientPhotoRequest) {
  return authedFetch<PatientPhotoResponse>(`/api/v1/patient-photos/${photoId}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function deletePatientPhoto(authedFetch: AuthedFetch, photoId: string) {
  return authedFetch<void>(`/api/v1/patient-photos/${photoId}`, {
    method: "DELETE"
  });
}

// --- consent documents ---------------------------------------------------------
// Matches backend/src/router/consent/consent_router.py. Open to any active
// practice role (Owner/Doctor/Receptionist) — administrative/legal, not
// clinical judgment, unlike notes/photos.
// The fixed set of consent types this practice can raise a document for —
// matches backend/src/models/consent_document.py's own comment on the
// intended real vocabulary (still free text server-side, but the frontend
// only ever offers these).
export const CONSENT_DOCUMENT_TYPES = [
  "procedure",
  "anesthesia",
  "photo",
  "marketing",
  "financial",
  "cancellation_policy",
  "privacy_acknowledgement"
] as const;

export interface ConsentDocumentResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  document_type: string;
  content: string | null;
  version: number;
  template_id: string | null;
  template_version: number | null;
  status: "draft" | "sent" | "signed" | "void";
  signed_at: string | null;
  signed_by_name: string | null;
  witnessed_by: string | null;
  discussed_at: string | null;
  discussed_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateConsentDocumentRequest {
  document_type: string;
  content?: string | null;
  template_id?: string | null;
}

// --- consent templates ----------------------------------------------------
export interface ConsentTemplateResponse {
  id: string;
  practice_id: string;
  document_type: string;
  version: number;
  body: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateConsentTemplateRequest {
  document_type: string;
  body: string;
}

export interface UpdateConsentTemplateRequest {
  body?: string | null;
  is_active?: boolean | null;
}

export function createConsentTemplate(authedFetch: AuthedFetch, data: CreateConsentTemplateRequest) {
  return authedFetch<ConsentTemplateResponse>("/api/v1/consent-templates", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listConsentTemplates(authedFetch: AuthedFetch) {
  return authedFetch<ConsentTemplateResponse[]>("/api/v1/consent-templates");
}

export function updateConsentTemplate(authedFetch: AuthedFetch, id: string, data: UpdateConsentTemplateRequest) {
  return authedFetch<ConsentTemplateResponse>(`/api/v1/consent-templates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function createConsentDocument(authedFetch: AuthedFetch, patientId: string, data: CreateConsentDocumentRequest) {
  return authedFetch<ConsentDocumentResponse>(`/api/v1/patients/${patientId}/consent-documents`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listConsentDocuments(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<ConsentDocumentResponse[]>(`/api/v1/patients/${patientId}/consent-documents`);
}

export function signConsentDocument(authedFetch: AuthedFetch, id: string, signedByName: string) {
  return authedFetch<ConsentDocumentResponse>(`/api/v1/consent-documents/${id}/sign`, {
    method: "POST",
    body: JSON.stringify({ signed_by_name: signedByName })
  });
}

export function voidConsentDocument(authedFetch: AuthedFetch, id: string) {
  return authedFetch<ConsentDocumentResponse>(`/api/v1/consent-documents/${id}/void`, {
    method: "POST"
  });
}

// Doctor's one consent action — see consent_router.py's role split.
export function markConsentDiscussed(authedFetch: AuthedFetch, id: string) {
  return authedFetch<ConsentDocumentResponse>(`/api/v1/consent-documents/${id}/mark-discussed`, {
    method: "POST"
  });
}

// --- surgery ---------------------------------------------------------------
// Matches backend/src/router/surgery/surgery_router.py. Owner/Doctor only,
// same clinical-visibility boundary as consultation notes and photos.
export interface SurgeryResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  patient_name: string | null;
  procedure_id: string | null;
  procedure_name: string | null;
  doctor_id: string;
  doctor_name: string | null;
  assistant_doctor_id: string | null;
  assistant_doctor_name: string | null;
  scheduled_appointment_id: string | null;
  recovery_journal_id: string | null;
  scheduled_date: string;
  duration_estimate_minutes: number | null;
  anesthesia_type: string | null;
  facility_note: string | null;
  pre_op_checklist: Array<{ item: string; checked: boolean; checked_by?: string | null; checked_at?: string | null }>;
  implants_used: Array<{ type?: string; manufacturer?: string; lot_number?: string; size?: string }>;
  operative_note: string | null;
  status: "planned" | "completed" | "cancelled";
  created_at: string;
  updated_at: string;
}

export interface CreateSurgeryRequest {
  patient_id: string;
  procedure_id?: string | null;
  doctor_id: string;
  assistant_doctor_id?: string | null;
  scheduled_appointment_id?: string | null;
  scheduled_date: string;
  duration_estimate_minutes?: number | null;
  anesthesia_type?: string | null;
  facility_note?: string | null;
  pre_op_checklist?: Array<{ item: string; checked: boolean }>;
}

export interface UpdateSurgeryRequest {
  scheduled_date?: string | null;
  duration_estimate_minutes?: number | null;
  anesthesia_type?: string | null;
  facility_note?: string | null;
  assistant_doctor_id?: string | null;
  pre_op_checklist?: Array<{ item: string; checked: boolean }> | null;
  implants_used?: Array<{ type?: string; manufacturer?: string; lot_number?: string; size?: string }> | null;
  operative_note?: string | null;
}

export interface CompleteSurgeryRequest {
  operative_note: string;
  implants_used?: Array<{ type?: string; manufacturer?: string; lot_number?: string; size?: string }>;
}

export function createSurgery(authedFetch: AuthedFetch, data: CreateSurgeryRequest) {
  return authedFetch<SurgeryResponse>("/api/v1/surgeries", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listSurgeries(authedFetch: AuthedFetch, patientId?: string, scope?: "all" | "mine") {
  return authedFetch<SurgeryResponse[]>(
    `/api/v1/surgeries${patientId || scope ? `?${patientId ? `patient_id=${patientId}${scope ? "&" : ""}` : ""}${scope ? `scope=${scope}` : ""}` : ""}`
  );
}

export function getSurgery(authedFetch: AuthedFetch, id: string) {
  return authedFetch<SurgeryResponse>(`/api/v1/surgeries/${id}`);
}

export function updateSurgery(authedFetch: AuthedFetch, id: string, data: UpdateSurgeryRequest) {
  return authedFetch<SurgeryResponse>(`/api/v1/surgeries/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function completeSurgery(authedFetch: AuthedFetch, id: string, data: CompleteSurgeryRequest) {
  return authedFetch<SurgeryResponse>(`/api/v1/surgeries/${id}/complete`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function cancelSurgery(authedFetch: AuthedFetch, id: string) {
  return authedFetch<SurgeryResponse>(`/api/v1/surgeries/${id}/cancel`, {
    method: "POST"
  });
}

// --- invoices (billing) --------------------------------------------------------
// Matches backend/src/router/billing/billing_router.py. Viewing is open to
// Owner/Doctor/Receptionist; creating/editing (incl. mark-paid) is
// Owner/Receptionist only — same split as consent documents' manage roles.
export interface InvoiceLineItemResponse {
  id: string;
  invoice_id: string;
  treatment_plan_item_id: string | null;
  description: string;
  quantity: number;
  unit_price: number;
  created_at: string;
  updated_at: string;
}

export interface PaymentResponse {
  id: string;
  invoice_id: string;
  amount: number;
  currency: string;
  method: "cash" | "card_manual" | "bank_transfer" | "stripe" | "other";
  recorded_by: string | null;
  notes: string | null;
  paid_at: string;
  created_at: string;
}

export interface InvoiceResponse {
  id: string;
  practice_id: string;
  patient_id: string;
  appointment_id: string | null;
  treatment_plan_id: string | null;
  subtotal_amount: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  status: "pending" | "partially_paid" | "paid" | "overdue" | "cancelled" | "refunded";
  currency: string;
  exchange_rate_to_base: number | null;
  due_date: string | null;
  paid_at: string | null;
  line_items: InvoiceLineItemResponse[];
  payments: PaymentResponse[];
  amount_paid: number;
  balance_due: number;
  created_at: string;
  updated_at: string;
}

export interface CreateInvoiceLineItemRequest {
  treatment_plan_item_id?: string | null;
  description: string;
  quantity?: number;
  unit_price: number;
}

export interface CreateInvoiceRequest {
  patient_id: string;
  appointment_id?: string | null;
  treatment_plan_id?: string | null;
  line_items?: CreateInvoiceLineItemRequest[];
  tax_amount?: number;
  discount_amount?: number;
  due_date?: string | null;
  currency?: string | null;
}

export interface UpdateInvoiceRequest {
  status?: InvoiceResponse["status"];
  due_date?: string | null;
  tax_amount?: number;
  discount_amount?: number;
}

export interface RecordPaymentRequest {
  amount: number;
  method: PaymentResponse["method"];
  notes?: string | null;
}

export interface FinanceSettingsResponse {
  base_currency: string;
  usd_to_pkr_rate: number | null;
}

export interface UpdateFinanceSettingsRequest {
  base_currency?: string;
  usd_to_pkr_rate?: number;
}

export function createInvoice(authedFetch: AuthedFetch, data: CreateInvoiceRequest) {
  return authedFetch<InvoiceResponse>("/api/v1/invoices", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listInvoicesForPatient(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<InvoiceResponse[]>(`/api/v1/invoices?patient_id=${patientId}`);
}

export function listInvoicesForPractice(authedFetch: AuthedFetch, status?: InvoiceResponse["status"]) {
  return authedFetch<InvoiceResponse[]>(`/api/v1/invoices${status ? `?status=${status}` : ""}`);
}

export function getInvoice(authedFetch: AuthedFetch, id: string) {
  return authedFetch<InvoiceResponse>(`/api/v1/invoices/${id}`);
}

export function updateInvoice(authedFetch: AuthedFetch, id: string, data: UpdateInvoiceRequest) {
  return authedFetch<InvoiceResponse>(`/api/v1/invoices/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function recordInvoicePayment(authedFetch: AuthedFetch, id: string, data: RecordPaymentRequest) {
  return authedFetch<InvoiceResponse>(`/api/v1/invoices/${id}/payments`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listInvoicePayments(authedFetch: AuthedFetch, id: string) {
  return authedFetch<PaymentResponse[]>(`/api/v1/invoices/${id}/payments`);
}

type AuthedFetchBlob = ((path: string, init?: RequestInit) => Promise<Blob>) | null;

export async function fetchInvoicePdfBlob(authedFetchBlob: AuthedFetchBlob, id: string): Promise<Blob> {
  if (!authedFetchBlob) throw new Error("Not signed in");
  return authedFetchBlob(`/api/v1/invoices/${id}/pdf`);
}

export function createInvoiceCheckoutSession(authedFetch: AuthedFetch, id: string) {
  return authedFetch<{ session_id: string; url: string }>(`/api/v1/invoices/${id}/checkout-session`, {
    method: "POST"
  });
}

export function confirmInvoiceCheckoutSession(authedFetch: AuthedFetch, id: string, sessionId: string) {
  return authedFetch<InvoiceResponse>(`/api/v1/invoices/${id}/checkout-session/${sessionId}/confirm`, {
    method: "POST"
  });
}

export function getFinanceSettings(authedFetch: AuthedFetch) {
  return authedFetch<FinanceSettingsResponse>("/api/v1/finance/settings");
}

export function updateFinanceSettings(authedFetch: AuthedFetch, data: UpdateFinanceSettingsRequest) {
  return authedFetch<FinanceSettingsResponse>("/api/v1/finance/settings", {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

// --- wallet / practice credits ---------------------------------------------------
// Matches backend/src/router/wallet/wallet_router.py — Owner-only. Tracking
// only: top up via Stripe, view balance/history; nothing deducts from it yet.
export interface WalletBalanceResponse {
  balance: number;
  currency: string;
}

export interface WalletTransactionResponse {
  id: string;
  amount: number;
  currency: string;
  status: "pending" | "completed" | "failed";
  description: string | null;
  created_at: string;
}

export function getWalletBalance(authedFetch: AuthedFetch) {
  return authedFetch<WalletBalanceResponse>("/api/v1/wallet");
}

export function listWalletTransactions(authedFetch: AuthedFetch) {
  return authedFetch<WalletTransactionResponse[]>("/api/v1/wallet/transactions");
}

export function createWalletCheckoutSession(authedFetch: AuthedFetch, amount: number) {
  return authedFetch<{ session_id: string; url: string }>("/api/v1/wallet/checkout-session", {
    method: "POST",
    body: JSON.stringify({ amount })
  });
}

export function confirmWalletCheckoutSession(authedFetch: AuthedFetch, sessionId: string) {
  return authedFetch<WalletBalanceResponse>(`/api/v1/wallet/checkout-session/${sessionId}/confirm`, {
    method: "POST"
  });
}

// --- finance: expenses + overview -----------------------------------------------
// Matches backend/src/router/finance/finance_router.py. Recording/viewing
// expenses is Owner+Receptionist; the aggregate overview is Owner-only.
export interface ExpenseResponse {
  id: string;
  practice_id: string;
  expense_type: string;
  status: string;
  category: string;
  amount: number;
  vendor: string | null;
  payee_name: string | null;
  expense_date: string;
  notes: string | null;
  paid_at: string | null;
  recorded_by: string;
  created_at: string;
  updated_at: string;
}

export interface CreateExpenseRequest {
  expense_type?: string;
  status?: string;
  category: string;
  amount: number;
  vendor?: string | null;
  payee_name?: string | null;
  expense_date: string;
  notes?: string | null;
}

export interface UpdateExpenseRequest {
  expense_type?: string;
  status?: string;
  category?: string;
  amount?: number;
  vendor?: string | null;
  payee_name?: string | null;
  expense_date?: string;
  notes?: string | null;
  paid_at?: string | null;
}

export interface FinanceOverviewResponse {
  total_revenue: number;
  total_expenses: number;
  net: number;
  invoice_count: number;
  expense_count: number;
}

export function createExpense(authedFetch: AuthedFetch, data: CreateExpenseRequest) {
  return authedFetch<ExpenseResponse>("/api/v1/finance/expenses", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listExpenses(authedFetch: AuthedFetch) {
  return authedFetch<ExpenseResponse[]>("/api/v1/finance/expenses");
}

export function updateExpense(authedFetch: AuthedFetch, id: string, data: UpdateExpenseRequest) {
  return authedFetch<ExpenseResponse>(`/api/v1/finance/expenses/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function deleteExpense(authedFetch: AuthedFetch, id: string) {
  return authedFetch<void>(`/api/v1/finance/expenses/${id}`, {
    method: "DELETE"
  });
}

export function getFinanceOverview(authedFetch: AuthedFetch) {
  return authedFetch<FinanceOverviewResponse>("/api/v1/finance/overview");
}

// --- inventory ------------------------------------------------------------------
// Matches backend/src/router/inventory/inventory_router.py. Owner+Receptionist
// only, same split as Expenses.
export interface InventoryItemResponse {
  id: string;
  practice_id: string;
  name: string;
  sku: string | null;
  category: string | null;
  unit: string | null;
  reorder_threshold: number | null;
  is_active: boolean;
  on_hand_quantity: number;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateInventoryItemRequest {
  name: string;
  sku?: string | null;
  category?: string | null;
  unit?: string | null;
  reorder_threshold?: number | null;
}

export interface UpdateInventoryItemRequest {
  name?: string;
  sku?: string | null;
  category?: string | null;
  unit?: string | null;
  reorder_threshold?: number | null;
  is_active?: boolean;
}

export interface InventoryBatchResponse {
  id: string;
  inventory_item_id: string;
  lot_number: string | null;
  quantity: number;
  expiry_date: string | null;
  received_at: string;
  created_at: string;
  updated_at: string;
}

export interface ReceiveBatchRequest {
  lot_number?: string | null;
  quantity: number;
  expiry_date?: string | null;
  received_at?: string | null;
}

export function createInventoryItem(authedFetch: AuthedFetch, data: CreateInventoryItemRequest) {
  return authedFetch<InventoryItemResponse>("/api/v1/inventory/items", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listInventoryItems(authedFetch: AuthedFetch) {
  return authedFetch<InventoryItemResponse[]>("/api/v1/inventory/items");
}

export function getInventoryItem(authedFetch: AuthedFetch, id: string) {
  return authedFetch<InventoryItemResponse>(`/api/v1/inventory/items/${id}`);
}

export function updateInventoryItem(authedFetch: AuthedFetch, id: string, data: UpdateInventoryItemRequest) {
  return authedFetch<InventoryItemResponse>(`/api/v1/inventory/items/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function receiveInventoryBatch(authedFetch: AuthedFetch, itemId: string, data: ReceiveBatchRequest) {
  return authedFetch<InventoryBatchResponse>(`/api/v1/inventory/items/${itemId}/batches`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function listInventoryBatches(authedFetch: AuthedFetch, itemId: string) {
  return authedFetch<InventoryBatchResponse[]>(`/api/v1/inventory/items/${itemId}/batches`);
}

export function consumeInventoryStock(authedFetch: AuthedFetch, itemId: string, quantity: number) {
  return authedFetch<InventoryItemResponse>(`/api/v1/inventory/items/${itemId}/consume`, {
    method: "POST",
    body: JSON.stringify({ quantity })
  });
}

// --- AI Receptionist -------------------------------------------------------------
// Matches backend/src/router/ai_receptionist/ai_receptionist_router.py — the
// merged voice/chat + reminders + translation module (previously 3 separate
// "agent" folders: receptionist_agent, appointment_reminder_agent,
// multilingual_translation_agent). Owner always sees /overview; Doctor sees
// it too if granted the "view_ai_receptionist" permission.
export interface ReceptionistPipeline {
  qualified_leads: number;
  appointments_scheduled: number;
  auto_followups_sent: number;
}

export interface ReceptionistChannelStatus {
  channel: string;
  connected: boolean;
  detail: string;
}

export interface ReceptionistHealth {
  status: string;
  last_activity_at: string | null;
  sessions_24h: number;
  interactions_24h: number;
}

export interface ReceptionistActivityEntry {
  id: string;
  label: string;
  channel: string | null;
  summary: string | null;
  created_at: string;
}

export interface AIReceptionistOverviewResponse {
  calls_handled: number;
  reminders_sent: number;
  translations_done: number;
  total_interactions: number;
  estimated_cost_total: number;
  estimated_cost_last_30_days: number;
  // Optional so a stale/older backend payload (before the monitor widgets
  // went real) degrades to fallback widgets instead of crashing the page.
  pipeline?: ReceptionistPipeline;
  channels?: ReceptionistChannelStatus[];
  health?: ReceptionistHealth;
  recent_activity?: ReceptionistActivityEntry[];
}

export function getAIReceptionistOverview(authedFetch: AuthedFetch) {
  return authedFetch<AIReceptionistOverviewResponse>("/api/v1/ai-receptionist/overview");
}

export interface SystemPromptResponse {
  system_prompt: string;
  custom_instructions: string;
  updated_at: string | null;
  updated_by: string | null;
}

export function getAIReceptionistSystemPrompt(authedFetch: AuthedFetch) {
  return authedFetch<SystemPromptResponse>("/api/v1/ai-receptionist/system-prompt");
}

export function updateAIReceptionistSystemPrompt(authedFetch: AuthedFetch, customInstructions: string) {
  return authedFetch<SystemPromptResponse>("/api/v1/ai-receptionist/system-prompt", {
    method: "PUT",
    body: JSON.stringify({ custom_instructions: customInstructions })
  });
}

// --- agent config ------------------------------------------------------------
// Backed by backend/src/router/agent_config/ — GET read for any practice user,
// PUT write for the Owner only. `config` JSONB holds per-agent knobs (tone,
// escalation sensitivity) that the Agent settings page edits.
export interface AgentConfigResponse {
  id: string;
  practice_id: string;
  agent_type: string;
  enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentConfigUpdate {
  enabled?: boolean;
  config?: Record<string, unknown>;
}

export function listAgentConfigs(authedFetch: AuthedFetch) {
  return authedFetch<AgentConfigResponse[]>("/api/v1/agent-config");
}

export function updateAgentConfig(authedFetch: AuthedFetch, agentType: string, update: AgentConfigUpdate) {
  return authedFetch<AgentConfigResponse>(`/api/v1/agent-config/${agentType}`, {
    method: "PUT",
    body: JSON.stringify(update)
  });
}

export function translateText(authedFetch: AuthedFetch, text: string, targetLanguage: string) {
  return authedFetch<{ translated_text: string }>("/api/v1/ai-receptionist/translate", {
    method: "POST",
    body: JSON.stringify({ text, target_language: targetLanguage })
  });
}

export function sendAppointmentReminder(authedFetch: AuthedFetch, appointmentId: string) {
  return authedFetch<{ appointment_id: string; message_id: string; sent: boolean }>(
    `/api/v1/ai-receptionist/appointments/${appointmentId}/reminder`,
    { method: "POST" }
  );
}

// --- staff messages ---------------------------------------------------------------
// Matches backend/src/router/staff_messages/staff_message_router.py — a 1:1
// team chat between any two practice users. Conversations are stored as
// canonical user pairs, so every member (owner, doctor, receptionist) uses
// the same endpoints with no role-specific aliases. `mine` is computed
// server-side per viewer.
export interface StaffMessageResponse {
  id: string;
  conversation_id: string;
  sender_id: string;
  sender_name: string | null;
  sender_role: string;
  body: string;
  created_at: string;
  mine: boolean;
}

export interface StaffContactResponse {
  id: string;
  name: string | null;
  role: string;
  email: string;
}

export interface StaffConversationSummary {
  conversation_id: string;
  recipient_id: string;
  recipient_name: string | null;
  recipient_email: string;
  recipient_role: string;
  last_message_preview: string | null;
  last_message_at: string | null;
  message_count: number;
}

export interface StartStaffConversationPayload {
  recipient_user_id: string;
  body?: string;
}

export function listStaffContacts(authedFetch: AuthedFetch) {
  return authedFetch<StaffContactResponse[]>("/api/v1/staff-messages/contacts");
}

export function listStaffConversations(authedFetch: AuthedFetch) {
  return authedFetch<StaffConversationSummary[]>("/api/v1/staff-messages/conversations");
}

export function startStaffConversation(authedFetch: AuthedFetch, payload: StartStaffConversationPayload) {
  return authedFetch<StaffConversationSummary>("/api/v1/staff-messages/conversations", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listStaffMessages(authedFetch: AuthedFetch, conversationId: string) {
  return authedFetch<StaffMessageResponse[]>(`/api/v1/staff-messages/conversations/${conversationId}`);
}

export function sendStaffMessage(authedFetch: AuthedFetch, conversationId: string, body: string) {
  return authedFetch<StaffMessageResponse>(`/api/v1/staff-messages/conversations/${conversationId}`, {
    method: "POST",
    body: JSON.stringify({ body })
  });
}

export async function sendStaffFile(_authedFetch: AuthedFetch, conversationId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`/api/v1/staff-messages/conversations/${conversationId}/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${localStorage.getItem("clerk_session_token") || ""}` },
    body: formData
  });
  if (!response.ok) throw new Error("Upload failed");
  return response.json() as Promise<StaffMessageResponse>;
}

// --- patient portal ----------------------------------------------------------
// Real ID+PIN login (backend/src/router/patient_portal/patient_portal_router.py) —
// replaces the earlier plaintext-link-token scheme entirely. Owner/staff manage
// access (enable/reset-PIN/disable) via authedFetch (Clerk); the patient's own
// session is a separate, short-lived JWT from POST /login, sent as a Bearer
// token by portalFetch below — never Clerk, never the practice's authedFetch.
export interface PortalAccessResponse {
  portal_id: string | null;
  enabled: boolean;
  pin: string | null;
  pin_expires_at: string | null;
  pin_set: boolean;
}

export interface PortalEnabledResponse {
  portal_id: string;
  invite_sent: boolean;
  pin: string | null;
  pin_expires_at: string | null;
}

export interface PortalAppointment {
  id: string;
  appointment_type: string;
  status: string;
  start_time: string;
  end_time: string;
  notes: string | null;
}

export interface PortalConsentDocument {
  id: string;
  document_type: string;
  status: string;
  signed_at: string | null;
  signed_by_name: string | null;
}

export interface PortalInvoice {
  id: string;
  description: string;
  total_amount: number;
  status: string;
  due_date: string | null;
  created_at: string;
}

export interface PortalPhoto {
  id: string;
  photo_type: string | null;
  notes: string | null;
  url: string;
  taken_at: string;
}

export interface PortalDoctorInfo {
  id: string;
  name: string;
  specialty: string | null;
  bio: string | null;
  photo_url: string | null;
}

export interface PortalTreatmentPlanItem {
  id: string;
  procedure_name: string;
  status: string;
  estimated_price: number | null;
  actual_price: number | null;
}

export interface PortalTreatmentPlan {
  id: string;
  title: string;
  status: string;
  items: PortalTreatmentPlanItem[];
  created_at: string;
}

export interface PortalPatientResponse {
  id: string;
  portal_id: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  additional_phones: Array<{ number?: string; label?: string }>;
  chief_complaint: string | null;
  consent_status: boolean;
  doctor: PortalDoctorInfo | null;
  appointments: PortalAppointment[];
  consent_documents: PortalConsentDocument[];
  invoices: PortalInvoice[];
  photos: PortalPhoto[];
  treatment_plans: PortalTreatmentPlan[];
  invoice_total_pending: number;
  intake_completed: boolean;
  intake_summary: string | null;
  // True once the patient set their own login PIN (staff never sees the PIN).
  pin_set: boolean;
}

export interface PortalBookingRequest {
  appointment_type: string;
  start_time: string;
  end_time: string;
  notes?: string | null;
}

export interface PatientIntakeRequest {
  allergies: Array<{ name?: string; severity?: string; reaction?: string }>;
  surgical_history: Array<{ procedure?: string; year?: number; facility?: string; notes?: string }>;
  current_medications: Array<{ name?: string; dosage?: string; frequency?: string }>;
  smoking_status?: string | null;
  previous_cosmetic_procedures: Array<{ procedure?: string; year?: number; provider?: string }>;
  additional_notes?: string | null;
}

// --- Owner/staff-side management (authedFetch, Clerk) ---

export function enablePatientPortal(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PortalEnabledResponse>(`/api/v1/patient-portal/patients/${patientId}/enable`, {
    method: "POST"
  });
}

export function resendPatientPortalInvite(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PortalAccessResponse>(`/api/v1/patient-portal/patients/${patientId}/resend-invite`, {
    method: "POST"
  });
}

export function generatePatientPortalPin(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PortalAccessResponse>(`/api/v1/patient-portal/patients/${patientId}/pin`, {
    method: "POST"
  });
}

export function disablePatientPortal(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PortalAccessResponse>(`/api/v1/patient-portal/patients/${patientId}/disable`, {
    method: "POST"
  });
}

export function getPatientPortalAccess(authedFetch: AuthedFetch, patientId: string) {
  return authedFetch<PortalAccessResponse>(`/api/v1/patient-portal/patients/${patientId}/access`);
}

// --- Patient-side (own JWT, not Clerk) ---

// Thin fetch wrapper mirroring client.ts's apiFetch, but Bearer-authed with
// the patient's own portal session token instead of a Clerk session.
async function portalFetch<T>(path: string, portalToken: string | null, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(portalToken ? { Authorization: `Bearer ${portalToken}` } : {}),
      ...init?.headers
    }
  });
  if (!res.ok) {
    let detail: string | null = null;
    try {
      const body = await res.clone().json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON or empty error body — fall through to the generic message.
    }
    throw new ApiError(res.status, detail || `${init?.method || "GET"} ${path} failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export interface PortalLoginResponse {
  access_token: string;
  expires_in_minutes: number;
  // True when this patient hasn't set a login PIN yet — the portal shows the
  // "set your PIN" screen right after logging in via a one-time code.
  requires_pin_setup?: boolean;
}

export interface RequestOtpResponse {
  found: boolean;
  delivered_via: "whatsapp" | "email" | null;
}

export function portalRequestOtp(phone: string) {
  return portalFetch<RequestOtpResponse>("/api/v1/patient-portal/request-otp", null, {
    method: "POST",
    body: JSON.stringify({ phone })
  });
}

export function portalVerifyOtp(phone: string, code: string) {
  return portalFetch<PortalLoginResponse>("/api/v1/patient-portal/verify-otp", null, {
    method: "POST",
    body: JSON.stringify({ phone, code })
  });
}

// The cheap, OTP-free daily login — phone + the patient's own PIN (no code is
// sent, so repeated logins don't cost anything; a forgotten PIN uses the OTP
// flow above to set a new one).
export function portalLoginWithPin(phone: string, pin: string) {
  return portalFetch<PortalLoginResponse>("/api/v1/patient-portal/patient-login", null, {
    method: "POST",
    body: JSON.stringify({ phone, pin })
  });
}

// First-time PIN setup (after a one-time-code login with requires_pin_setup)
// or a PIN change — `currentPin` is required when changing an existing PIN.
export function portalSetPin(portalToken: string, pin: string, currentPin?: string) {
  return portalFetch<PortalPatientResponse>("/api/v1/patient-portal/me/pin", portalToken, {
    method: "POST",
    body: JSON.stringify({ pin, current_pin: currentPin || null })
  });
}

export function getMyPortalData(portalToken: string) {
  return portalFetch<PortalPatientResponse>("/api/v1/patient-portal/me", portalToken);
}

export function portalBookAppointment(portalToken: string, data: PortalBookingRequest) {
  return portalFetch<PortalPatientResponse>("/api/v1/patient-portal/me/appointments", portalToken, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function portalSubmitIntake(portalToken: string, data: PatientIntakeRequest) {
  return portalFetch<PortalPatientResponse>("/api/v1/patient-portal/me/intake", portalToken, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export interface PortalMessage {
  id: string;
  role: "patient" | "agent" | "staff" | "system";
  content: string;
  created_at: string;
}

export function getMyPortalMessages(portalToken: string) {
  return portalFetch<PortalMessage[]>("/api/v1/patient-portal/me/messages", portalToken);
}

export function sendMyPortalMessage(portalToken: string, content: string) {
  return portalFetch<PortalMessage>("/api/v1/patient-portal/me/messages", portalToken, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export interface UpdateMyProfileRequest {
  first_name?: string;
  last_name?: string;
  email?: string | null;
  additional_phones?: Array<{ number?: string; label?: string }>;
}

export function updateMyPortalProfile(portalToken: string, data: UpdateMyProfileRequest) {
  return portalFetch<PortalPatientResponse>("/api/v1/patient-portal/me/profile", portalToken, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export interface ConsultationRequestPayload {
  full_name: string;
  email?: string | null;
  phone?: string | null;
  chief_complaint: string;
  needs_surgery?: boolean;
}

export interface ConsultationRequestResponse {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  chief_complaint: string | null;
  needs_surgery: boolean;
  ai_agent_assigned: string | null;
  source: string | null;
  lifecycle_stage: string;
  created_at: string;
  updated_at: string;
}

// Public website "Book a consultation" lead — no authedFetch, same reason as
// portalBookAppointment: the form is the funnel entry, no auth required.
export async function submitConsultationRequest(data: ConsultationRequestPayload): Promise<ConsultationRequestResponse> {
  const res = await fetch(`/api/v1/public/consultation-request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't send your request. Please try again.");
  }
  return res.json();
}

// Public website AI chat (Aria) — no authedFetch, same reason as
// submitConsultationRequest: the hero/chat IS the public funnel entry. The
// client passes conversation_id back to continue the same thread.
export interface LandingChatMessagePayload {
  conversation_id?: string | null;
  message: string;
  context?: string | null;
}

export interface LandingChatMessageResponse {
  conversation_id: string;
  reply: string;
  /** "sales" (clinic buyer evaluating Aiaceone) or "patient" (booked a consult). */
  flow?: "sales" | "patient" | null;
  booking_created: boolean;
  lead_name?: string | null;
  sales_lead_created?: boolean;
  sales_lead_name?: string | null;
}

export async function sendLandingChatMessage(data: LandingChatMessagePayload): Promise<LandingChatMessageResponse> {
  const res = await fetch(`/api/v1/landing-chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body?.detail === "string" ? body.detail : "Couldn't reach the assistant. Please try again.");
  }
  return res.json();
}
