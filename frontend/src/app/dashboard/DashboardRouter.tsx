import React, { Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { RequireAuth } from "../auth/RequireAuth";
import { RequirePractice } from "../auth/RequirePractice";
import { DashboardLayout } from "./layout/DashboardLayout";
import { DASHBOARD_ROUTES } from "./constants/routes";
import { usePlan } from "./plan/PlanContext";

// ── Lazy-loaded dashboard pages ──────────────────────────────────────────
// Each page is its own chunk — only downloaded when the user navigates to it.
const OverviewPage = React.lazy(() => import("./overview/OverviewPage").then(m => ({ default: m.OverviewPage })));
const SessionsPage = React.lazy(() => import("./sessions/SessionsPage").then(m => ({ default: m.SessionsPage })));
const NeedsAttentionPage = React.lazy(() => import("./sessions/NeedsAttentionPage").then(m => ({ default: m.NeedsAttentionPage })));
const PatientsPage = React.lazy(() => import("./patients/PatientsPage").then(m => ({ default: m.PatientsPage })));
const PatientDetailPage = React.lazy(() => import("./patients/PatientDetailPage").then(m => ({ default: m.PatientDetailPage })));
const PatientFormPage = React.lazy(() => import("./patients/PatientFormPage").then(m => ({ default: m.PatientFormPage })));
const DoctorsPage = React.lazy(() => import("./doctors/DoctorsPage").then(m => ({ default: m.DoctorsPage })));
const DoctorDetailPage = React.lazy(() => import("./doctors/DoctorDetailPage").then(m => ({ default: m.DoctorDetailPage })));
const DoctorFormPage = React.lazy(() => import("./doctors/DoctorFormPage").then(m => ({ default: m.DoctorFormPage })));
const DoctorOverviewPage = React.lazy(() => import("./doctor-overview/DoctorOverviewPage").then(m => ({ default: m.DoctorOverviewPage })));
const MyCalendarPage = React.lazy(() => import("./doctor-overview/MyCalendarPage").then(m => ({ default: m.MyCalendarPage })));
const MyBookAppointmentPage = React.lazy(() => import("./doctor-overview/MyBookAppointmentPage").then(m => ({ default: m.MyBookAppointmentPage })));
const DoctorRequestsPage = React.lazy(() => import("./doctor-requests/DoctorRequestsPage").then(m => ({ default: m.DoctorRequestsPage })));
const DoctorRequestDetailPage = React.lazy(() => import("./doctor-requests/DoctorRequestDetailPage").then(m => ({ default: m.DoctorRequestDetailPage })));
const AgentCategoryPage = React.lazy(() => import("./agents/AgentCategoryPage").then(m => ({ default: m.AgentCategoryPage })));
const AgentDetailDashboardPage = React.lazy(() => import("./agents/AgentDetailPage").then(m => ({ default: m.AgentDetailPage })));
const CommandCenterPage = React.lazy(() => import("./command-center/CommandCenterPage").then(m => ({ default: m.CommandCenterPage })));
const ReceptionistMonitorPage = React.lazy(() => import("./receptionist/ReceptionistMonitorPage").then(m => ({ default: m.ReceptionistMonitorPage })));
const AnalyticsPage = React.lazy(() => import("./analytics/AnalyticsPage").then(m => ({ default: m.AnalyticsPage })));
const AgentSettingsPage = React.lazy(() => import("./settings/AgentSettingsPage").then(m => ({ default: m.AgentSettingsPage })));
const IntegrationsPage = React.lazy(() => import("./settings/IntegrationsPage").then(m => ({ default: m.IntegrationsPage })));
const MetaCallbackPage = React.lazy(() => import("./settings/MetaCallbackPage").then(m => ({ default: m.MetaCallbackPage })));
const ProfilePage = React.lazy(() => import("./profile/ProfilePage").then(m => ({ default: m.ProfilePage })));
const PlanBillingPage = React.lazy(() => import("./billing/PlanBillingPage").then(m => ({ default: m.PlanBillingPage })));
const PlanGate = React.lazy(() => import("./plan/PlanGate").then(m => ({ default: m.PlanGate })));
const FrontDeskPage = React.lazy(() => import("./front-desk/FrontDeskPage").then(m => ({ default: m.FrontDeskPage })));
const BookAppointmentPage = React.lazy(() => import("./front-desk/BookAppointmentPage").then(m => ({ default: m.BookAppointmentPage })));
const StaffPage = React.lazy(() => import("./staff/StaffPage").then(m => ({ default: m.StaffPage })));
const ProceduresPage = React.lazy(() => import("./clinical/ProceduresPage").then(m => ({ default: m.ProceduresPage })));
const ConsultationNoteFormPage = React.lazy(() => import("./clinical/ConsultationNoteFormPage").then(m => ({ default: m.ConsultationNoteFormPage })));
const TreatmentPlanFormPage = React.lazy(() => import("./clinical/TreatmentPlanFormPage").then(m => ({ default: m.TreatmentPlanFormPage })));
const TreatmentPlanPage = React.lazy(() => import("./clinical/TreatmentPlanPage").then(m => ({ default: m.TreatmentPlanPage })));
const InvoicesPage = React.lazy(() => import("./billing-invoices/InvoicesPage").then(m => ({ default: m.InvoicesPage })));
const InvoiceFormPage = React.lazy(() => import("./billing-invoices/InvoiceFormPage").then(m => ({ default: m.InvoiceFormPage })));
const InvoiceDetailPage = React.lazy(() => import("./billing-invoices/InvoiceDetailPage").then(m => ({ default: m.InvoiceDetailPage })));
const ExpensesPage = React.lazy(() => import("./finance/ExpensesPage").then(m => ({ default: m.ExpensesPage })));
const FinanceOverviewPage = React.lazy(() => import("./finance/FinanceOverviewPage").then(m => ({ default: m.FinanceOverviewPage })));
const FunnelPage = React.lazy(() => import("./leads/FunnelPage").then(m => ({ default: m.FunnelPage })));
const InventoryPage = React.lazy(() => import("./inventory/InventoryPage").then(m => ({ default: m.InventoryPage })));
const InventoryItemDetailPage = React.lazy(() => import("./inventory/InventoryItemDetailPage").then(m => ({ default: m.InventoryItemDetailPage })));
const MessagesPage = React.lazy(() => import("./messages/MessagesPage").then(m => ({ default: m.MessagesPage })));
const SurgeryListPage = React.lazy(() => import("./surgery/SurgeryListPage").then(m => ({ default: m.SurgeryListPage })));
const SurgeryFormPage = React.lazy(() => import("./surgery/SurgeryFormPage").then(m => ({ default: m.SurgeryFormPage })));
const SurgeryDetailPage = React.lazy(() => import("./surgery/SurgeryDetailPage").then(m => ({ default: m.SurgeryDetailPage })));
const ConsentTemplatesPage = React.lazy(() => import("./settings/ConsentTemplatesPage").then(m => ({ default: m.ConsentTemplatesPage })));
const TeamAttendancePage = React.lazy(() => import("./attendance/TeamAttendancePage").then(m => ({ default: m.TeamAttendancePage })));

// Doctor's real landing page is /dashboard/doctor, not root — root's
// OverviewPage is Owner-flavored practice-wide data (greeting, KPIs,
// AIInsightsPanel) that isn't appropriate for a Doctor login. A doctor
// landing on root gets sent to their own overview instead of seeing it.
// Same reasoning for Receptionist → Front Desk. roleLanding() is the single
// source for "where does THIS role go when their path doesn't exist or they
// don't belong somewhere" — never bounces anyone onto a foreign dashboard.
function roleLanding() {
  const { role } = usePlan();
  if (role === "doctor") return DASHBOARD_ROUTES.doctorOverview;
  if (role === "receptionist") return DASHBOARD_ROUTES.frontDesk;
  return DASHBOARD_ROUTES.overview;
}

function RoleLanding() {
  return <Navigate to={roleLanding()} replace />;
}

function DashboardIndex() {
  const { role } = usePlan();
  if (role === "doctor") return <Navigate to={DASHBOARD_ROUTES.doctorOverview} replace />;
  if (role === "receptionist") return <Navigate to={DASHBOARD_ROUTES.frontDesk} replace />;
  return <OverviewPage />;
}

// Guards the doctor-only routes — a non-doctor landing here (direct URL,
// stale link, preview mismatch) is sent to their OWN role landing, so a
// receptionist never gets dumped onto the Owner overview by mistake.
function RequireDoctor({ children }: { children: React.ReactNode }) {
  const { role } = usePlan();
  if (role !== "doctor") return <Navigate to={roleLanding()} replace />;
  return <>{children}</>;
}

// Guards the Front Desk/Waiting Room/Book Appointment routes — mirrors
// RequireDoctor. Owner can also reach these (full practice visibility), a
// Doctor cannot.
function RequireReceptionist({ children }: { children: React.ReactNode }) {
  const { role } = usePlan();
  if (role !== "receptionist" && role !== "owner") return <Navigate to={roleLanding()} replace />;
  return <>{children}</>;
}

// Guards the Owner-only review pages — anyone else goes to their own landing.
function RequireOwner({ children }: { children: React.ReactNode }) {
  const { role } = usePlan();
  if (role !== "owner") return <Navigate to={roleLanding()} replace />;
  return <>{children}</>;
}

// Guard for the Procedures page — Owner manages (add/edit) and a Doctor is
// expected to at least see the practice's procedure catalog and prices. Both
// roles reach it; anyone else (receptionist/staff) is sent to their own landing.
function RequireOwnerOrDoctor({ children }: { children: React.ReactNode }) {
  const { role } = usePlan();
  if (role !== "owner" && role !== "doctor") return <Navigate to={roleLanding()} replace />;
  return <>{children}</>;
}

// Read-only surgery visibility for Receptionist (front-desk context); every
// surgery mutation stays Owner/Doctor backend-side.
function RequireOwnerOrDoctorOrReceptionist({ children }: { children: React.ReactNode }) {
  const { role } = usePlan();
  if (role !== "owner" && role !== "doctor" && role !== "receptionist") return <Navigate to={roleLanding()} replace />;
  return <>{children}</>;
}

// Single registrar for every /dashboard/* screen — mirrors
// backend/src/router/agents/__init__.py's role for the agent routers. Every
// path in constants/routes.ts has exactly one matching <Route> here; nothing
// under app/dashboard/ is reachable except through this file.
// Lightweight loading fallback for dashboard pages
function DashboardLoading() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
      <div style={{ width: 28, height: 28, border: "3px solid #e5e7eb", borderTopColor: "#6366f1", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
    </div>
  );
}

export function DashboardRouter() {
  return (
    <Suspense fallback={<DashboardLoading />}>
      <Routes>
        <Route element={<RequireAuth><RequirePractice><DashboardLayout /></RequirePractice></RequireAuth>}>
          <Route index element={<DashboardIndex />} />
          {/* Unknown /dashboard/* path — route the user to their OWN area
              instead of an unhandled blank/invalid screen. */}
          <Route path="*" element={<RoleLanding />} />
          <Route path="doctor" element={<RequireDoctor><DoctorOverviewPage /></RequireDoctor>} />
          <Route path="my-calendar" element={<RequireDoctor><MyCalendarPage /></RequireDoctor>} />
          <Route path="my-book" element={<RequireDoctor><MyBookAppointmentPage /></RequireDoctor>} />
          <Route path="sessions" element={<SessionsPage />} />
          <Route path="sessions/needs-attention" element={<NeedsAttentionPage />} />
          <Route path="patients" element={<PatientsPage />} />
          <Route path="patients/new" element={<PatientFormPage />} />
          <Route path="patients/:id" element={<PatientDetailPage />} />
          <Route path="doctors" element={<DoctorsPage />} />
          <Route path="doctors/new" element={<DoctorFormPage />} />
          <Route path="doctors/:id" element={<DoctorDetailPage />} />
          <Route path="doctors/:id/edit" element={<DoctorFormPage />} />
          <Route path="doctor-requests" element={<RequireOwner><DoctorRequestsPage /></RequireOwner>} />
          <Route path="doctor-requests/:id" element={<RequireOwner><DoctorRequestDetailPage /></RequireOwner>} />
          <Route path="staff" element={<RequireOwner><StaffPage /></RequireOwner>} />
          <Route path="attendance" element={<RequireOwner><TeamAttendancePage /></RequireOwner>} />
          <Route path="front-desk" element={<RequireReceptionist><FrontDeskPage /></RequireReceptionist>} />
          <Route path="book-appointment" element={<RequireReceptionist><BookAppointmentPage /></RequireReceptionist>} />
          <Route path="settings/procedures" element={<RequireOwnerOrDoctor><ProceduresPage /></RequireOwnerOrDoctor>} />
          <Route path="patients/:patientId/notes/new" element={<RequireDoctor><ConsultationNoteFormPage /></RequireDoctor>} />
          <Route path="patients/:patientId/treatment-plans/new" element={<RequireDoctor><TreatmentPlanFormPage /></RequireDoctor>} />
          <Route path="treatment-plans/:id" element={<TreatmentPlanPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="invoices/new" element={<RequireReceptionist><InvoiceFormPage /></RequireReceptionist>} />
          <Route path="invoices/:id" element={<InvoiceDetailPage />} />
          <Route path="finance/expenses" element={<RequireReceptionist><ExpensesPage /></RequireReceptionist>} />
          <Route path="finance/overview" element={<RequireReceptionist><FinanceOverviewPage /></RequireReceptionist>} />
          <Route path="leads" element={<FunnelPage />} />
          <Route path="inventory" element={<RequireReceptionist><InventoryPage /></RequireReceptionist>} />
          <Route path="inventory/:id" element={<RequireReceptionist><InventoryItemDetailPage /></RequireReceptionist>} />
          <Route path="surgeries" element={<RequireOwnerOrDoctorOrReceptionist><SurgeryListPage /></RequireOwnerOrDoctorOrReceptionist>} />
          <Route path="surgeries/new" element={<RequireOwnerOrDoctor><SurgeryFormPage /></RequireOwnerOrDoctor>} />
          <Route path="surgeries/:id" element={<RequireOwnerOrDoctorOrReceptionist><SurgeryDetailPage /></RequireOwnerOrDoctorOrReceptionist>} />
          <Route path="messages" element={<MessagesPage />} />
          <Route path="agents/:categoryId" element={<AgentCategoryPage />} />
          <Route path="agents/:categoryId/:agentSlug" element={<AgentDetailDashboardPage />} />
          <Route path="command-center" element={<RequireOwner><CommandCenterPage /></RequireOwner>} />
          <Route path="ai-receptionist" element={<RequireReceptionist><ReceptionistMonitorPage /></RequireReceptionist>} />
          <Route
            path="analytics"
            element={
            <PlanGate feature="analytics" title="Analytics" tagline="Real charts on session volume, escalation rate, and channel mix.">
                <AnalyticsPage />
              </PlanGate>
            } />

          <Route path="settings/agents" element={<AgentSettingsPage />} />
          <Route path="settings/integrations" element={<RequireOwner><IntegrationsPage /></RequireOwner>} />
          <Route path="settings/integrations/meta-callback" element={<RequireOwner><MetaCallbackPage /></RequireOwner>} />
          <Route path="settings/profile" element={<ProfilePage />} />
          <Route path="settings/billing" element={<PlanBillingPage />} />
          <Route path="settings/consent-templates" element={<RequireOwner><ConsentTemplatesPage /></RequireOwner>} />
        </Route>
      </Routes>
    </Suspense>
  );

}
