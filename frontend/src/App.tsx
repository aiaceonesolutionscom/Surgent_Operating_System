import React, { Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ScrollToTop } from "./components/layout";

// ── Lazy-loaded page components ──────────────────────────────────────────
// Each import creates a separate chunk that is only fetched when the route
// is actually visited — dramatically reducing the initial JS payload.
const AgentsPage = React.lazy(() => import("./pages/AgentsPage").then(m => ({ default: m.AgentsPage })));
const AgentDetailPage = React.lazy(() => import("./pages/AgentDetailPage").then(m => ({ default: m.AgentDetailPage })));
const ChannelsPage = React.lazy(() => import("./pages/ChannelsPage").then(m => ({ default: m.ChannelsPage })));
const DemoPage = React.lazy(() => import("./pages/DemoPage").then(m => ({ default: m.DemoPage })));
const DashboardRouter = React.lazy(() => import("./app/dashboard/DashboardRouter").then(m => ({ default: m.DashboardRouter })));
const AdminRouter = React.lazy(() => import("./app/admin/AdminRouter").then(m => ({ default: m.AdminRouter })));
const PortalPage = React.lazy(() => import("./app/portal/PortalPage").then(m => ({ default: m.PortalPage })));
const PortalSwitchPage = React.lazy(() => import("./app/portal/PortalSwitchPage").then(m => ({ default: m.PortalSwitchPage })));
const NotFoundPage = React.lazy(() => import("./components/layout/NotFoundPage").then(m => ({ default: m.NotFoundPage })));
const PlanProvider = React.lazy(() => import("./app/dashboard/plan/PlanContext").then(m => ({ default: m.PlanProvider })));
const DoctorApplyRecovery = React.lazy(() => import("./app/auth/DoctorApplyRecovery").then(m => ({ default: m.DoctorApplyRecovery })));

// Auth pages — small, but still lazy so the landing page never pays for them
const SignInPage = React.lazy(() => import("./app/auth/SignInPage").then(m => ({ default: m.SignInPage })));
const SignUpPage = React.lazy(() => import("./app/auth/SignUpPage").then(m => ({ default: m.SignUpPage })));
const DoctorSignUpPage = React.lazy(() => import("./app/auth/DoctorSignUpPage").then(m => ({ default: m.DoctorSignUpPage })));
const StaffSignUpPage = React.lazy(() => import("./app/auth/StaffSignUpPage").then(m => ({ default: m.StaffSignUpPage })));
const DoctorApplyPage = React.lazy(() => import("./app/auth/DoctorApplyPage").then(m => ({ default: m.DoctorApplyPage })));
const DoctorApplyCompletePage = React.lazy(() => import("./app/auth/DoctorApplyCompletePage").then(m => ({ default: m.DoctorApplyCompletePage })));
const DoctorApplyPendingPage = React.lazy(() => import("./app/auth/DoctorApplyPendingPage").then(m => ({ default: m.DoctorApplyPendingPage })));
const StaffApplyPage = React.lazy(() => import("./app/auth/StaffApplyPage").then(m => ({ default: m.StaffApplyPage })));
const StaffApplyCompletePage = React.lazy(() => import("./app/auth/StaffApplyCompletePage").then(m => ({ default: m.StaffApplyCompletePage })));
const StaffApplyPendingPage = React.lazy(() => import("./app/auth/StaffApplyPendingPage").then(m => ({ default: m.StaffApplyPendingPage })));
const OrgApplyPage = React.lazy(() => import("./app/auth/OrgApplyPage").then(m => ({ default: m.OrgApplyPage })));
const RoleHome = React.lazy(() => import("./app/auth/RoleHome").then(m => ({ default: m.RoleHome })));

// Onboarding / checkout pages
const DemoPaymentPage = React.lazy(() => import("./app/onboarding/DemoPaymentPage").then(m => ({ default: m.DemoPaymentPage })));
const CheckoutSuccessPage = React.lazy(() => import("./app/onboarding/CheckoutSuccessPage").then(m => ({ default: m.CheckoutSuccessPage })));
const CheckoutCancelPage = React.lazy(() => import("./app/onboarding/CheckoutCancelPage").then(m => ({ default: m.CheckoutCancelPage })));
const ClaimPlanPage = React.lazy(() => import("./app/onboarding/ClaimPlanPage").then(m => ({ default: m.ClaimPlanPage })));
const SetupWizardPage = React.lazy(() => import("./app/onboarding/SetupWizardPage").then(m => ({ default: m.SetupWizardPage })));

// Lightweight loading fallback — just a centered spinner, no heavy JS
function LoadingFallback() {
  return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <div style={{ width: 32, height: 32, border: "3px solid #e5e7eb", borderTopColor: "#6366f1", borderRadius: "50%", animation: "spin 0.6s linear infinite" }} />
    </div>
  );
}

export function App() {
  return (
    <>
      <ScrollToTop />
      <Suspense fallback={<LoadingFallback />}>
        <DoctorApplyRecovery />
        <Routes>
          <Route path="/" element={<RoleHome />} />
          <Route path="/agents" element={<AgentsPage />} />
          <Route path="/agents/:slug" element={<AgentDetailPage />} />
          <Route path="/channels" element={<ChannelsPage />} />
          <Route path="/demo" element={<DemoPage />} />
          <Route path="/sign-in/*" element={<SignInPage />} />
          <Route path="/sign-up/*" element={<SignUpPage />} />
          <Route path="/doctor/sign-up/*" element={<DoctorSignUpPage />} />
          <Route path="/staff/sign-up/*" element={<StaffSignUpPage />} />
          {/* Role-area entry points — land each role straight in their own
              dashboard territory. The /dashboard/* target is itself guarded
              (RequireDoctor/RequireReceptionist bounce mismatches away). */}
          <Route path="/doctor" element={<Navigate to="/dashboard/doctor" replace />} />
          <Route path="/receptionist" element={<Navigate to="/dashboard/front-desk" replace />} />
          <Route path="/doctor/apply/complete" element={<DoctorApplyCompletePage />} />
          <Route path="/doctor/apply/pending" element={<DoctorApplyPendingPage />} />
          <Route path="/doctor/apply/*" element={<DoctorApplyPage />} />
          <Route path="/staff/apply/complete" element={<StaffApplyCompletePage />} />
          <Route path="/staff/apply/pending" element={<StaffApplyPendingPage />} />
          <Route path="/staff/apply/*" element={<StaffApplyPage />} />
          <Route path="/org/apply" element={<OrgApplyPage />} />
          <Route path="/pricing/pay" element={<DemoPaymentPage />} />
          <Route path="/pricing/success" element={<CheckoutSuccessPage />} />
          <Route path="/pricing/cancel" element={<CheckoutCancelPage />} />
          <Route path="/onboarding/claim" element={<ClaimPlanPage />} />
          <Route path="/onboarding/setup" element={<SetupWizardPage />} />
          <Route path="/dashboard/*" element={<DashboardRouter />} />
          {/* Renamed from /admin to /super-admin so the URL itself reads
              clearly as platform-level access, distinct from any practice's
              own dashboard — keeps the two contexts from ever being
              confused at a glance. */}
          <Route path="/super-admin/*" element={<AdminRouter />} />
          <Route path="/admin/*" element={<Navigate to="/super-admin" replace />} />
          <Route path="/user" element={<PortalPage />} />
          <Route path="/portal" element={<PlanProvider><PortalSwitchPage /></PlanProvider>} />
          {/* Catch-all: every unknown URL lands here (404) instead of a
              silent blank screen — previously /staff, typos, and stale links
              rendered nothing. */}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </>);
}
