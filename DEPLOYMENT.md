# Deployment runbook — GitHub · Neon · InsForge

Frontend → InsForge hosting (`deployments`), backend → InsForge compute (a container), database → Neon.
Every command below is run from the repo root unless stated.

> **Status of the code:** the app refuses to boot in production on an unsafe config
> (`backend/src/config.py → validate_production`) and the frontend refuses to *build* without a real API URL
> and Clerk key (`frontend/vite.config.ts`). So a wrong setting fails loudly at deploy time, not silently in front of patients.

---

## Current deployment (staging, 2026-10-09)

| | |
|---|---|
| Frontend | https://surgeon-os.insforge.site (same site, also reachable at https://h7snbk6c.insforge.site) — InsForge hosting, project `Surgent_OS`. **Every origin that serves the frontend must be in the backend's `CORS_ORIGINS`** (comma-separated), otherwise the browser reports "Failed to fetch". |
| Backend API | https://aiaceone-api-b878dd48-8587-49ba-8ceb-a4981544c73b.fly.dev (InsForge compute service `aiaceone-api`, region `sin`, 512 MB — the free plan's per-machine ceiling) |
| Database | Neon project `muddy-firefly-59906622`, branch `production` (schema at Alembic head `8a4c1e9f3d27`) |
| Auth | Clerk **development** instance → backend runs with `APP_ENV=staging` (the production guard rejects `sk_test_` keys) |
| Config files | `backend/.env.production` (git-ignored) is the single source for backend env; frontend env lives in InsForge (`deployments env list`) |

Redeploy / operate (run from the repo root, where `.insforge/` links the project):

```bash
# backend (rebuilds remotely; the env file replaces the service's env)
npx @insforge/cli compute deploy backend --name aiaceone-api --port 8000 --region sin --memory 512 --env-file backend/.env.production
# one-off env change without restating the rest
npx @insforge/cli compute update <service-id> --env-set KEY=VALUE
# frontend
npx @insforge/cli deployments deploy frontend
# database migrations: from your machine, against Neon's DIRECT endpoint
MIGRATION_DATABASE_URL=<direct url> DATABASE_URL=<pooled url> python -m alembic upgrade head   # run inside backend/
```

`RUN_MIGRATIONS` is `false` in the env file on purpose: the service scales to zero, and a migration run on every wake-up would slow each cold start.
Apply new migrations from your machine before deploying code that needs them.

Moving to real production = swap in live Clerk keys (`sk_live_` / `pk_live_`), set `APP_ENV=production`, add `STRIPE_*` and a hosted `REDIS_URL`; the guard
then validates all of it at boot.

---

## 0. Before the first push — do these first

| # | Action | Why |
|---|---|---|
| 1 | **Rotate the Green API token** (green-api.com → instance → API token). | The old token sits in `backend/*.log` files that were committed and already pushed to `origin/main` (httpx logged the full URL, token included). The logs are now untracked and the logger is silenced, but the token is in git history. |
| 2 | Decide on history: `git filter-repo --path-glob 'backend/*.log' --invert-paths` (then force-push), **or** keep the repo private. | Rotating the token neutralises the leak; purging history is hygiene. Force-pushing rewrites `origin/main` — do it deliberately. |
| 3 | Rotate any other key that was ever pasted into a log or chat. | Cheap insurance. |
| 4 | `git status` — review, then commit the working tree. | The audit/hardening work in this branch is uncommitted. |

`.env` files are git-ignored and were never committed (checked). Only `*.env.example` is tracked.

## 1. Neon (database)

1. Create a Neon project (pick the region closest to the backend's region).
2. Copy **two** connection strings from the dashboard:
   - **Pooled** (host contains `-pooler`) → `DATABASE_URL` (the running app).
   - **Direct** (no `-pooler`) → `MIGRATION_DATABASE_URL` (Alembic).
3. Paste them as-is. `sslmode=require` / `channel_binding=require` and the `postgresql://` scheme are rewritten for asyncpg
   automatically (`backend/src/db_url.py`); pgbouncer-safe settings are applied when the host is a pooler.
4. Migrations: the whole chain (58 revisions) was run from an **empty** database to `head` and the resulting schema was compared with the
   models — no drift that matters (only cosmetic FK `ON DELETE` options). It will create everything on a fresh Neon branch.

> Neon free compute auto-suspends when idle, but this app's background pollers query the DB every few seconds, so it will effectively stay awake.

## 2. Backend env vars (secrets → `--env-file`, never in the repo)

Required — the app **will not start** in production without them:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `DEBUG` | `false` |
| `DATABASE_URL` / `MIGRATION_DATABASE_URL` | Neon pooled / direct |
| `CORS_ORIGINS` | the deployed frontend origin(s), `https://…`, comma-separated. **No** localhost, no `*`. |
| `FRONTEND_URL` | `https://…` frontend URL |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | not the default `Aceone` |
| `ADMIN_JWT_SECRET`, `PATIENT_PORTAL_JWT_SECRET` | two different random strings, ≥ 32 chars (`openssl rand -hex 32`) |
| `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_JWKS_URL` | **live** keys (`sk_live_…` / `pk_live_…`) from the Clerk *production* instance |
| `CLERK_WEBHOOK_SECRET` | from the Clerk webhook endpoint (§5) — required, unsigned webhooks are refused |
| `LANGSMITH_TRACING_V2=false` | …unless you have a signed BAA/DPA with LangChain *and* set `LANGSMITH_API_KEY`. Tracing sends prompts (patient data) to a third party. |

Strongly recommended: `REDIS_URL` (a hosted Redis, `rediss://…` — without it patient **OTP login cannot work** and rate limiting is per-instance only),
`SENTRY_DSN`, `PLATFORM_ADMIN_EMAILS`, `CLOUDINARY_*`, `RESEND_API_KEY` + `RESEND_FROM_EMAIL` (verify a sending domain),
at least one LLM key (`GROQ_API_KEY` / `MISTRAL_API_KEY` / `OPENAI_API_KEY`).

Billing (when ready): `STRIPE_SECRET_KEY` (live), `STRIPE_WEBHOOK_SECRET`, and a `stripe_price_id` on the Plan rows. (The Admin → Plans drawer has no field for it yet, so set it with SQL: `update plans set stripe_price_id = 'price_…' where tier::text ilike 'practice'`.)
**Until Stripe is configured, online checkout answers 503** — there is no demo/simulated payment mode in any environment.

Optional: `GREEN_API_WEBHOOK_SECRET` (only if you switch WhatsApp from polling to push), `SEED_SAMPLE_DATA_ON_APPROVAL=false` (start approved clinics empty).

## 3. Deploy the backend (InsForge compute)

```bash
npx @insforge/cli login            # once
npx @insforge/cli link             # or `create` — this is the InsForge project, NOT the database
# Put RUN_MIGRATIONS=true in the env file for the first deploy so it creates the schema
# (`--env` and `--env-file` are mutually exclusive in the CLI):
npx @insforge/cli compute deploy backend --name aiaceone-api --port 8000 \
      --env-file backend/.env.production
```

* Source mode needs `flyctl` on PATH (no Docker needed). Compute is a **private preview** on InsForge.
* `RUN_MIGRATIONS=true` runs `alembic upgrade head` on boot — fine for the **one** instance this app must run as (see below).
* Health check: `GET /health`.

### ⚠ One instance, always on

The WhatsApp poller, post-op follow-ups and lead nurturing run **inside the API process**, and the app is built for exactly one worker/replica
(a second would handle every WhatsApp message twice). InsForge compute **scales to zero when idle**, which would silently stop those pollers.
Before relying on WhatsApp / follow-ups in production either: (a) ask InsForge support for an always-on service, or
(b) switch WhatsApp to Green API push webhooks (`POST /api/v1/ai-receptionist/inbound/whatsapp` + `GREEN_API_WEBHOOK_SECRET`) and drive the follow-up jobs
from `insforge schedules` hitting an endpoint — which needs a small change; or (c) host the backend where it can stay running.

## 4. Deploy the frontend (InsForge hosting)

```bash
cd frontend
npx @insforge/cli deployments env set VITE_API_BASE_URL https://<backend-url>
npx @insforge/cli deployments env set VITE_CLERK_PUBLISHABLE_KEY pk_live_…
npx @insforge/cli deployments env set VITE_APP_VERSION 1.0.0      # = backend APP_VERSION
# optional: VITE_SENTRY_DSN, VITE_POSTHOG_KEY, VITE_POSTHOG_HOST
npx @insforge/cli deployments deploy .
```

* `vercel.json` provides the SPA rewrite, cache headers and security headers. Missing `/assets/*` files 404 instead of returning the HTML shell.
* Never set `VITE_DEMO_MODE` (the build refuses if it is set).
* A local `npm run build` is refused while `.env.local` points at localhost — use `ALLOW_LOCAL_BUILD=1 npm run build` for a local smoke build.
* The hero's scroll animation is 1,632 static WebP frames in `frontend/public/lets-scroll/frames/` (~31 MB: 816 desktop + 816 mobile, from `scripts/build-scroll-frames.py`); they are served by the same hosting as the site (not Cloudinary, not the database) and loaded lazily per scene. `vercel.json` caches them for a year (`immutable`) - safe because every frame URL carries `?v=<hash>` from `src/components/hero/frames.manifest.json`. After regenerating frames run the script (or `--manifest-only`) so the hash changes.

## 5. Third-party setup

* **Clerk (production instance):** add the production domain; webhook endpoint `https://<backend>/api/v1/webhooks/clerk` for `user.created` → copy the signing secret to `CLERK_WEBHOOK_SECRET`.
* **Stripe:** webhook endpoint `https://<backend>/api/v1/webhooks/stripe` (events `checkout.session.completed`, `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`).
* **Green API:** per-clinic instance + token are entered in the dashboard (Settings → Integrations); nothing to set globally for polling.
* **Meta OAuth** (if used): whitelist `https://<frontend>/dashboard/settings/integrations/meta-callback`.

## 6. Post-deploy smoke test

1. `GET https://<backend>/health` → `{"status":"ok"}`.
2. Open the frontend → `/super-admin` → sign in → **Platform overview** shows your real clinic/user counts; `System → DB health` is a few ms to tens of ms (Neon round-trip).
3. Sign in as an Owner → dashboard loads (a Doctor/Receptionist lands on their own home with no Owner UI flash).
4. Chat with Aria on the landing page and a Command Center question → streaming replies work; a minute later the Overview's **AI → Runs / Cost** moves.
5. Super Admin → Clinics → suspend a test clinic → its staff are locked out of the dashboard immediately; reactivate.

## 7. Known gaps (not blocking, but know them)

* LangSmith `@traced_*` instrumentation decorators are missing from the 12 agent services (1 test, `test_shipped_services_are_all_instrumented`, fails). Harmless with tracing off.
* Patient photos / voice notes / documents are uploaded to Cloudinary as **public** URLs (unguessable, but not access-controlled) — move to authenticated delivery before storing real patient imagery at scale.
* Public endpoints without rate limits: `/landing-chat/*` (LLM cost), `/public/consultation-request`, `/demo-requests`, checkout.
* `/landing-chat` and `/public/consultation-request` attach leads to the **oldest** practice on the platform — fine for one tenant, wrong once several clinics share the platform.
* PostHog session replay now masks all text and inputs; Sentry no longer captures local variables (both were PHI risks).
* Process work, not code (see `task.md` §8): legal/BAA review, a tested backup-and-restore drill (Neon branches/PITR make this cheap), self-serve onboarding hardening.
