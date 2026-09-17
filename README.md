# AesthetixAI — Surgent Operating System

A real, working **Clinic Management OS** for plastic surgery and aesthetic
medicine practices — Owner, Doctor, and Receptionist roles each get a real,
authenticated dashboard backed by a real Postgres database — plus an **AI
Agent Workforce** layered on top: **9 named agents across 4 practice
categories**, every one backed by a real backend endpoint (not a shell),
plus a platform-wide **Super Agent** in the admin panel.

This repo is a monorepo: the practice-facing web app (`frontend/`) and its
API (`backend/`).

```
.
├── frontend/          Vite + React + TypeScript — the marketing/product site
│                      AND the real, authenticated Owner/Doctor/Receptionist
│                      dashboard (patients, appointments, billing, staff, ...)
│                      AND the platform admin panel (/admin, /super-admin)
├── backend/           FastAPI (Python) — the real clinic-operations API,
│                      the 9 agents' APIs, admin API, auth, integrations
└── design-references/ Early AI-generated UI mockups, kept for reference only —
                        not built, not part of either app
```

---

## What's actually here today

Two genuinely different things share this codebase, and it's worth being
precise about which is which before reading anything else below:

1. **The clinic operating system** — patients, appointments, billing,
   staff, clinical documentation, inventory, leads — is **real**. Every
   domain below is backed by real SQLAlchemy models, real Alembic
   migrations, real CRUD APIs, real role-based access control, and a real
   authenticated React dashboard.
2. **The AI agent layer** is this product's core differentiator: **9
   agents, all real** (`receptionist`, `appointment_reminder`,
   `patient_intake`, `lead_qualification`, `consultation_assistant`,
   `main_agent`, `finance_agent`, `post_op_recovery`,
   `marketing_retention`) grouped into 4 practice categories (Front Desk
   & Intake, Consultation & Screening, Business & Operations, Post-Surgery
   Care) — plus **Aria**, the marketing site's own AI chat, and the
   platform-wide **Super Agent** at `/super-admin/super-agent` that works
   across every practice.

Nothing below is aspirational unless it's explicitly marked as such.

## The real clinic operating system

Every one of these is a real, DB-backed feature with a real dashboard
screen, exercised via real database tests and live browser runs during
development (not just "the code compiles"):

| Domain | What it actually does |
|---|---|
| **Auth & roles** | Clerk-based sign-in for staff; four roles (Owner, Doctor, Receptionist, platform Staff/admin) with granular, per-record permission grants — not just role-level gating. Staff also get a separate authenticated **admin panel** (`/admin`) with its own login |
| **Patients** | Full CRM: contact info, chief complaint, consent status, medical profile (allergies, history, medications, insurance, referral source), and a real **lifecycle/funnel stage** (inquiry → contacted → consult → treatment planned → patient, or lost) |
| **Doctors** | Owner-managed roster; a doctor can also **self-apply** via a shareable signup link, reviewed and approved by the Owner before they get real dashboard access |
| **Receptionist / Front Desk** | A real staff role — today's schedule, check-in, waiting room, booking — invited by the Owner via email, with its own granular permission set |
| **Appointments** | Full booking/reschedule/cancel/complete/check-in lifecycle, plus no-show marking and a real waitlist |
| **Clinical documentation** | SOAP-structured consultation notes, phased treatment plans built from a real procedure catalog, per-doctor procedure pricing, and per-document e-consent (typed-name signature, **versioned templates** so signed wording is frozen) |
| **Before/after photos** | Cloudinary-backed upload, timeline grouping by stage (before/day7/day14/1mo/3mo/6mo/1yr), a drag-comparison slider, and an independent marketing-use approval flag separate from clinical consent |
| **Surgery** | Real record (surgeon, assistant, anesthesia, pre-op checklist, implants with lot numbers, operative note), full planned → completed/cancelled lifecycle |
| **Billing / Invoices** | Invoices generated ad-hoc or straight from a treatment plan's priced items, line items, tax/discount, mark-paid workflow |
| **Finance** | Expense tracking, a real revenue-vs-expense overview (Owner), and a dedicated **Finance Agent** that answers revenue/expense questions in plain language |
| **Leads / Funnel** | The patient lifecycle stage above, visualized as a real funnel with a "lost" breakdown + a real Sales Leads feed in the admin panel |
| **Inventory** | SKU catalog + received-batch tracking (lot/quantity/expiry), FEFO consumption, low-stock flagging |
| **Post-op recovery** | Real `RecoveryJournal` tied to each Surgery, checkpoint-based (Day 1/3/7/14/1mo) |
| **Internal messaging** | Two-way threads between the Owner and each Doctor/Receptionist, surfaced from the topbar |
| **AI Receptionist / Aria** | The marketing site chat (Aria) answers questions live via LLM and every completed booking lands as a patient lead (source "Landing Chat") with immediate follow-up — see below |
| **Human takeover** | Staff can reply directly to an AI-handled conversation and the AI pauses auto-replying until manually resumed — a human and the bot never talk over each other |
| **Command Center** | "Main Agent" — a real assistant staff can ask things like "which patients need surgery?" — genuinely queries the real database via real category handlers, gated by the plan tier |
| **Practice subscription** | **Practice** (flat $999/mo, all categories included) and **Enterprise** (custom) plans — billing → Stripe checkout → claim → setup wizard. Plans and every practice's tier are managed from the admin panel; AI features are **gated server-side** by the practice's plan, not just hidden in the UI |

## Backend (`backend/`)

FastAPI + async SQLAlchemy 2.0 + Postgres + Alembic. Two kinds of domains
live side by side under the same layered convention:

```
backend/src/
├── router/<domain>/<domain>_router.py             real clinic-ops domains:
├── controller/<domain>/<domain>_controllers.py    patients, appointments, billing,
├── services/<domain>/<domain>_services.py         finance, inventory, clinical, staff, ...
│
├── router/agents/<name>_agent/<name>_agent_router.py     the 9 AI agents +
├── controller/agents/<name>_agent/<name>_agent_controllers.py  super agent,
├── services/agents/<name>_agent/<name>_agent_services.py       one named folder each
├── router/admin/                                    platform admin API (staff-only):
│    practices CRUD, subscriptions, plans, users,
│    org-request approval, sales leads, super-agent
├── router/agents/__init__.py    registers every router (agent or not) -> /api/v1/...
│
├── models/       SQLAlchemy models (Practice, Patient, Appointment, Invoice, Plan, ...)
├── schemas/      Pydantic request/response contracts
├── server/       middleware, Clerk auth dependency chain, exception handling
└── services/     shared, non-domain services: llm, messaging, storage,
                  cloudinary, email, agent_log, rate_limiter (Redis-backed), ...
```

Router → Controller → Service is the call chain everywhere: the router
defines HTTP routes + the auth dependency (`get_current_practice_user`,
`require_role(...)`), the controller adapts a request into a service call,
the service holds the actual logic. Every practice-scoped query is
filtered by `practice_id` resolved server-side from the authenticated
user — never trusted from the client. The new platform admin area is
authenticated separately (username + password, JWT) and is the only
surface that can see across practices.

**Running it locally:**
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # every setting has a safe default — the app boots
                                  # with none of them real, see the table below for
                                  # exactly what each one unlocks
alembic upgrade head
uvicorn src.main:app --host 127.0.0.1 --port 8001
```
`GET /health` is a liveness check with no auth. Everything else expects a
Clerk-issued bearer token (`Authorization: Bearer <token>`), except the
patient portal (ID+PIN login → its own JWT) and the admin panel
(`/api/v1/admin/auth/login` → admin JWT).

**Redis note (Windows local dev):** rate limiting, the patient-portal PIN
OTP store, booking drafts, and the landing-chat cache use Redis
(`REDIS_URL=redis://localhost:6380` in the WSL setup). If Redis is not
reachable the app **fails open** (connection timeouts are short and the
rate limiter caches the outage), so everything still works — it just isn't
rate-limited. Start Redis (`redis-server`, typically via WSL) to get the
real protection.

## Frontend (`frontend/`)

Vite + React 18 + TypeScript + Tailwind.

```
frontend/src/
├── app/
│   ├── auth/         real Clerk sign-in/sign-up, doctor self-apply flow,
│   │                 staff invite acceptance
│   ├── onboarding/   pricing -> Stripe checkout -> claim plan -> setup wizard
│   ├── dashboard/    the real, authenticated Owner/Doctor/Receptionist app —
│   │                  one folder per domain: patients/, doctors/, appointments
│   │                  (front-desk/), clinical/, billing-invoices/, finance/,
│   │                  inventory/, leads/, messages/, receptionist/ (AI monitor),
│   │                  staff/, plan/, settings/, layout/ (Sidebar role-gating)
│   ├── admin/        platform staff panel: practices, plans, users, org-requests,
│   │                  sales leads, and /super-admin (Super Agent chat + sessions)
│   └── super-admin/...
├── components/       marketing site sections (Navbar, hero, pricing, ...)
├── pages/            public marketing pages (Home, Agents catalog, ...)
├── data/agents/       one file per AI agent — content/capabilities/category —
│                      aggregated by index.ts into the public catalog
├── hooks/             e.g. useLivePlans (plans served from the backend)
└── api/               typed fetch wrapper (client.ts) + one file of functions
                       per backend domain (entities.ts, practice.ts, admin.ts, ...)
```

`app/dashboard/` is **not** placeholder scaffolding — it's the real product:
every role signs in via Clerk, lands on a role-appropriate view
(`DashboardRouter.tsx`), and `layout/Sidebar.tsx` shows/hides each nav item
by role and by granted permission (`requiresPermission`), not just by
role alone.

**Running it locally:**
```bash
cd frontend
npm install
cp .env.example .env.local       # VITE_API_BASE_URL must point at the backend —
                                  # default is http://127.0.0.1:8001
npm run dev
```
Open the app at `http://localhost:5173` (not `127.0.0.1` — the backend's CORS
allow-list is `localhost`-only, so the two don't count as the same origin).

**Deploying**: `frontend/Dockerfile` builds the static site behind nginx
(SPA fallback included) — no Node process at runtime. `backend/Dockerfile`
runs the API directly.

## The AI agent layer — what's real

Nine agents, four categories — **every one is real** (a working backend
endpoint answering with real data, not a stub), all logged via
`AgentLogService` so usage is queryable:

| Category | Agents (slug) |
|---|---|
| Front Desk & Intake | `receptionist` (Aria — marketing-site chat/triage, real booking → lead), `appointment_reminder` |
| Consultation & Screening | `patient_intake`, `lead_qualification`, `consultation_assistant` |
| Business & Operations | `main_agent` (Command Center), `finance_agent` |
| Post-Surgery Care | `post_op_recovery`, `marketing_retention` |

Plus, outside the per-practice catalog:

- **Aria** — the marketing site's own chat widget. Fast (Groq-first,
  short capped answers), answers pricing/questions, and converts a booking
  conversation into a real lead handed to the practice.
- **Super Agent** — platform-wide, staff-only, at `/super-admin/super-agent`.
  One assistant that works across every practice's data (practices, plans,
  sales leads, conversations) instead of being scoped to one practice.

Latency discipline is built in: interactive agents cap their LLM `max_tokens`
so the UI stays snappy, and Aria's reply path routes through a dedicated
`chat_fast` Groq-first helper rather than the general-purpose chat call.

## What's deliberately still mock data

Separate from "not built yet" above:

- **Legacy Overview / Sessions / Analytics widgets** in the older dashboard
  areas were intentionally left on mock data at the product owner's request
  (a decision to revisit, not a technical gap). In contrast, the **agent**
  layer (Command Center, Finance Agent, Super Agent, Aria) reads real data
  end-to-end.
- **AI Receptionist monitor** page's live call/transcript widgets need call
  streaming infra that isn't wired up yet — clearly labeled "Preview" on the
  page; its KPI numbers and conversation feed are real.

## Configuration — what needs a real credential, and what breaks without one

Every setting in `.env` has a default the app boots with — nothing is
required just to run it locally. This is what's currently a **placeholder**
in this project's own working `.env` vs what's **real**, and exactly what
silently doesn't work as a result. (Values themselves are never in this
repo — `.env` is gitignored; only `.env.example` — names, no secrets — is
tracked.)

| Service | Env vars | Status here | Breaks without a real one |
|---|---|---|---|
| **Clerk** (staff auth) | `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_JWKS_URL`, `CLERK_WEBHOOK_SECRET` | Real (webhook secret is a placeholder) | Auth itself is real and working. Webhook signatures aren't verified yet — fine in dev, needs a real value before production |
| **Postgres** | `DATABASE_URL` | Real | — |
| **Mistral** | `MISTRAL_API_KEY` | Real | Fallback LLM tier — powers the AI layer when Groq is down / for non-Aria paths |
| **Groq** | `GROQ_API_KEY`, `GROQ_MODEL` (e.g. `openai/gpt-oss-120b`) | Real | Aria's fast reply path, JSON extraction, and admin Super Agent fail |
| **OpenAI** | `OPENAI_API_KEY` | Placeholder | Optional high-tier fallback — nothing on a live path hard-requires it |
| **Twilio** | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Placeholder | Legacy voice path idle — active messaging runs through WhatsApp/email, not Twilio |
| **WhatsApp / Green API** | `GREEN_API_ID`, `GREEN_API_TOKEN` | Real (one real number connected) | Live WhatsApp conversations, media/profile lookups, human-takeover replies |
| **Cloudinary** | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Real in this project's `.env` | Before/after photo uploads and doctor-application documents fail (uploads stored here) |
| **Resend** | `RESEND_API_KEY`, `RESEND_FROM_EMAIL` | Real | The active outbound-email path (notifications, practice outreach) |
| **Stripe** | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_SOLO`, `STRIPE_PRICE_PRACTICE` | Placeholder | Checkout sessions are created server-side and the flow works end-to-end locally, but a real transaction needs real keys |
| **Redis** | `REDIS_URL` | Configured (WSL), optional at runtime | Rate limiting / OTP store / booking drafts / meeting-cache **fail open** if unreachable (see note above) — real protection needs it running |

## How ready is this, honestly

- **The core clinic operating system** — patients, appointments, billing,
  staff, clinical documentation, surgery, recovery, inventory, leads,
  internal messaging, patient portal — is **built, tested, and usable today**
  by a real practice, gated only by the placeholder credentials above
  (Stripe, Twilio). Those are pure configuration — real keys and the exact
  same code paths start working with no code changes.
- **Auth, roles, and permissions** are fully real: Clerk sign-in for the
  four staff roles, granular per-record permission grants, doctor self-apply,
  staff email invites, a separate patient ID+PIN portal auth, and a
  username/password admin panel auth.
- **The AI agent layer is 9 real agents + Aria + a platform Super Agent**,
  with server-side plan gating (Practice $999 flat / Enterprise custom).
- Everything was verified with real-database smoke scripts and live browser
  runs; there is **no committed automated test suite / CI yet** — worth
  adding before scaling the team.
- **What's actually blocking a fully production-ready launch:**
  1. Real Stripe keys for live checkout; the pipeline (sessions, claim,
     setup wizard) is code-complete.
  2. A real `CLERK_WEBHOOK_SECRET` for cryptographic webhook verification.
  3. Redis running in the hosting environment (it's already integrated —
     rate limiting, OTP store, booking drafts).
  4. A decision on re-wiring the legacy mock Overview/Sessions/Analytics
     widgets vs. keeping agent-focused analytics.
  5. Production infrastructure (VPS sizing, logging/monitoring) — everything
     above was built and verified in local development only.

## Tech stack

**Backend**: FastAPI, SQLAlchemy 2.0 (async) + Postgres, Alembic, Pydantic v2,
Clerk (auth), Mistral + Groq (LLM), Green API (WhatsApp), Stripe, Resend,
Cloudinary, Redis (rate limiting/OTP, fail-open), Twilio (legacy voice path
idle).

**Frontend**: React 18, TypeScript, Vite, Tailwind CSS, React Router,
Clerk React SDK, framer-motion, lucide-react.