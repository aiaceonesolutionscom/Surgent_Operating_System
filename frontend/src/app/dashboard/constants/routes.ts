// Single source of truth for every /dashboard/* path — the sidebar, the
// central DashboardRouter, and any internal links all read from here so a
// path never has to be hand-typed (and drift) in more than one place.
export const DASHBOARD_ROUTES = {
  root: "/dashboard",
  overview: "/dashboard",
  sessionsAll: "/dashboard/sessions",
  sessionsNeedsAttention: "/dashboard/sessions/needs-attention",
  patients: "/dashboard/patients",
  patientNew: "/dashboard/patients/new",
  patientDetail: (id: string) => `/dashboard/patients/${id}`,
  doctors: "/dashboard/doctors",
  doctorNew: "/dashboard/doctors/new",
  doctorDetail: (id: string) => `/dashboard/doctors/${id}`,
  doctorEdit: (id: string) => `/dashboard/doctors/${id}/edit`,
  doctorOverview: "/dashboard/doctor",
  myCalendar: "/dashboard/my-calendar",
  myBook: "/dashboard/my-book",
  doctorRequests: "/dashboard/doctor-requests",
  doctorRequestDetail: (id: string) => `/dashboard/doctor-requests/${id}`,
  agentCategory: (categoryId: string) => `/dashboard/agents/${categoryId}`,
  agentDetail: (categoryId: string, slug: string) => `/dashboard/agents/${categoryId}/${slug}`,
  receptionistMonitor: "/dashboard/ai-receptionist",
  analytics: "/dashboard/analytics",
  commandCenter: "/dashboard/command-center",
  // Receptionist's real staff workspace — distinct from receptionistMonitor
  // above, which is the Owner-only AI-monitoring page.
  // Waiting Room used to be its own route/sidebar item — it's a tab inside
  // Front Desk now (see ReceptionistFrontDesk.tsx), not a separate page.
  frontDesk: "/dashboard/front-desk",
  bookAppointment: "/dashboard/book-appointment",
  staff: "/dashboard/staff",
  teamAttendance: "/dashboard/attendance",
  consultationNoteNew: (patientId: string) => `/dashboard/patients/${patientId}/notes/new`,
  treatmentPlanNew: (patientId: string) => `/dashboard/patients/${patientId}/treatment-plans/new`,
  treatmentPlanDetail: (id: string) => `/dashboard/treatment-plans/${id}`,
  invoices: "/dashboard/invoices",
  invoiceNew: (patientId?: string) => (patientId ? `/dashboard/invoices/new?patient_id=${patientId}` : "/dashboard/invoices/new"),
  invoiceDetail: (id: string) => `/dashboard/invoices/${id}`,
  messages: "/dashboard/messages",
  messageThread: (conversationId: string) => `/dashboard/messages?thread=${conversationId}`,
  expenses: "/dashboard/finance/expenses",
  financeOverview: "/dashboard/finance/overview",
  leadsFunnel: "/dashboard/leads",
  inventory: "/dashboard/inventory",
  inventoryItemDetail: (id: string) => `/dashboard/inventory/${id}`,
  surgeries: "/dashboard/surgeries",
  surgeryNew: (patientId?: string, procedureId?: string) => {
    const params = new URLSearchParams();
    if (patientId) params.set("patient_id", patientId);
    if (procedureId) params.set("procedure_id", procedureId);
    const qs = params.toString();
    return qs ? `/dashboard/surgeries/new?${qs}` : "/dashboard/surgeries/new";
  },
  surgeryDetail: (id: string) => `/dashboard/surgeries/${id}`,
  settingsAgents: "/dashboard/settings/agents",
  settingsIntegrations: "/dashboard/settings/integrations",
  settingsProcedures: "/dashboard/settings/procedures",
  settingsProfile: "/dashboard/settings/profile",
  settingsBilling: "/dashboard/settings/billing",
  settingsConsentTemplates: "/dashboard/settings/consent-templates"
} as const;
