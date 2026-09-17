# Aiaceone — System Design

**Status**: living document, started at the beginning of a 30-day build push
(see [Roadmap](#30-day-roadmap) below) to take the platform from "real,
tested clinic operating system" to "pilot-ready, complete patient-journey
platform with a real AI layer." Update this file as each week lands —
it's the durable reference, not a snapshot of one conversation.

---

## 1. Product vision

**One Operating System for the entire patient journey** — from first
inquiry to consultation, treatment, payment, and post-op follow-up — for
plastic surgery and aesthetic medicine practices, with AI automation
layered on top of real clinic operations, not instead of them.

```
Instagram/WhatsApp inquiry → Lead → AI Receptionist → Appointment
  → Patient Intake → Doctor Consultation → Treatment Plan
  → Before Photos → Consent → Payment/Deposit → Surgery/Treatment
  → Post-op Follow-up → Review → Re-engagement
```

Four real user types, each with their own authenticated experience:
**Owner** (practice control room), **Doctor** (clinical work + their own
patients), **Receptionist** (front desk, day-to-day operations), **Patient**
(their own journey, via a dedicated portal — see §4.4).

---

## 2. Architecture

### 2.1 Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, async SQLAlchemy 2.0, Postgres, Alembic, Pydantic v2 |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router |
| Auth (staff) | Clerk — Owner/Doctor/Receptionist |
| Auth (patient) | Custom Patient ID + PIN (see §4.4) — deliberately not Clerk (per-MAU staff pricing model, patients aren't staff) |
| LLM | Mistral (general tier) + **Groq** (fast tier — Aria's reply path & JSON extraction, OpenAI-compatible via one client) via a single provider-agnostic service; OpenAI (`tier="high"`, optional, currently unconfigured) |
| Speech-to-text | Groq (Whisper-large-v3-turbo, OpenAI-compatible endpoint) — same Groq key as the fast LLM tier |
| Messaging | **Green API** (unofficial WhatsApp Business API — live, connected), Twilio (legacy voice path, idle), Resend (email) |
| File storage | Cloudinary |
| Background/cache | **Redis — now used** (rate limiting, patient-portal OTP store, booking drafts, landing-chat cache); **fails open** if unreachable. No job queue (Celery) runs yet |

### 2.2 Backend layout

Every domain — real clinic-ops and AI-agent alike — follows the same
three-layer convention:

```
backend/src/
├── router/<domain>/<domain>_router.py        HTTP routes + auth dependency
├── controller/<domain>/<domain>_controllers.py  request -> service call
├── services/<domain>/<domain>_services.py     actual logic, integrations
├── router/agents/__init__.py                  registers every router -> /api/v1/...
├── models/                                    SQLAlchemy models
├── schemas/                                   Pydantic request/response contracts
└── server/                                    middleware, Clerk auth chain, exceptions
```

Every practice-scoped query filters by `practice_id` resolved **server-side**
from the authenticated user (`get_current_practice_user`) — never trusted
from the client. This is the single most important invariant in the system
and is what the Week 4 tenant-isolation tests exist to prove holds under
adversarial input, not just under normal use.

### 2.3 Frontend layout

```
frontend/src/
├── app/
│   ├── auth/         Clerk sign-in/sign-up, doctor self-apply, staff invite
│   ├── portal/        the Patient Portal (own auth system, see §4.4)
│   ├── onboarding/     pricing -> Stripe checkout -> claim -> setup wizard
│   └── dashboard/      Owner/Doctor/Receptionist app, one folder per domain,
│                        role- and permission-gated via layout/Sidebar.tsx
├── components/, pages/, data/agents/   public marketing site + AI catalog
└── api/                 client.ts (fetch wrapper) + entities.ts/practice.ts
```

---

## 3. Data model

### 3.1 Already real (built before this month)

| Model | Purpose |
|---|---|
| `Practice`, `User` (role: owner/doctor/receptionist/staff) | Tenancy + auth identity |
| `Doctor`, `PendingDoctorRequest` | Roster + self-apply/approval flow |
| `Patient` | CRM core — contact info, `lifecycle_stage`, consent flag |
| `Appointment` | Booking lifecycle incl. `checked_in_at` |
| `ConsultationNote` (SOAP), `TreatmentPlan`/`TreatmentPlanItem`, `Procedure` | Clinical documentation |
| `PatientPhoto`, `ConsentDocument` | Photos + typed-name e-consent |
| `Invoice`/`InvoiceLineItem`, `Expense` | Billing + finance |
| `InventoryItem`/`InventoryBatch` | Stock, FEFO consumption |
| `StaffMessage` | Owner↔staff internal messaging |
| `AgentLog`, `AgentConfig`, `AgentCosting` | AI action logging, per-practice agent config, static cost catalog |
| `Conversation`/`Message`, `ReviewRequest` | Inbound channel activity, review requests |

### 3.2 New this month

| Model | Week | Purpose |
|---|---|---|
| `DoctorProcedure` | 1 | Real Doctor↔Procedure link (fee per doctor per procedure) — replaces free-text `capabilities` tags |
| `DoctorAvailability` | 1 | One-off schedule overrides beyond `Doctor.working_hours` |
| `ConsentTemplate` | 2 | Versioned consent text; `ConsentDocument` snapshots `template_id`+`template_version` at signing so edits never retroactively change what was signed |
| `Surgery` | 2 | Real surgery record: patient/procedure/surgeon/assistant/anesthesia/date/pre-op checklist/implants/operative note — **not** a multi-room OR-conflict scheduler (see plan's "explicitly out of reach") |
| `Supplier`, `PurchaseOrder`/`PurchaseOrderItem` | 3 | Inventory procurement |
| `Plan` (seeded: Practice/Enterprise), practice `subscription_plan` + server-side gating | — | Simplify pricing: flat $999 Practice (all categories) + Enterprise custom; Solo retired but enum value kept & normalized; plans admin-editable (`/admin/plans`) |
| `AdminAccount`/admin JWT | — | Platform staff auth, separate from Clerk — username/password login → scoped admin token |
| `Notification` | 3 | In-app notification store (SMS/WhatsApp/Email already have their own real send paths — this is the 4th channel) |
| `AuditLog` | 4 | WHO/WHAT/WHEN/FROM-WHERE on sensitive actions — separate from `AgentLog`, which is AI-action-specific |

### 3.3 Extended existing models

- `Patient`: `date_of_birth`, `gender`, `emergency_contact_name`/`_phone`,
  `allergies`, `medical_history`/`surgical_history`, `current_medications`,
  `smoking_status`, `previous_cosmetic_procedures`, `referral_source`,
  `preferred_language`, `communication_preferences`, `insurance_provider`/
  `_number`, plus **`portal_id`** and **`portal_pin_hash`** (§4.4).
- `Doctor`: `qualifications`, `specializations`, `working_hours`,
  `commission_percent`, `signature_url`.
- `PatientPhoto`: `stage` (before/day7/day14/1mo/3mo/6mo/1yr/other),
  `body_area`, `procedure_id`, `is_marketing_approved` (independent of
  clinical visibility — a deliberate separation per the product owner's
  explicit instruction that marketing consent and clinical-record consent
  must never be the same flag).
- `RecoveryJournal`: made real (was schema-only) — tied to a `Surgery`,
  checkpoint-based (Day 1/3/7/14/1mo).

---

## 4. Auth model, by role

### 4.1 Owner / Doctor / Receptionist — Clerk

Standard Clerk-issued bearer token. `get_current_practice_user` resolves it
to a real `User` row; `require_role(...)` gates endpoints. Doctor and
Receptionist additionally carry a granular JSON permission list
(`doctor_permissions.py`/`receptionist_permissions.py`) checked both in the
Sidebar (UI visibility) and — this month, Week 4 — at the endpoint level for
the highest-risk actions (previously UI-only, a known gap being closed).

### 4.2 Doctor self-apply

Shareable practice signup link → Clerk sign-up → `PendingDoctorRequest` →
Owner review/approve → real `Doctor` row + activated `User`. Unchanged this
month.

### 4.3 Staff invite

Owner invites via email (Clerk's invitation API) → accept → real `User` at
`role=receptionist`. Unchanged this month.

### 4.4 Patient — real ID + PIN (new this month, replaces the token scheme)

**Before this month**: `Patient.portal_token`, a plaintext, unrevoked-by-
default, un-rate-limited `secrets.token_urlsafe(32)` in a URL. Explicitly
documented in the code itself as demo-only.

**This month**: every patient gets a human-readable `portal_id` (e.g.
`AP-2026-00042`, generated at patient creation) and a `portal_pin_hash`
(bcrypt, never stored plaintext). `POST /patient-portal/login` takes
`portal_id` + PIN, returns a short-lived JWT scoped to that one patient —
deliberately not Clerk, since Clerk's pricing model is staff/MAU-oriented
and a clinic's patients aren't staff. Rate-limited (new capability, see §7)
against both wrong-PIN brute-forcing and ID enumeration. The PIN is handed
to the patient by front-desk staff at first real booking/check-in (default),
with self-registration on first portal visit as a practice-level option.

### 4.5 Platform admin — separate from Clerk (new)

Platform staff (the company running Aiaceone, not clinic staff) authenticate at
`/admin` with a username + password from `.env` (`ADMIN_USERNAME`/`ADMIN_PASSWORD`),
earning a short-lived scoped JWT. This is the **only** surface that sees across
practices: practice CRUD, subscription edits, plans editor, org-request approval,
user management, sales leads, and the platform Super Agent. Everything else in the
system remains strictly `practice_id`-scoped.

---

## 5. API surface — new this month (by domain)

| Domain | New/changed endpoints |
|---|---|
| Doctors | `GET/POST/PATCH /doctors/{id}/procedures`, `GET/POST /doctors/{id}/availability` |
| Front Desk | Extended `PATCH /appointments/{id}/status` (full Arrival→Checkout chain), walk-in booking, no-show marking, waitlist |
| Patient Portal | `POST /patient-portal/login` (new), existing book/appointments/photos/consent/invoices endpoints kept, `GET /patient-portal/me/doctor`, `GET /patient-portal/me/treatment-plan` (new — currently never surfaced to patients) |
| Consent | `GET/POST /consent-templates`, existing sign/void endpoints now snapshot template version |
| Surgery | `POST/GET/PATCH /surgeries`, `POST /surgeries/{id}/complete` |
| Inventory | `POST/GET /suppliers`, `POST/GET /purchase-orders`, `POST /inventory/items/{id}/wastage` |
| Notifications | `GET /notifications`, `PATCH /notifications/{id}/read` |
| Command Center | 4 new real query handlers: revenue-over-time, most-profitable-procedure, lead-conversion-rate, no-show-rate |
| AI workflows | `POST /ai/lead-qualification`, `POST /ai/patient-intake`, `POST /ai/consultation-assistant`, `POST /ai/transcribe` (Groq STT) |
| Landing chat (Aria) | `POST /api/v1/landing-chat/messages` — Groq-fast answers, real booking → patient lead (source "Landing Chat"), Redis-backed per-IP rate limiting/cache |
| Platform admin | `POST /admin/auth/login`, `GET /admin/me`, `GET/POST /admin/practices`, `PATCH /admin/practices/{id}`, `PATCH /admin/practices/{id}/subscription`, `GET/POST/PATCH /admin/plans`, `GET/PATCH /admin/users`, org-request approve/reject, `GET /admin/sales-leads`, `/admin/super-agent/*` |
| Audit | Internal only (middleware-level), no new public endpoints |

---

## 6. AI layer

### 6.1 The workforce: 9 real agents, 4 categories

The AI layer is now **9 consolidated, real agents** (replacing the earlier
"31 stubs, 5 real" catalog — every agent has a working backend endpoint that
answers with real data, logged via `AgentLogService`):

| Category | Agents |
|---|---|
| Front Desk & Intake | `receptionist` (Aria — marketing-site chat/triage → real booking → lead), `appointment_reminder` |
| Consultation & Screening | `patient_intake`, `lead_qualification`, `consultation_assistant` |
| Business & Operations | `main_agent` (Command Center, 4 handlers), `finance_agent` (real revenue/expense queries) |
| Post-Surgery Care | `post_op_recovery` (reads the real RecoveryJournal), `marketing_retention` |

Plus two platform-level agents:
- **Aria** — the marketing site chat. Fast (Groq-first `chat_fast`, capped
  `max_tokens`), short answers, converts a booking conversation into a real lead.
- **Super Agent** — staff-only, `/super-admin/super-agent`; one assistant across
  every practice's data (practices, plans, sales leads, conversations, sessions).

**Two hard rules on every LLM call:**
1. **Server-side plan gating** — the LLM service checks the practice's plan tier
   before answering (not just UI hiding). Practice ($999 flat, all categories)
   vs Enterprise (custom); Solo retired.
2. **Latency discipline** — interactive call sites cap `max_tokens` (Aria ~350,
   agents 400) and Aria's reply path uses `chat_fast` (Groq-first) so the widget
   feels instant.

### 6.2 Pattern
A thin service wrapping a real integration, logged via `AgentLogService`. Aria
double-send / stale-prompt issues and admin-login hangs (Redis timeouts) were
found and fixed by live browser runs this session — see the shared-services
notes (rate limiter socket timeouts + cached fail-open).

### 6.3 Explicit AI boundary (stated once, applies everywhere)

For anything touching patient health status (post-op check-ins,
symptom reports): **AI collects → classifies → alerts a human clinician.
It never independently diagnoses or decides treatment.** This is a hard
line, not a suggestion — consistent with why several "Consultation &
Screening"-category agents were deliberately left unbuilt in the prior
phase pending compliance review.

---

## 7. Credentials — free-tier-first strategy

| Service | Status today | This month | Cost |
|---|---|---|---|
| Clerk | Real, working | — | Free tier (sufficient for pilot volume) |
| Mistral | Real, working | Fallback/general tier | Free tier |
| **Groq** (fast LLM tier) | Real, working | Powers Aria + JSON extraction | Free tier |
| Resend | Real, working | — | Free tier |
| Cloudinary | Real, working | — | Free |
| **Green API** (WhatsApp) | Real, working | One real number connected | Free/cheap tiers, message-volume caps |
| **Redis** | Configured (WSL), optional at runtime | Now integrated — rate limiting, OTP, booking drafts, landing-chat cache; fails open if down | Free |
| Twilio | Placeholder | Legacy voice path idle | Not free — no meaningful free tier for a real number |
| WhatsApp Business API (Meta) | Not used | Not used — Green API chosen over the verification-gated Meta path | Free API, but requires Meta's external business-verification process |
| Stripe | Placeholder | Real checkout sessions are created server-side (end-to-end works locally); live charge needs real keys | Free to integrate, only charges per real transaction |
| OpenAI | Placeholder | Not needed — Groq covers the fast path | Optional — nothing live requires it |

See `CREDENTIALS.md` (added Week 4) for the actionable signup checklist.

---

## 8. Security posture this month

Focused on the highest-risk surfaces (per product owner's explicit
priority), not full coverage:

- **Tenant isolation**: the existing `practice_id` server-side-resolution
  pattern gets adversarial tests (Clinic A can never read/guess/download
  Clinic B's data via API) — proving an existing invariant, not building a
  new one.
- **New attack surface = new tests**: the Patient Portal's ID+PIN login is
  this month's biggest new auth surface, so it gets rate-limiting, account
  lockout, and dedicated tests as a first-class citizen, not an
  afterthought.
- **Audit logging**: WHO/WHAT/WHEN/FROM-WHERE on sensitive reads/writes
  (patient record view, consent change, photo download, appointment
  change), via a router-dependency, not hand-added per endpoint.
- **`CLERK_WEBHOOK_SECRET`**: moves from placeholder to real — the one item
  here that's a dashboard step, not code, called out so it doesn't get
  silently skipped.
- **Explicitly not attempted this month**: real HIPAA/regulatory
  certification (a legal/business process), a live production deployment,
  100% test coverage. See the plan's "Explicitly out of reach" section for
  the full reasoning — stated up front rather than discovered late.

---

## 9. 30-day roadmap

Full detail lives in the approved plan
(`C:\Users\muhammad sadoon\.claude\plans\woolly-meandering-harbor.md`) —
summarized here for a reader who only has this file:

- **Week 1** — Doctor model enrichment (+today-at-a-glance dashboard),
  Receptionist front-desk status machine, real Patient Portal auth, a
  repeatable 2-doctor+1-receptionist demo seed script. ✅ done
- **Week 2** — Patient profile depth, consent versioning, before/after
  photo timeline, the Surgery module. ✅ done
- **Week 3** — Post-op recovery journey (✅ `RecoveryJournal` real), a
  centralized notification engine (🟡 per-channel send paths real,
  unified interface still roadmap), inventory depth (🟡 models added), 4
  real Owner Analytics handlers (✅ in Command Center + Finance Agent).
- **Week 4** — the AI workforce rebuild (✅ 9 agents + Aria + Super Agent,
  server-side gating), Groq fast tier (✅), admin panel (✅), Redis
  integration (✅). Still open: real audit logging, the focused test suite
  + CI pipeline, Groq STT wiring for call transcription.
- **Won/ongoing since**: plan simplification (Practice $999 / Enterprise;
  Solo retired), `chat_fast` latency work, Redis-fail-open hardening, and
  the docs you're reading.

Every week ends with the same verification discipline already proven
throughout this project: a reviewed Alembic migration, a real-DB smoke
script per new service, clean `tsc`/`eslint`, and a live Playwright pass
against the seeded demo practice — never marked done from code review
alone.
