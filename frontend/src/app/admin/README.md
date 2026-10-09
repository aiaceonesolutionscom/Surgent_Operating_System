# admin (Super Admin Panel)

The platform super admin panel - for the Aiaceone team, not clinics. Every route
under `/admin/*` is registered once in `AdminRouter.tsx`, mirroring
`app/dashboard/DashboardRouter.tsx`'s role for the doctor dashboard.

**Auth is a standalone username/password + JWT, deliberately independent of
Clerk.** `AdminSignInPage.tsx` posts to `POST /api/v1/admin/auth/login`
(`backend/src/services/admin/admin_auth_service.py`), stores the returned
JWT in `localStorage` (`api/admin.ts`), and every subsequent
`/api/v1/admin/*` call attaches it as a Bearer token. The backend verifies
it with `require_admin_token` (`server/dependencies.py`) - a completely
separate mechanism from Clerk's `get_current_user`/`require_platform_admin`
chain (that Clerk-based path still exists in the backend but nothing calls
it anymore; kept for reference in case a future multi-admin-via-Clerk-roles
feature wants it). Credentials live in `backend/.env`
(`ADMIN_USERNAME`/`ADMIN_PASSWORD`/`ADMIN_JWT_SECRET`) - change them for
any real deployment.

**`AdminRequireAuth.tsx` fails closed, no dev bypass**: a missing or
backend-rejected token always redirects to sign-in - there's no
`RequireAuth.tsx`-style "run without auth if unconfigured" fallback, since
this panel edits live pricing.

**Visual language**: dark sidebar (`bg-panel` `#15171A`) against the light
`canvas` content area - the inverse of the doctor dashboard's light sidebar -
using the same `accent`/`cyan`/`panel` tokens established for the
"Aiaceone premium" surfaces (`app/auth/AuthLayout.tsx`,
`app/onboarding/CheckoutPage.tsx`, `app/dashboard/overview/OverviewPage.tsx`).
`AdminSignInPage.tsx` reuses `AuthLayout`'s split-screen shell via its
`variant="admin"` prop for the same reason, with its own plain form instead
of a Clerk widget.

**Every number on the overview is measured, none is hardcoded.** The page
(`overview/PlatformOverviewPage.tsx`) refreshes itself every 30 seconds from
`GET /admin/platform_metrics`, `/admin/summary` and `/admin/activity`:

* clinic / user / patient / appointment / subscription counts come straight
  from the clinic tables;
* **AI** (runs, avg + p95 latency, tokens, cost, failed-call rate, top spenders)
  comes from the `llm_calls` table - one row per provider request, written by
  `LLMService._create` - so it survives restarts and covers every instance.
  Cost is tokens x the provider's *list price* (`services/telemetry/pricing.py`,
  re-check it against provider pricing pages); it is labelled as such;
* **SYSTEM** (24h error rate, requests, slow requests, slow queries + the
  slowest statements, restarts) comes from `system_metric_buckets` and
  `slow_query_log`, flushed every 30s by `services/telemetry/recorder.py`.
  "Uptime" is the only per-process figure. DB health is a live `SELECT 1`
  round trip;
* **MRR** is active (paying) subscriptions only - trials are shown as pipeline.

The one projection left is the "Plan cost projection" table on a clinic's page
(per-session agent prices x an assumed monthly volume) - it is labelled as a
projection and sits below the measured AI cost.
