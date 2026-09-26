# AesthetixAI / Aiaceone — Architecture Overview

**Version:** 1.0 (as of 2026-09-25)
**Status:** Active development — post-consolidation (31 → 9 agents)

---

## 1. High-Level Stack

| Layer | Technology |
|-------|------------|
| **Backend API** | FastAPI (Python 3.11+) |
| **Database** | PostgreSQL 15+ (asyncpg, SQLAlchemy 2.0) |
| **ORM** | SQLAlchemy 2.0 (async) + Alembic migrations |
| **Auth** | Clerk (external) + standalone admin JWT |
| **Frontend** | React 18 + TypeScript + Vite |
| **Styling** | Tailwind CSS |
| **AI/LLM** | OpenAI GPT-4o, Mistral (free tier, multi-key), Groq (fallback) |
| **LLM Orchestration** | Custom `LLMService` with tiered routing, fallbacks, streaming |
| **Voice/Telephony** | Twilio (SMS stubbed, voice stubbed), Green API (WhatsApp) |
| **Email** | Resend (primary), SendGrid (fallback) |
| **Payments** | Stripe (Checkout, Billing Portal, Webhooks) |
| **Storage** | Cloudinary (images, PDFs) |
| **Observability** | Sentry (errors), LangSmith (LLM tracing) |
| **Background Jobs** | In-process pollers (Green API, Post-Op, Lead Nurturing) — *Celery/Redis planned* |
| **Deployment** | Docker + Docker Compose |

---

## 2. Repository Structure

```
plastic-surgeoun3.0/
├── backend/
│   ├── src/
│   │   ├── models/           # SQLAlchemy models (40+)
│   │   ├── router/           # FastAPI routers (flat, domain-first)
│   │   │   ├── v1/
│   │   │   │   ├── webhooks/     # Clerk, Stripe, Twilio, WhatsApp
│   │   │   │   └── billing/      # Cancel/resume/upgrade subscription
│   │   │   ├── admin/            # Super Admin panel APIs
│   │   │   ├── ai_receptionist/  # Inbound WhatsApp, voice
│   │   │   ├── landing_chat/     # Public website chat (Aria)
│   │   │   └── ...               # 40+ domain routers
│   │   ├── services/         # Business logic (60+ services)
│   │   │   ├── ai_receptionist/  # EmergencyTriage, VoiceChat, Inbound
│   │   │   ├── super_agent/      # Platform-level admin agent
│   │   │   ├── checkout/         # Stripe checkout + provisioning
│   │   │   ├── payment/          # Stripe subscription mgmt
│   │   │   ├── landing_chat/     # Aria (public chat)
│   │   │   ├── command_center/   # Clinic admin agent (streaming)
│   │   │   ├── finance_agent/    # Clinic finance agent (streaming)
│   │   │   └── ...
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── server/           # FastAPI app, middleware, deps, exceptions
│   │   └── config.py         # Pydantic Settings (all env vars)
│   ├── alembic/              # 50+ migrations
│   ├── Dockerfile
│   └── docker-compose.yml
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js-style pages (React Router)
│   │   │   ├── dashboard/        # Practice dashboard (Owner/Doctor/Receptionist)
│   │   │   ├── onboarding/       # Signup flow
│   │   │   ├── admin/            # Super Admin panel
│   │   │   └── ...
│   │   ├── components/       # Shared UI components
│   │   ├── data/             # Static data (agents, plans, tiers)
│   │   ├── hooks/            # Custom React hooks
│   │   └── index.tsx         # App entry
│   ├── package.json
│   └── vite.config.ts
├── lets-scroll-assets/       # Marketing site assets (local-only, gitignored)
├── AIACEONE_Investment*.pdf  # Business decks (gitignored)
├── task.md                   # Production readiness tracker
├── system_design.md          # Original architecture spec
├── README.md
└── .gitignore
```

---

## 3. Core Domain Models (Key Tables)

| Table | Purpose |
|-------|---------|
| `practices` | Clinic/organization root — owns all data |
| `users` | Staff accounts (Owner, Doctor, Receptionist) — linked to Clerk |
| `subscriptions` | Billing state per practice (tier, status, price, Stripe refs) |
| `plans` | Admin-editable pricing/capabilities (Practice, Enterprise, SOLO=trial) |
| `patients` | Patient records (phone = durable identity) |
| `conversations` | Thread per (patient, channel) — WhatsApp, Web Chat, Voice |
| `messages` | Individual messages in a conversation |
| `appointments` | Booked appointments with doctor/time |
| `surgeries` | Surgical procedures with status machine |
| `recovery_journals` / `recovery_checkins` | Post-op tracking |
| `agent_configs` | Per-practice agent enable/disable |
| `agent_logs` | Audit trail of every agent action |
| `sales_leads` | Platform-level leads (Aria, Demo form) with SLA |
| `demo_requests` | Website demo/consultation form submissions |
| `invoices` / `wallet_transactions` | Patient billing & practice credits |
| `audit_logs` | Platform admin actions |

---

## 4. AI Agent Architecture

### 4.1 Consolidated Agent Roster (9 Agents)

| Category | Agents | Slugs |
|----------|--------|-------|
| **Front Desk & Intake** | Receptionist, Appointment Reminder | `receptionist`, `appointment_reminder` |
| **Consultation & Screening** | Lead Qualification, Patient Intake, Consultation Assistant | `lead_qualification`, `patient_intake`, `consultation_assistant` |
| **Post-Op Care & Retention** | Post-Op Recovery, Marketing Retention | `post_op_recovery`, `marketing_retention` |
| **Business & Operations** | Finance Agent, Main Agent | `finance_agent`, `main_agent` |

**Legacy aliases (19)** map old 31-agent slugs to these 9 — see `frontend/src/data/agents/index.ts:50-79`.

### 4.2 Special Agents

| Agent | Scope | Streaming |
|-------|-------|-----------|
| **AI Receptionist** | Per-practice, inbound WhatsApp/Voice | ❌ (direct message send) |
| **Landing Chat (Aria)** | Platform, public website | ✅ `handle_message_stream` |
| **Command Center** | Per-practice, clinic admin | ✅ `ask_stream` (step reveal + token stream) |
| **Finance Agent** | Per-practice, clinic admin | ✅ `ask_stream` |
| **Super Agent** | Platform, Super Admin only | ✅ `ask_stream` |
| **Emergency Triage** | Per-practice, safety layer | N/A (pre-reply check) |

### 4.3 LLM Tier Routing (`LLMService`)

| Tier | Use Case | Provider Chain |
|------|----------|----------------|
| `high` | Clinical, billing, booking, escalation | OpenAI GPT-4o only |
| `low` | FAQ, translation, general chat, admin agents | Mistral (3 keys) → Groq → OpenAI |

**Key features:**
- Multi-key Mistral fallback on 429
- Groq reasoning_effort="low" to avoid hidden CoT token burn
- LangSmith tracing when `LANGSMITH_API_KEY` set
- Streaming (`chat_stream`, `chat_fast_stream`) with single-provider-per-stream (no mid-stream fallback)

---

## 5. Patient Communication Channels

| Channel | Status | Implementation |
|---------|--------|----------------|
| **WhatsApp (Green API)** | ✅ Real | Poller + webhook, per-practice credentials in `Practice.settings.green_api` |
| **Instagram/Facebook Messenger** | ✅ Real | Meta OAuth + webhook (`inbound_router.py`) |
| **Website Chat (Aria)** | ✅ Real | SSE streaming, unauthenticated, creates leads/patients |
| **SMS (outbound)** | ✅ Real | Twilio `send_sms()` |
| **Voice Inbound** | ❌ Stub | Twilio webhook returns `{"status": "received"}` — no STT/LLM/TTS |
| **Voice Outbound** | ✅ Partial | `TwilioService.make_call()` with static `<Say>` |
| **LinkedIn** | ❌ None | Marketing claim only |

---

## 6. Subscription & Billing Flow

```
Marketing Site → /checkout/create-session (unauth)
    → PendingSignup created
    → Stripe Checkout (real if keys configured, else demo page)
    → Stripe webhook: checkout.session.completed
        → PendingSignup.completed_at set
    → User claims via /practice/claim (Clerk signup)
        → ProvisioningService: Practice + User(OWNER) + Subscription(TRIAL)
            → Subscription.price = Plan.price
            → Subscription.end_date = start_date + Plan.trial_period_days
            → Subscription.stripe_subscription_id = NULL (set via webhook)
            → AgentConfigs seeded for tier
    → Stripe webhooks (subscription.* / invoice.*) sync status:
        - customer.subscription.created → stripe_subscription_id, price
        - customer.subscription.updated → status (active/trialing/past_due/canceled)
        - customer.subscription.deleted → CANCELLED
        - invoice.paid → ACTIVE
        - invoice.payment_failed → PAST_DUE
    → Cancel/Resume/Upgrade via /api/v1/billing/{cancel,resume,change-plan}
        - Standard SaaS: cancel_at_period_end=true
```

**Tiers:**
- **PRACTICE** ($999/mo) — all 9 agents, 1 location, analytics
- **ENTERPRISE** (Custom) — multi-location, BAA, custom integrations
- **SOLO** → repurposed as **hidden 3-day Free Trial** (Super Admin grant only, `display_order=-1`)

---

## 7. Background Jobs (Pollers)

| Poller | Purpose | Interval |
|--------|---------|----------|
| `GreenAPIPoller` | Fetch inbound WhatsApp messages | ~5s |
| `PostOpFollowUpPoller` | Send recovery check-ins to patients | Daily |
| `LeadNurturingPoller` | Send follow-up messages to leads | Daily |

**⚠️ Current limitation:** In-process, no distributed lock. Multi-instance deploy = duplicate messages. **Planned:** Celery + Redis.

---

## 8. Security & Compliance

| Area | Implementation |
|------|----------------|
| **Auth** | Clerk (staff), standalone JWT (admin), ID+PIN (patient portal) |
| **Tenant Isolation** | All queries scoped by `practice_id` (enforced in services) |
| **Webhook Verification** | Clerk (svix HMAC), Stripe (signature), Twilio (TODO) |
| **Secrets** | `.env` only, `.env.example` tracked, production validation in `config.py` |
| **PII/PHI** | No PII in Sentry (`send_default_pii=False`), audit logs for admin actions |
| **HIPAA** | No BAA yet — Enterprise tier only; audit logs Enterprise-gated |
| **Rate Limiting** | `RateLimiter` service (Redis-backed, per-practice) |

---

## 9. Admin & Super Admin

| Panel | Access | Features |
|-------|--------|----------|
| **Clinic Dashboard** | Owner/Doctor/Receptionist (role-gated) | Patients, Calendar, Agents, Billing, Settings |
| **Super Admin** | Platform admins (`is_platform_admin`) | All practices, Plans, Sales Leads, Org Approvals, Super Agent |
| **Sales Leads** | Super Admin | Aria leads, Demo form leads, Book Consultation leads — 24hr SLA tracking |

---

## 10. Key Configuration (`.env`)

```bash
# Required for production
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://...
CLERK_SECRET_KEY=sk_live_...
CLERK_WEBHOOK_SECRET=whsec_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_PRACTICE=price_...
ADMIN_PASSWORD=<strong-random>
ADMIN_JWT_SECRET=<strong-random>
PATIENT_PORTAL_JWT_SECRET=<strong-random>
SENDGRID_API_KEY=SG....
RESEND_API_KEY=re_...
OPENAI_API_KEY=sk-...
MISTRAL_API_KEY=... (up to 3)
GROQ_API_KEY=gsk_...
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
GREEN_API_INSTANCE_ID=...
GREEN_API_TOKEN=...
META_APP_ID=...
META_APP_SECRET=...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
SENTRY_DSN=https://...
LANGSMITH_API_KEY=...
```

---

## 11. Migration / Deployment Notes

- **Alembic:** Run `alembic upgrade head` on deploy
- **Plan Seeding:** Plans auto-seeded via migration `c9da7a5261a3` (idempotent)
- **Agent Costing:** Self-seeds on first read (`AgentCostingService`)
- **Docker:** `docker-compose.yml` runs backend (uvicorn) + frontend (nginx) + postgres + redis
- **Health Check:** `GET /health` (backend), `GET /` (frontend)

---

## 12. Known Gaps / Planned Work

| Area | Status | Notes |
|------|--------|-------|
| Voice Inbound | ❌ Stub | Need Twilio `<Gather>` + Deepgram STT + Groq LLM + Twilio TTS |
| Background Jobs | ⚠️ In-process | Migrate to Celery/Redis for multi-instance |
| Emergency Triage | ✅ Basic | Keyword+LLM confirm → NEEDS_ATTENTION; expand red-flag rules |
| HIPAA/BAA | ⚠️ Enterprise only | Need signed BAA, audit log export, encryption at rest |
| Multi-location | 🔄 Enterprise | Plan supports `max_locations=null`, UI not built |
| EHR Integration | ❌ None | Enterprise custom integration only |
| Insurance Verification | ❌ None | Cost table row only |
| Video Consultation | ❌ None | Cost table row only |
| Real Usage Metering | ❌ Estimated only | `ASSUMED_MONTHLY_SESSIONS_PER_AGENT=150` |

---

## 13. Team & Ownership

- **Solo Developer:** Furqan Raza
- **Product Owner:** AceOne Solutions (pricing, sales, marketing, GTM decisions)
- **Original Build Team (historical):** Furqan, Wahaj, Muneeb — names removed from repo artifacts

---

*This document is the single source of truth for architecture. Stale docs (`backend/README.md`, `frontend/system.md`, `task.md` pre-2026-09-25) should be deprecated in favor of this file.*