// Single source of truth for every /admin/* path — mirrors
// app/dashboard/constants/routes.ts's role for the doctor dashboard.
export const ADMIN_ROUTES = {
  root: "/super-admin",
  overview: "/super-admin",
  clinics: "/super-admin/clinics",
  clinicDetail: (id: string) => `/super-admin/clinics/${id}`,
  orgRequests: "/super-admin/org-requests",
  plans: "/super-admin/plans",
  salesLeads: "/super-admin/sales-leads",
  superAgent: "/super-admin/super-agent",
  signIn: "/super-admin/sign-in"
} as const;
