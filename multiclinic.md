# Multi-Clinic (Multi-Tenant) System — Architecture & Product Spec

> **Purpose:** This document is the single source of truth for how Aiaceone works as a
> **multi-clinic, multi-tenant system**. It documents (a) what is **already built and
> verified in this repo**, (b) what is **missing**, and (c) the **exact product flow** a
> new customer must walk through — from landing on the Pricing page, to requesting a free
> organization, to Super-Admin approval, to a fully-populated (mock-data) Owner dashboard,
> to connecting WhatsApp / Facebook / Instagram / Twilio and the AI Receptionist.
>
> **Everything written here was verified against the actual code** — file paths and line
> numbers are real. Nothing in this document is aspirational guessing.

---

## Table of Contents

1. [The Core Idea — Why "Request Organization" instead of "Buy a Plan"](#1-the-core-idea)
2. [Verified System Map — What Already Exists](#2-verified-system-map)
3. [Confirmed Gaps — What Is Missing](#3-confirmed-gaps)
4. [The End-to-End User Flow](#4-the-end-to-end-user-flow)
5. [Tenant Isolation — The Non-Negotiable Rule](#5-tenant-isolation)
6. [The Owner Dashboard — Full Feature Tour](#6-the-owner-dashboard)
7. [Adding Doctors / Receptionists / Patients](#7-adding-doctors--receptionists--patients)
8. [Mock Data System (Demo Mode)](#8-mock-data-system)
9. [Integration Guides — Step by Step](#9-integration-guides)
10. [AI Receptionist — Step-by-Step Setup](#10-ai-receptionist)
11. [Agent Settings — "Add Your Own API Key"](#11-agent-settings)
12. [Support / Ticket System](#12-support--ticket-system)
13. [Super-Admin Panel — Full Control](#13-super-admin-panel)
14. [Database Reference](#14-database-reference)
15. [API Endpoint Reference](#15-api-endpoint-reference)
16. [Implementation Roadmap](#16-implementation-roadmap)

---

## 1. The Core Idea

Aiaceone is **not** sold as a "pick a plan and pay" product first. It is sold as
**"request access to the platform, and we switch you on."**

This exists because the target buyer is a **clinic owner or doctor** who does not know what
an AI receptionist costs or what a good plan looks like. Forcing a Stripe payment *before*
they have ever seen the product kills the conversion. Instead:

| Step | Who acts | What happens |
|------|----------|--------------|
| 1 | Prospect | Lands on Pricing page, reads plan detail |
| 2 | Prospect | Clicks **"Request Access"** instead of "Buy" |
| 3 | Prospect | Signs up with Clerk → redirected to `/org/apply` |
| 4 | Prospect | Submits practice name → a `PendingSignup` row is filed as `PENDING` |
| 5 | **Super-Admin** | Sees the request at `/super-admin/org-requests` |
| 6 | **Super-Admin** | Clicks **Approve** → Practice + Owner User + Subscription + 9 AgentConfigs are provisioned |
| 7 | Owner | Lands on Owner dashboard, **fully unlocked**, seeded with mock data |
| 8 | Owner | Explores everything, configures integrations, invites their real doctors |
| 9 | Owner | When satisfied, clicks **Upgrade** → real Stripe charge |

**The money is not made at step 3. It is made at step 9**, after the owner has already
proved to himself that the product works.

> **Direct answer to "kya banda abhi dashboard par excess kar pa raha hai pricing ke baad?"**
> **Nahi.** Right now, clicking anything on the Pricing section drops you into the booking /
> checkout funnel. There is **no "Request Access" button anywhere on the Pricing page** —
> `/org/apply` exists and is fully functional, but **nothing links to it**. This is gap
> **G-1** below, and it is the single highest-impact fix in this document.

---

## 2. Verified System Map

Everything in this section was read directly out of the repository and **already works**.

### 2.1 Data model — the tenant is `Practice`

The multi-tenancy primitive is **not** a new `Organization` table. A clinic **is** a
`Practice` row, and every tenant-scoped table carries a `practice_id`.

`backend/src/models/practice.py` defines the lifecycle gate:

```python
class PracticeStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"   # filed, awaiting Super-Admin
    ACTIVE           = "active"              # usable
    SUSPENDED        = "suspended"           # Super-Admin's soft "delete"
```

`Practice` cascades `delete-orphan` to **20** child relationships
(`backend/src/models/practice.py:39-59`) — users, patients, doctors, appointments,
agent_configs, subscriptions, invoices, inventory, audit_logs, and more. Suspending does
**not** delete; it flips status only, so patient data is never destroyed by a mistaken click.

### 2.2 Roles — already correctly scoped

`backend/src/models/user.py:18-22` is worth reading in full, because the comment there
explains a subtle decision:

```python
class UserRole(str, enum.Enum):
    OWNER       = "owner"
    DOCTOR      = "doctor"
    RECEPTIONIST = "receptionist"
    STAFF       = "staff"   # honest fallback: Clerk's user.created webhook
                          # carries no signal about the real role
```

`UserRole` only ever means something **within** `practice_id`. Platform-level authority is a
**separate boolean**, `User.is_platform_admin` (`user.py:60`), which self-heals to `True` on
login for any email in `Settings.platform_admin_emails`
(`backend/src/server/dependencies.py:get_current_practice_user`). Keeping the two
orthogonal is what makes "Clinic A's owner cannot touch Clinic B" provable rather than
hopeful.

> **Note:** `PATIENT` is deliberately **not** a `UserRole`. Patients are `Patient` rows, not
> `User` rows. A patient login is a deliberately separate, later problem.

### 2.3 The org-request lifecycle — already fully implemented

**The dual-purpose row.** `backend/src/models/pending_signup.py` reuses one table for
*both* the paid Stripe checkout and the free org request. Its module docstring
(`pending_signup.py:11-28`) spells out the discriminator:

> *"The two flows are told apart by `stripe_session_id IS NULL` (org request) vs NOT NULL
> (paid checkout) rather than a new table, since every other field already means the exact
> same thing in both."*

```python
class OrgRequestStatus(str, enum.Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
```

Org-request-only columns (`pending_signup.py:59-64`): `clerk_id`, `org_name`,
`request_status`, `reviewed_at`, `rejected_reason`.

**Migration:** `backend/alembic/versions/6becd117ec3f_practice_status_and_org_request_fields.py`
adds all of the above, and — importantly — adds `practices.status` with
`server_default='ACTIVE'` so **no existing paying customer is locked out** by the migration
(`6becd117ec3f...py:43-49`). It also makes `plan_tier` nullable, because the free
org-request path never sets one (`6becd117ec3f...py:37-40`).

**Webhook entry.** `backend/src/router/v1/webhooks/webhook_router.py`'s `user.created`
handler reads Clerk's `unsafeMetadata.invite_type == "org_request"` and files a
`PendingSignup` instead of granting practice access. The frontend sets that flag at
`frontend/src/app/auth/SignUpPage.tsx:38`.

**Service:** `backend/src/services/practice/org_request_service.py`
- `get_or_create_for_webhook(db, clerk_id, email)` — line 28
- `submit(db, clerk_id, email, org_name)` — line 44
- `get_my_request(db, clerk_id)` — line 60

**Super-Admin decisions:** `backend/src/services/admin/admin_services.py`
- `list_pending_org_requests` — line 274
- `approve_org_request` — line 289 → delegates to `provision_from_org_request`
- `reject_org_request` — line 300
- `suspend_practice` / `reactivate_practice` — lines 319 / 328

**Provisioning on approve:** `backend/src/services/checkout/provisioning_service.py:59`
`provision_from_org_request` creates, in one transaction:
1. the `Practice` row (`_get_or_create_practice_for_org_request`, line 91)
2. the owner `User` row (`_get_or_create_owner_user`, line 115)
3. a trial `Subscription` (`_get_or_create_subscription`, line 134)
4. the **9 `AgentConfig` rows** (`_seed_agent_configs`, line 169)

So by the time the owner sees a dashboard, all nine AI agents already exist and are
correctly plan-gated. The Super-Admin can also pick the `plan_tier` at approval time
(`approve_org_request(..., plan_tier=...)`).

### 2.4 Frontend routes — already present

| Route | File | Status |
|-------|------|--------|
| `/org/apply` | `app/auth/OrgApplyPage.tsx` | ✅ Works — polls every 8s, shows pending/approved/rejected |
| `/super-admin/org-requests` | `app/admin/org-requests/OrgRequestsListPage.tsx` | ✅ Works |
| `/super-admin/clinics` | `app/admin/clinics/ClinicsListPage.tsx` | ✅ Works |
| `/super-admin/clinics/:id` | `app/admin/clinics/ClinicDetailPage.tsx` | ✅ Works |
| `/onboarding/setup` | `app/onboarding/SetupWizardPage.tsx` | ✅ 4-step wizard |
| `/dashboard/*` | `app/dashboard/DashboardRouter.tsx` | ✅ Role-guarded |
| `/super-admin/*` | `app/admin/AdminRouter.tsx` | ✅ Guarded by `AdminRequireAuth.tsx` |

Route constants live in `frontend/src/app/admin/constants/routes.ts`. `App.tsx:84` mounts
the admin area at `/super-admin/*` with `/admin/*` redirecting for backwards compatibility —
deliberately named so platform-level access is never confused with a clinic's own dashboard.

`OrgApplyPage.tsx` is well-built: on approval it deep-links to `/onboarding/setup`
(`OrgApplyPage.tsx:163`), and it self-heals if the Clerk webhook has not yet reached the
backend by letting the user create the row on first submit (`OrgApplyPage.tsx:76-82`).

### 2.5 Onboarding wizard

`app/onboarding/SetupWizardPage.tsx` + `app/onboarding/steps/`:
`PracticeDetailsStep` → `FirstDoctorStep` → `ChannelsStep` → `CompleteStep`.

### 2.6 Integrations — two channels are real

`app/dashboard/settings/IntegrationsPage.tsx` (292 lines) has working, step-by-step cards:

- **`GreenApiCard`** — real end-to-end. Stores `Practice.settings["green_api"]`, which
  `WhatsAppGreenAPI` already reads. Includes the QR-scan instruction
  (`IntegrationsPage.tsx:146`).
- **`MetaCard`** — real OAuth, connects the Facebook Page **and** its linked Instagram
  Business account in one step (`IntegrationsPage.tsx:277`). Callback handled by
  `MetaCallbackPage.tsx`.

The file's own header comment (`IntegrationsPage.tsx:17-23`) is honest about the state:
Meta's OAuth is gated platform-wide on `MetaService.is_configured()` (a registered Facebook
App), and until Aiaceone's team registers one, the card shows *"not available yet"* rather
than a dead button.

### 2.7 Backend channel services — all four exist

| Channel | Service |
|---------|---------|
| WhatsApp (GreenAPI) | `backend/src/services/channels/whatsapp_green_api.py` |
| WhatsApp (business logic) | `backend/src/services/whatsapp/whatsapp_service.py` |
| Meta / Facebook | `backend/src/services/meta_service.py` → `services/channels/meta_service.py` |
| Instagram | `backend/src/services/instagram/instagram_service.py` |
| Twilio (voice + SMS) | `backend/src/services/twilio/twilio_service.py` |

### 2.8 AI Receptionist

- Config schema: `backend/src/schemas/ai_receptionist.py`
- Router: `backend/src/router/ai_receptionist/ai_receptionist_router.py`
- Controller: `backend/src/controller/ai_receptionist/ai_receptionist_controllers.py`
- Human availability: `backend/src/services/ai_receptionist/human_availability_service.py`
- Frontend workspace: `app/dashboard/receptionist/` (incl. `LiveTranscript.tsx`,
  `SystemPrompt.tsx`, `VoiceEngine.tsx`, `HumanAvailabilityCard.tsx`)
- Agent settings: `app/dashboard/settings/AgentSettingsPage.tsx` + `useAgentSettings.ts`
- Agent costing: `services/agent_costing/` + `app/dashboard/settings/agentCosting.ts`

### 2.9 Isolation is already tested

`backend/tests/test_tenant_isolation.py` exists — cross-practice access is a **regression
test**, not just a convention. This is the single most valuable asset in the repo for a
multi-tenant product; it must never be deleted or weakened.

---

## 3. Confirmed Gaps

These were verified as **genuinely absent or incomplete**. Each has an ID so it can be
tracked.

### G-1 — Pricing page has no "Request Access" button 🔴 **CRITICAL**

**The single reason a prospect "goes to pricing and gets redirected to booking."**

- `frontend/src/components/sections/Pricing.tsx` and `CheckoutModal.tsx` contain **zero**
  references to `/org/apply`, "request", or "contact us".
- A repo-wide grep for `org/apply` returns only the route declaration in `App.tsx:73` and
  the internal redirect from `OrgApplyPage.tsx:163`.
- **Consequence:** `/org/apply` is **orphaned**. A fully-built approval pipeline with a
  Super-Admin UI has no front door. Every prospect is funnelled into Stripe, which is
  exactly the conversion problem the org-request flow was designed to solve.

**Fix:** add a secondary CTA under the pricing cards — *"Not ready to pay? Request free
access"* — linking to `/sign-up`. The `unsafeMetadata` flag at `SignUpPage.tsx:38` already
routes plain signups into the request pipeline, so **no backend change is needed.**

### G-2 — No mock/sample data per organization 🔴 **HIGH**

`provision_from_org_request` seeds the `Practice`, `User`, `Subscription` and 9
`AgentConfig` rows — **but zero patients, appointments, conversations, or transcripts.**

An approved owner lands on **empty** dashboards: no patients, no appointments, no message
history. There is nothing to explore, so the "let me try it before I pay" promise is not
actually delivered.

Mock data exists only as **global dev scripts** that require manual, out-of-band execution
against a known database — unusable by a real prospect:
- `backend/scripts/seed_demo_practice.py`
- `backend/scripts/seed_data.py`
- `backend/scripts/seed_admin_demo.py`
- `backend/scripts/seed_leads.py`

**Fix:** a `sample_data_service.py` that seeds **per-practice**, idempotently, flagged
`is_sample = True` so it can be selectively deleted. See [§8](#8-mock-data-system).

### G-3 — No support / ticket system 🟡 **MEDIUM**

A repo-wide search for `*support*` returns **nothing**. There is no way for a clinic owner
to ask for help, and no way for Aiaceone to answer. For a product whose entire pitch is
"try it free, we'll switch you on," human hand-holding *is* the product.

**Fix:** see [§12](#12-support--ticket-system).

### G-4 — Twilio and Instagram have no frontend guide 🟡 **MEDIUM**

`IntegrationsPage.tsx` renders exactly two cards — `GreenApiCard` and `MetaCard`
(`IntegrationsPage.tsx:30-33`). The Twilio service (`services/twilio/twilio_service.py`) and
the Instagram service (`services/instagram/instagram_service.py`) both exist on the backend
but have **no owner-facing setup UI at all**. Instagram is only reachable as a side-effect
of the Meta OAuth. A clinic owner who wants a voice AI receptionist has literally nowhere to
start.

**Fix:** see [§9](#9-integration-guides).

### G-5 — No "per-organization billing page" distinction 🟢 **LOW**

`app/dashboard/billing/PlanBillingPage.tsx` exists. A trial org that upgrades must be able
to see the trial-vs-paid state and trigger upgrade. Worth confirming the upgrade CTA is
reachable from the Owner dashboard for a `trial` subscription.

---

## 4. The End-to-End User Flow

### 4.1 The free request path (the one that matters)

```
PROSPECT LANDS
   │
   ▼
/pricing  ── reads plan cards, prices, feature lists
   │
   ├─► "Get started" ──► /pricing/pay (Stripe's embedded form) ──► /onboarding/claim
   │                                                            └─► ClaimPlanPage
   │                                                                └─► ProvisioningService
   │                                                                    .provision_from_pending_signup
   │
   └─► "Request free access"  ★ ADD THIS (G-1) ★
         │
         ▼
      /sign-up   (Clerk; SignUpPage.tsx:38 sets unsafeMetadata
                  { invite_type: "org_request" })
         │
         │  Clerk fires user.created webhook
         ▼
      webhook_router.py  ──reads invite_type──►  org_request_service
         │                                            .get_or_create_for_webhook
         │                                                  │
         │                                    INSERT pending_signups
         │                                    request_status = PENDING
         ▼
      RoleHome / RequirePractice bounces to:
      /org/apply  (OrgApplyPage.tsx)
         │
         ├─ no row yet?  ──► OrgNameForm  ──► POST submit()  (self-healing)
         │
         └─ row exists?  ──► RequestCard ── polls every 8s
                                │
                                ├─ "pending"  → "Reviewing your request…"
                                ├─ "approved" → "You're approved!" → /onboarding/setup
                                └─ "rejected" → shows rejected_reason
```

### 4.2 The Super-Admin side, concurrently

```
SUPER-ADMIN SIGNS IN  (/super-admin/sign-in)
   │
   ▼
/super-admin/org-requests        (OrgRequestsListPage)
   │  GET pending org requests   (admin_services.list_pending_org_requests)
   │  shows: email · org_name · clerk_id · created_at
   │
   ├─► APPROVE  ──► approve_org_request(request_id, plan_tier?)
   │      └─► ProvisioningService.provision_from_org_request
   │             ├─ Practice           (status = ACTIVE)
   │             ├─ User               (role = OWNER)
   │             ├─ Subscription       (TRIAL)
   │             └─ 9 × AgentConfig
   │      └─► request_status = APPROVED, reviewed_at = now
   │      └─► OWNER'S POLL PICKS IT UP WITHIN 8 SECONDS
   │
   └─► REJECT  ──► reject_org_request(request_id, reason?)
          └─► request_status = REJECTED, rejected_reason = reason
          └─► OWNER SEES THE REASON ON /org/apply
```

### 4.3 The paid path (unchanged, still fully live)

```
/pricing → /pricing/pay → Stripe Checkout Session (embedded form)
   → webhook checkout.session.completed → PendingSignup.completed_at
   → user creates Clerk account → /onboarding/claim
   → POST /practice/claim → ProvisioningService.provision_from_pending_signup
   → /onboarding/setup
```

The `pending_signups` module docstring (`pending_signup.py:11-17`) documents an important
constraint: the Stripe webhook **does not** create a `Subscription`/`Practice`, because
`Subscription.practice_id` is `NOT NULL` and no `Practice` exists at webhook time (Stripe
fires server-side, before the customer has a Clerk account). **Provisioning happens at claim
time.**

### 4.4 Post-approval — the Owner's first 10 minutes

```
/onboarding/setup
   │
   ├─ Step 1  PracticeDetailsStep   — name, phone, address, timezone
   ├─ Step 2  FirstDoctorStep        — invite the first real doctor via link
   ├─ Step 3  ChannelsStep           — connect WhatsApp / Meta
   └─ Step 4  CompleteStep           — first agent config, system prompt
   │
   ▼
/dashboard  ── Owner lands here
   │
   ★ Should land on EMPTY dashboards today. (G-2)
   ★ Should land on POPULATED mock dashboards. (G-2)
```

---

## 5. Tenant Isolation

**The rule:** *Clinic A's data never appears in Clinic B's. Ever. Not in a list, not in a
count, not in a search result, not in an error message.*

### 5.1 How it is enforced today

1. **Every tenant-scoped table carries `practice_id`.** See `Practice`'s 20 cascading
   relationships (`practice.py:39-59`).
2. **The session resolves to exactly one practice.** `server/dependencies.py`:
   `get_current_practice_user` (which also self-heals `is_platform_admin`) and
   `get_current_practice_context` (the actual enforcement point — per the comment at
   `admin_services.py:314-317`, this is what locks every practice-scoped endpoint the moment
   `Practice.status` flips to `SUSPENDED`).
3. **It is regression-tested.** `backend/tests/test_tenant_isolation.py`.

### 5.2 The two axes of privilege — keep them orthogonal

| Axis | Field | Scope | Who sets it |
|------|-------|-------|-------------|
| Within a clinic | `User.role` | one practice | invite / apply flow |
| Across the platform | `User.is_platform_admin` | whole platform | `Settings.platform_admin_emails` |

A clinic owner has `role=OWNER` and `is_platform_admin=False`. They are the **owner of their
own `practice_id` and nothing else.** Only `is_platform_admin=True` reaches across tenants
— and every such action is auditable via `AuditLog` (`models/audit_log.py`, exposed at
`router/audit_logs/`).

### 5.3 Checklist for any new endpoint

- [ ] Does the query filter by the session's `practice_id`, not one passed in the request?
- [ ] Can a caller pass another practice's `id` and get a 404 (not a 403, which leaks
      existence)?
- [ ] Does any aggregate/count leak cross-tenant totals?
- [ ] Are webhook routes (WhatsApp/Meta/Twilio) scoped by practice, or could practice A's
      inbound message be written into practice B's data?
- [ ] Does `tests/test_tenant_isolation.py` cover the new route?

---

## 6. The Owner Dashboard

`app/dashboard/DashboardLayout.tsx` + `DashboardRouter.tsx`, role-gated per sub-route.

| Area | Path | Purpose |
|------|------|---------|
| Overview | `/dashboard` | KPIs: patients, appointments, revenue |
| Patients | `/dashboard/patients` | List, detail, archive, assign doctor |
| Doctors | `/dashboard/doctors` | Roster, forms, detail, **signup-link generation** |
| Front desk | `/dashboard/front-desk` | Booking, check-in, waitlist |
| Sessions | `/dashboard/sessions` | Appointment scheduling |
| Receptionist | `/dashboard/receptionist` | Live transcript, voice engine, system prompt |
| Clinical | `/dashboard/clinical` | Treatment plans, consent, procedures |
| Inventory | `/dashboard/inventory` | Stock, batches, purchase orders |
| Finance | `/dashboard/finance` | Revenue, expenses, refunds |
| Messages | `/dashboard/messages` | Omnichannel threads |
| Command center | `/dashboard/command-center` | Notifications, quick actions |
| Leads | `/dashboard/leads` | Funnel stages, qualification |
| Surgery | `/dashboard/surgery` | Case list, status machine |
| Staff | `/dashboard/staff` | Roster, scheduling, **permissions** |
| Billing | `/dashboard/billing` | Plan, invoices, upgrade |
| Settings | `/dashboard/settings/*` | **Integrations**, Agent settings, Consent, Marketing |

Guards: `RequireAuth.tsx`, `RequirePractice.tsx`, plus per-role guards inside
`DashboardRouter`.

---

## 7. Adding Doctors / Receptionists / Patients

### 7.1 Doctor — owner-initiated, via the Owner's own link

```
Owner → /dashboard/doctors → "Add Doctor"
   │  name · email · specialization · phone · room
   ▼
POST /doctors  (or generate a signup code — practice.ts exposes this)
   │
   ├─ creates a PendingDoctorRequest linked to practice_id  (models/pending_doctor_request.py)
   │
   ▼
Doctor opens /doctor/sign-up?code=…      (DoctorSignUpPage.tsx)
   │  creates Clerk identity → webhook
   ▼
Doctor lands on /doctor/apply             (DoctorApplyPage.tsx)
   │  Owner sees "1 pending" and approves
   ▼
Approved → doctor's role within THIS practice is DOCTOR.
           Zero visibility into any other practice.
```

Pending state: `DoctorApplyPendingPage.tsx`. Rejection path: `DoctorApplyRecovery.tsx`.
Doctor approvals: `services/doctor_applications/`.

### 7.2 Receptionist — same shape

`StaffSignUpPage.tsx` → `StaffApplyPage.tsx` → `StaffApplyPendingPage.tsx`, backed by
`PendingStaffRequest` (`models/pending_staff_request.py`) and `services/staff_applications/`.
Granular dashboard permissions are set by the Owner via `PATCH /staff/{id}/permissions`,
catalogued in `backend/src/data/receptionist_permissions.py` and mirrored in
`frontend/src/data/receptionistPermissions.ts`.

### 7.3 Patient

Patients are **not** `User` rows and have **no login** in this design
(`user.py:16-17`). The Owner creates them at `/dashboard/patients`; each is scoped by
`practice_id`. A separate patient-portal PIN flow already exists for read-only patient
access (`patient_portal_router`, `models/patient_portal_id_pin_auth`) — but that is opt-in
per practice and is **not** part of the "add your workforce" story.

---

## 8. Mock Data System

> **Status: DOES NOT EXIST. This is gap G-2 and it is the reason the free trial feels empty.**

### 8.1 Product requirement

> *"user ko mock data mily gaa jis wo delte bhe kar sakta hai har gahan sy"*

When a Super-Admin approves an org request, the new practice should immediately look like a
**working clinic**, so the owner can explore instead of staring at empty tables.

Requirements, in order of importance:

1. **Per-practice** — seeded into the approving practice's `practice_id`, never global.
2. **Idempotent** — re-running must not duplicate rows.
3. **Individually deletable** — "delete all mock data" *and* per-row delete.
4. **Flagged** — `is_sample = True` so real and sample data are never confused, and a
   filter can hide samples.
5. **Never counted as revenue.** This matters more than it looks — see §8.4.

### 8.2 What to seed

| Entity | Count | Content |
|--------|-------|---------|
| Patients | 12 | Names, phone, email, complaint, assigned doctor, intake fields |
| Appointments | 18 | Spread across next 14 days, mixed statuses (scheduled/completed/cancelled) |
| Conversations | 8 threads | WhatsApp-style threads across channels |
| Messages | ~40 | Alternating inbound/outbound, realistic pre/post-consult text |
| Leads | 6 | Across funnel stages (new → contacted → qualified → booked) |
| Agent logs | 12 | Sample AI receptionist calls with transcripts |
| Procedures | 5 | From `assets/knowledge_base/Aesthetic-Fee-Schedule-Benchmark-2026.pdf` |
| Inventory | 8 items | Realistic consumables with unit costs |
| Expenses | 6 | Rent, utilities, supplies, salaries |
| Treatment plans | 4 | Tied to seeded patients |

Reference material for realistic content already sits in
`backend/assets/knowledge_base/` — intake form, fee schedule, consent form, aftercare
handout, and a HIPAA compliance checklist. Seed from these so the demo looks credible.

### 8.3 Implementation shape

**New:** `backend/src/services/demo/sample_data_service.py`

```python
async def seed_sample_data(db: AsyncSession, practice: Practice) -> dict[str, int]
async def clear_sample_data(db: AsyncSession, practice_id: UUID) -> dict[str, int]
async def sample_data_counts(db: AsyncSession, practice_id: UUID) -> dict[str, int]
```

Every seeded row gets `is_sample=True` (new nullable boolean, default `False`, so every
existing row is real by construction — never a migration-time data change).

Wire the same way `OrgRequestsListPage` calls the admin API: add
`POST /api/demo/seed`, `DELETE /api/demo/sample-data`, `GET /api/demo/sample-data/counts`,
all scoped to the caller's `practice_id`, Owner-only.

**Auto-seed on approval:** call `seed_sample_data` at the end of
`ProvisioningService.provision_from_org_request` (`provisioning_service.py:59`), guarded by
a Settings flag so it can be turned off.

**UI:** a "Sample data" panel — in the Owner dashboard settings, with per-entity counts,
"Load sample data", and "Delete all sample data" behind a confirm dialog that spells out
exactly what will be removed. Also expose a per-row "delete" on every seeded row so the
owner can prune piecemeal.

### 8.4 The honesty requirement ⚠️

`admin_services.py:20-28` contains a comment that must be respected here:

> *"No real per-session usage telemetry exists yet... Every 'cost'/'revenue' figure this
> service produces is therefore an ESTIMATE, not a measurement."*

Therefore:
- Any sample patient / appointment **must not** appear in revenue, invoice, or AgentCosting
  figures.
- Sample rows must be visually distinguishable in the UI (badge, tint, or filter).
- The finance and analytics pages must exclude `is_sample=True` — otherwise a prospect
  comparing numbers sees fabricated revenue, which is both a legal and a reputational
  problem the moment this goes public.

---

## 9. Integration Guides

Each integration must show the owner **exactly what to click, in order**, including what
it costs and what account to create. Below is the content each guide card should render.

### 9.1 WhatsApp — Option A: GreenAPI (third-party, fastest)

**Why:** works in ~10 minutes, no Meta business verification, no app review.

1. Go to **green-api.com** → sign up.
2. Choose a plan (GreenAPI charges per conversation; free tier is limited).
3. **Create an instance** → you get an `idApi` and an `apiTokenInstance`.
4. In the GreenAPI dashboard, open **Settings → QR code**.
5. **Scan the QR code with the WhatsApp Business account you want the practice to use.**
6. Confirm the number is linked — status becomes `authorized`.
7. Back in Aiaceone → **Settings → Integrations → WhatsApp**:
   - Paste `Instance ID`
   - Paste `API Token`
   - **Connect**
8. Send yourself a test message. Done.

**Note for the UI:** the QR-scan step is already implemented at
`IntegrationsPage.tsx:146`.

### 9.2 WhatsApp — Option B: WhatsApp Business via Meta Cloud API

**Why:** no per-message middleman, official, required at scale.

1. Create a **Meta Business Account** at business.facebook.com.
2. Create a **Meta Developer App** → add the **WhatsApp** product.
3. In **WhatsApp → API Setup**, note the test `Phone number ID` and `Access Token`.
4. In **WhatsApp → Configuration**, add your **Webhook URL**:
   `https://<your-backend>/api/webhooks/whatsapp`
   and subscribe to `messages` + `message_status`.
5. Set the webhook **Verify Token** to the same value in Aiaceone's settings.
6. Add a **phone number** (production requires verification).
7. Create **message templates** — required for outbound, must be approved by Meta.
8. Enter `Phone number ID` + `Access Token` in **Settings → Integrations → WhatsApp (Meta)**.

**Costs to state honestly in the UI:** Meta charges per-message (per-conversation from
July 2025). The 24-hour customer-service window is free; outside it you pay per template
message. Show this — it changes the plan recommendation.

### 9.3 Facebook — Meta OAuth

1. Go to **developers.facebook.com** → **My Apps** → **Create App**.
2. Choose use case **"Other"** → Business type.
3. Add the **Messenger** product.
4. **Facebook Login → Settings**: add your app's redirect URI
   `https://<your-frontend>/dashboard/settings/meta/callback`.
5. In **App Review**, request `pages_show_list`, `pages_read_engagement`,
   `pages_manage_posts`, `business_management` — Messenger cannot go live without review.
6. **Webhook → Settings**: callback URL
   `https://<your-backend>/api/webhooks/meta`, verify token, subscribe to
   `messages`, `messaging_postbacks`.
7. In Aiaceone, connect with the OAuth button — it links your **Page and its linked
   Instagram Business account in one step** (`IntegrationsPage.tsx:277`).
8. To *disconnect*, remove the app from your Facebook profile's **Settings → Apps**.

### 9.4 Instagram

Instagram has **no standalone API connection** — it piggybacks entirely on Meta.

1. Have an **Instagram Business or Creator** account (a personal account must be converted
   first; the app must be linked to a Facebook Page).
2. Go to **Instagram → Settings → Account → Linked accounts** and link the Facebook Page.
3. Complete the OAuth in §9.3 — Instagram comes across with it.
4. Confirm in **Settings → Integrations** that the IG account shows connected.

**Costs:** Instagram messaging follows the same per-message Meta pricing as Messenger.

### 9.5 Calls & Voice — Twilio

Currently **backend-only, no UI** — gap G-4.

1. Go to **twilio.com** → sign up.
2. From the console, note the **Account SID** and **Auth Token**.
3. **Phone Numbers → Buy a number** (voice + SMS capable), or use your own number in porting.
4. Note the **Twilio Phone Number SID**.
5. In Aiaceone → **Settings → Integrations → Twilio**: enter Account SID, Auth Token, and
   the number SID.
6. For inbound calls: create a **TwiML App**, point its voice webhook at
   `https://<your-backend>/api/webhooks/twilio/voice`, and set
   **HTTP Method = POST**.
7. Test with a call to the number.

**Costs to state honestly:** Twilio bills **per minute** of inbound voice (regional rate),
plus a **per-message** fee for SMS. Voice is typically the most expensive channel — say so,
and steer owners toward it only once they understand the unit economics.

### 9.6 What to build (G-4)

Add to `IntegrationsPage.tsx` (currently renders only two cards at lines 30-33):

- `TwilioCard` — SID/token/number entry, test-call button, plus the guide above.
- Split the combined Meta card into `MetaCard` (Messenger) + `InstagramCard`, so the pricing
  story and the account prerequisites are explained separately.
- A **"Which should I choose?"** comparison strip at the top of the page: GreenAPI vs Meta
  Cloud for WhatsApp, and the cost/verification/prereq trade-off for each. This is the
  single most valuable thing on the page — the owner does not know these differences and
  will otherwise pick wrong.

---

## 10. AI Receptionist

### 10.1 What is already built

- Per-practice configuration schema — `backend/src/schemas/ai_receptionist.py`
- Call orchestration, fallback-to-human, logging —
  `controller/ai_receptionist/ai_receptionist_controllers.py`
- Human availability slots — `services/ai_receptionist/human_availability_service.py`
- Frontend workspace — `app/dashboard/receptionist/`
- 9 agents are **auto-seeded and plan-gated** at provisioning
  (`provisioning_service.py:169`)
- Per-agent cost tracking — `services/agent_costing/`, migration
  `d88cd21b7c1f_agent_costing_and_patient_ai_assignment_.py`

### 10.2 The step-by-step guide the owner must see

```
/dashboard/receptionist  (or Settings → AI Receptionist)

STEP 1 — Pick a starting point
   Pre-built system prompts:  Appointment Booking · Patient Intake · FAQ Desk
   "Custom" opens an editor with the clinic's real details.
   Show a live preview of how the greeting will sound.

STEP 2 — Choose a voice
   OpenAI TTS · ElevenLabs · Twilio TWIML
   ▶ Play a sample. Let them compare before committing.

STEP 3 — Tell it when a human is available
   Per-day windows + which staff member + max concurrent calls.
   This drives both the handoff logic and the "we'll call you back" promise.

STEP 4 — Write the call flow
   Greeting → menu (press 1 appointments / 2 speak to doctor / …)
   → silence timeout → after-hours behaviour.

STEP 5 — Test
   A test-number button. Transcript appears immediately.
   Iterate until it sounds right.

STEP 6 — Go live
   Toggle on. Inbound calls route to the AI.
   Every call logged and reviewable in the dashboard.
```

### 10.3 Product rule

**The AI must never be the only thing on the line.** Every path needs a human handoff, and
the UI must make configuring one **impossible to skip** before going live. For a medical
practice this is a trust requirement, not a feature preference.

---

## 11. Agent Settings — "Add Your Own API Key"

The owner must be able to bring their own LLM key instead of consuming Aiaceone's margin.

**Existing:** `app/dashboard/settings/AgentSettingsPage.tsx`, `useAgentSettings.ts`,
`agentCosting.ts`, `useAgentCosting.ts`; backend `router/agent_config/`,
`services/agent_config/`, `services/agents/`, `services/llm/` (with LangSmith tracing —
`tests/test_langsmith_tracing.py`).

**The self-serve zero-to-live story must read:**

```
1. Choose your provider      OpenAI · Anthropic · Google · OpenRouter · local
2. Paste your API key        stored per-practice, never shared across practices
3. See the cost              per-agent cost estimate BEFORE enabling
4. Enable one agent          test it on a single number first
5. Add your number           link Twilio or WhatsApp
6. Go live                   with a human handoff already configured
```

**Security requirements (non-negotiable):**
- Keys stored **encrypted at rest**, scoped to `practice_id`, **never** returned to the
  frontend (mask only: `sk-…a1b2`).
- A practice's key must **never** be usable by another practice — this is the same
  isolation rule as §5, applied to secrets.
- Log which practice used which key, for billing attribution and abuse response.
- Redact keys from all logs and error traces.

---

## 12. Support / Ticket System

> **Status: DOES NOT EXIST. Gap G-3.**

For a product sold as "request access and we'll switch you on," the ability to ask for help
is part of the product — not an extra.

### 12.1 Minimum viable design

```sql
support_tickets
  id, practice_id, created_by_user_id,
  subject, body, category,        -- 'general'|'billing'|'technical'|'bug'|'onboarding'
  status,                         -- 'open'|'in_progress'|'waiting_on_customer'|'resolved'
  priority,                       -- 'low'|'normal'|'high'|'urgent'
  created_at, updated_at, resolved_at
support_messages
  id, ticket_id, author_user_id, is_staff, body, created_at
```

- Owner raises a ticket from the dashboard (`/dashboard/support`) — **from any screen**, via
  a persistent "Need help?" button.
- Super-Admin gets a queue at `/super-admin/support`, filtered by status/priority/practice.
- Replies thread in-app and email both parties.
- Status changes notify the owner in-app (`models/notification.py` already exists).

### 12.2 Which onboarding step creates the first ticket automatically?

**Step 4 of the AI Receptionist setup.** This is the step where a non-technical owner most
often gets stuck, and it is the moment intent is highest. Offer: *"Having trouble? Ask your
Aiaceone contact — this takes 2 minutes and we'll help you finish."* That is a warm,
high-value assist with zero infrastructure beyond the ticket system.

---

## 13. Super-Admin Panel

Mounted at `/super-admin/*` (`App.tsx:84`), guarded by `AdminRequireAuth.tsx` +
`useAdminAccess.ts`. Old `/admin/*` redirects.

| Route | File | Purpose |
|-------|------|---------|
| `/super-admin` | `PlatformOverviewPage.tsx` | Cross-tenant metrics |
| — | `PlatformPulsePanel.tsx` | Health gauges |
| `/super-admin/org-requests` | `OrgRequestsListPage.tsx` | **Approve / reject org requests** |
| `/super-admin/clinics` | `ClinicsListPage.tsx` | All practices |
| `/super-admin/clinics/:id` | `ClinicDetailPage.tsx` | Per-clinic detail, suspend/reactivate |
| `/super-admin/plans` | `PlanManagementPage.tsx` | Plan CRUD, custom pricing |
| `/super-admin/sales-leads` | `SalesLeadsPage.tsx` | Lead funnel |
| `/super-admin/super-agent` | `SuperAgentPage.tsx` | Platform agent management |
| `/super-admin/support` | — | **Ticket queue (G-3)** |

### 13.1 Controls that must exist

- Approve / reject an org request, with an optional plan tier.
- **Suspend** a clinic — soft, data-preserving (`admin_services.py:319`).
- **Reactivate** (`admin_services.py:328`).
- Change a clinic's plan tier.
- See every user's activity trace (`models/audit_log.py`).
- Impersonate/view-as a practice **with an audit entry** — invaluable for debugging, and a
  privacy-sensitive action, so it must be logged.

### 13.2 Honesty constraint ⚠️

Every revenue and cost figure in `admin_services.py` is an **estimate**, and the code is
careful to prefix the fields `estimated_` so the UI cannot present them as measurements
(`admin_services.py:20-27`). Keep that discipline. Do not add a "real revenue" label on top
of `ASSUMED_MONTHLY_SESSIONS_PER_AGENT` math.

---

## 14. Database Reference

### 14.1 Existing (verified)

| Table | Model | Tenant column |
|-------|-------|---------------|
| `practices` | `models/practice.py` | **is the tenant** |
| `users` | `models/user.py` | `practice_id` |
| `pending_signups` | `models/pending_signup.py` | `practice_id` (nullable) |
| `patients` | `models/patient.py` | `practice_id` |
| `doctors` | `models/doctor.py` | `practice_id` |
| `appointments` | `models/appointment.py` | `practice_id` |
| `agent_configs` | `models/agent_config.py` | `practice_id` |
| `subscriptions` | `models/subscription.py` | `practice_id` |
| `plans` | `models/plan.py` | platform-level |
| `audit_logs` | `models/audit_log.py` | `practice_id` |
| `notifications` | `models/notification.py` | `practice_id` |
| `pending_doctor_requests` | `models/pending_doctor_request.py` | `practice_id` |
| `pending_staff_requests` | `models/pending_staff_request.py` | `practice_id` |

### 14.2 New tables needed

| Table | Why |
|-------|-----|
| `support_tickets` | G-3 |
| `support_messages` | G-3 |
| `is_sample` column on seeded tables | G-2 — must be `nullable=False, default=False` so existing rows are real by construction |

### 14.3 Migration discipline

Follow the precedent set by `6becd117ec3f`: create Postgres `ENUM` types explicitly with
`checkfirst=True` before `ALTER TABLE` (lines 22-29), and use `server_default` so existing
rows backfill in the same statement (lines 44-49). **Never** write a migration that locks
out an existing paying customer.

---

## 15. API Endpoint Reference

### 15.1 Org requests (exist)

| Method | Path | Handler |
|--------|------|---------|
| POST | `/api/org-request` | `org_request_service.submit` |
| GET | `/api/org-request/me` | `org_request_service.get_my_request` |
| GET | `/api/admin/org-requests` | `admin_services.list_pending_org_requests` |
| POST | `/api/admin/org-requests/{id}/approve` | `admin_services.approve_org_request` |
| POST | `/api/admin/org-requests/{id}/reject` | `admin_services.reject_org_request` |

### 15.2 Practice lifecycle (exist)

| Method | Path | Handler |
|--------|------|---------|
| GET | `/api/admin/practices` | `list_practices` |
| POST | `/api/admin/practices` | `create_practice` |
| GET | `/api/admin/practices/{id}` | `practice_detail` |
| POST | `/api/admin/practices/{id}/suspend` | `suspend_practice` |
| POST | `/api/admin/practices/{id}/reactivate` | `reactivate_practice` |

### 15.3 New endpoints needed

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/demo/seed` | G-2 — load sample data for caller's practice |
| DELETE | `/api/demo/sample-data` | G-2 — clear all sample data |
| GET | `/api/demo/sample-data/counts` | G-2 — per-entity counts |
| POST | `/api/support/tickets` | G-3 |
| GET | `/api/support/tickets` | G-3 |
| GET | `/api/support/tickets/{id}` | G-3 |
| POST | `/api/support/tickets/{id}/messages` | G-3 |
| PATCH | `/api/support/tickets/{id}` | G-3 |
| GET/PUT | `/api/integrations/twilio` | G-4 |

---

## 16. Implementation Roadmap

Ordered by **conversion impact ÷ risk**.

| # | Item | Gap | Effort | Impact |
|---|------|-----|--------|--------|
| 1 | Add "Request free access" CTA to Pricing + CheckoutModal | G-1 | ~30 min | 🔴 **Critical** — unblocks the entire free path |
| 2 | Per-practice sample data service + endpoints | G-2 | M | 🔴 High — makes the trial non-empty |
| 3 | Sample-data panel in dashboard settings (with delete) | G-2 | S | 🔴 High — gives the owner the control the brief demands |
| 4 | `TwilioCard` + split Meta/Instagram cards + "which should I choose?" | G-4 | M | 🟡 Medium |
| 5 | `is_sample` flag + exclusion from finance/analytics | G-2 | S | 🟡 Medium — **protects credibility** |
| 6 | Support ticket system (model → router → both UIs) | G-3 | L | 🟡 Medium |
| 7 | Auto-seed on org approval (behind a Settings flag) | G-2 | S | 🟢 Polish |

### Definition of Done for the free path

A prospect can go from the Pricing page to a **fully-populated, working Owner dashboard with
zero payment**, and Aiaceone can switch them on, watch them, trace them, and support them —
all from `/super-admin/*`.

---

## Appendix — Document Maintenance

This file is **verified against code**. When any of the above changes, update this file in
the same commit. A spec that drifts from the implementation is worse than no spec — it is
how a team ends up believing a feature exists when it does not.

**Verified:** 2026-10-02, against branch state at commit time.