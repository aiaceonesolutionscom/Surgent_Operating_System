# AesthetixAI Practice Dashboard — concept & roadmap

This is the real, staff/doctor-facing product (distinct from the marketing site in
`frontend/src/pages/` and `frontend/src/components/`). Nothing under `app/dashboard/`
is wired up yet — this doc records the agreed direction before implementation starts,
so a fresh session (or a teammate) doesn't have to re-derive it.

## Why this exists

The marketing site sells 31 AI agents running a clinic end-to-end. The dashboard is
where a real clinic's staff actually watches and manages that — every patient
conversation, every booking, every escalation, every dollar. It's a full product on
its own, not a small admin panel bolted onto the marketing site.

## Color system — one palette, no exceptions (standing rule)

The marketing site and the dashboard are **one product** and must look like it.
Early dashboard work followed `design-references/For.UI/clinical_ethereal/DESIGN.md`'s
blue/cyan "Clinical Ethereal" spec verbatim — that's why it used to feel like a
different, generic SaaS admin panel bolted onto the marketing site. That spec is
now **superseded** for color (its layout ideas — 280px sidebar, 24px card radius,
tabular figures, Cmd+K — still stand). Every color in the whole app, marketing
site and dashboard alike, comes from `frontend/tailwind.config.js`'s
`theme.extend.colors` — nothing else:

- **Primary — `teal` (600 = `#0B6362`)**: the one brand color. Buttons, active
  nav state, links, primary icons, focus rings. This is the site's actual
  signature color (hero accents, nav, CTAs) — carrying it into the dashboard
  is what makes the two feel like one product instead of two.
- **Secondary/accent — `gold` (`#C9A24B`)**: highlights, "most popular"/premium
  badges, a second data-series color. Used sparingly, never as a primary
  action color.
- **Neutrals — `canvas`/`sand`/`ink`**: warm cream page background
  (`canvas` `#FAF8F4`), warm off-white card/border scale (`sand` 50–300),
  warm near-black text scale (`ink`/`ink-soft`/`ink-muted`). **Never** cool
  grays (`slate`/`gray`/raw hex like `#F7F9FB`, `#64748B`, `#0F172A`) —
  that cool-vs-warm neutral mismatch, not just the accent hue, was the real
  cause of the dashboard reading as a different, "fully white" product.
- **Functional only — `success`/`warning`/`danger`**: status semantics
  (resolved/pending/escalated, on/off toggles). Not brand colors — don't
  reach for them outside genuine status meaning.
- **Real platform brand colors stay as-is** (Instagram pink, WhatsApp green,
  Facebook blue, etc. in `data/channels.ts`) — recognizable third-party
  brand colors are correct to keep, not something to fold into the palette.

**Rule for all future work, anywhere in `frontend/src/`**: no raw hex classes
(`bg-[#...]`), no Tailwind's default gray/slate/blue palette, no new colors
added ad hoc. If a screen needs a color, it's one of the tokens above — if
none fits, it's a `tailwind.config.js` conversation, not a one-off inline hex.
This is what keeps the app from drifting back into looking "vibe coded."

## Foundation already in place

- **31-agent roster** — `frontend/src/data/agents/index.ts` (`AGENT_CATEGORIES`,
  5 categories: front-desk, consultation, surgery, post-care, business). The dashboard
  must reuse this exact naming/grouping — the marketing `/agents` page and the
  dashboard sidebar should feel like the same product, not two different ones.
- **Backend agent triads** — `backend/src/{router,controller,services}/agents/<slug>_agent/`
  for all 31 agents. Only `receptionist` has real (if thin) LLM/Twilio logic wired
  today; the rest are stubs — check before assuming an agent already "does" something.
- **Real DB models** — `backend/src/models/`: `Patient`, `Appointment`, `Conversation`,
  `Message`, `Invoice`, `RecoveryJournal`, `AgentLog`, `AgentConfig`, `Practice`,
  `User`, `PatientPhoto`, `Procedure`, `Subscription` — all practice_id-scoped
  (multi-tenant). **Known bug to fix before building on top of it**: `Patient.practice`
  and `Appointment.practice` relationships point at the wrong model name (`"Patient"`/
  `"Appointment"` instead of `"Practice"`) in `backend/src/models/`.
- **Real `conversations` API now exists** — `backend/src/router/conversations/`,
  `controller/conversations/`, `services/conversations/` (`GET /api/v1/conversations`
  with `status`/`channel`/`agent_type`/`search` filters, `GET /{id}`,
  `POST /{id}/resolve`). Practice-scoped via a new `get_current_practice_user`
  dependency (`server/dependencies.py`) that resolves a Clerk session to a local
  `User`/`practice_id` — this didn't exist before either. Verified end-to-end
  against a real local Postgres 18 instance (initialized on this machine —
  `initdb`'d and started directly via `pg_ctl`, since the Windows service
  registration needs admin rights this shell doesn't have; see
  `backend/alembic/`, whose `env.py` previously never imported `src.models`
  so `Base.metadata` was empty and autogenerate produced blank migrations —
  fixed). The sessions inbox (`sessions/useSessions.ts`), Overview KPIs,
  the Analytics page, the Sidebar needs-attention badge, the per-agent and
  per-category session lists, the patient session history, and the per-agent
  session counts on Agent Settings all read the real `conversations`/`analytics`
  APIs (`overview/useOverview.ts`, `analytics/computeAnalytics.ts`). The old
  `data/mockSessions.ts` file has been deleted — nothing reads mock sessions
  any more.
- **AI Receptionist monitor is fully real** — `GET /api/v1/ai-receptionist/overview`
  (`services/ai_receptionist/overview_service.py`) now returns, alongside the
  cost/usage KPIs, the booking-pipeline funnel (patient stages + real
  `Appointment` rows + auto-follow-up counts), channel connection status
  (from `Practice.settings.green_api`), system health (last activity + 24h
  session/interaction counts — no fake CPU/docs telemetry), and a recent
  activity feed (latest 20 `AgentLog` rows). The monitor page polls every 30s;
  `data/mockReceptionistActivity.ts` is deleted. `VoiceEngineCard` stays a
  decorative waveform placeholder on purpose — no live audio stream exists yet.
- **AI Receptionist system prompt is Owner-editable (viewable by staff)** —
  `GET/PUT /api/v1/ai-receptionist/system-prompt`
  (`services/ai_receptionist/system_prompt_service.py`) reads/writes a
  practice-specific instruction block stored in `Practice.settings`
  (`ai_receptionist_system_prompt`). The effective prompt returned is the real
  base template from `inbound_service._system_prompt` plus that custom block —
  the exact prompt every inbound WhatsApp message gets (it's re-read from
  `Practice.settings` per message, so edits apply on the next turn). GET is
  open to Owner/Doctor/Receptionist (front-desk staff can see exactly what the
  AI is told); PUT is Owner-only. `SystemPromptCard.tsx` renders it on the
  monitor page: read-only `pre` + copy for everyone, textarea edit for the Owner.
- **Visual design system** — layout ideas from `design-references/For.UI/clinical_ethereal/DESIGN.md`
  ("Clinical Ethereal") still apply: fixed 280px sidebar, 24px card radius,
  tabular-figure numbers, Cmd+K command palette, progress rings for metrics.
  **Its blue/cyan/cool-gray color palette does not apply** — see "Color
  system" above, which supersedes it. Typeface is the marketing site's own
  (`Plus Jakarta Sans`/`Fraunces`), not Inter.
- **Auth**: Clerk is already wired on the marketing site (`ClerkProvider` in
  `index.tsx`). `app/auth/` (placeholder) is where dashboard sign-in/session logic
  will live; backend routes already expect `Depends(get_current_user)`.

## Sidebar / information architecture

```
Overview                          — home, cross-agent summary
Agent Sessions
  All conversations               — unified inbox, every channel/agent, one list
  Needs attention                 — sessions an agent escalated to a human
Patients                          — patient list + profile (session history lives here)
Front Desk & Intake               — receptionist, booking, reschedule, reminder, translation
Consultation & Screening          — AI consultation, photo analysis, risk assessment, ...
Surgery Management                — scheduling, OR scheduler, implant inventory, ...
Post-Surgery Care                 — recovery follow-up, healing monitoring, triage, ...
Business & Operations             — cost estimation, invoicing, analytics, ...
Analytics                         — real charts, once session data exists (not fake numbers)
Agent Settings                    — per-agent on/off, tone, escalation rules
Profile / Practice settings
```

## "Agent Sessions" — the core concept

Every patient interaction (phone, WhatsApp, Instagram DM, web chat) is one **session**:
which patient, which channel, which agent handled it, the full transcript, what action
the agent took (booked something? sent a reminder? escalated?), and a clear flag if a
human had to step in. This is deliberately **unified across all agents/channels**
(one inbox, not one silo per agent) — modeled on how Intercom Fin / Decagon / Sierra
structure AI-agent conversation inboxes, and how Klara/Weave unify phone+text+chat for
clinics into one place rather than splitting by channel.

Sessions are the backbone the rest of the dashboard reads from: Overview's numbers,
each category page's session list, and Analytics all derive from the same session
data — build this first, everything else is a filtered view of it.

## Making it not feel generic ("vibe coded")

- Reuse real brand icons per channel (WhatsApp/Instagram/Facebook — already built for
  `Omnichannel.tsx` on the marketing site) and `lucide-react` icons per agent category
  (already in use in `AgentSuite.tsx`) — don't reinvent.
- Reuse the scroll-guide doctor avatar character for the dashboard's "agent" identity
  — one consistent character across marketing + product, not a new generic bot icon.
- Every metric gets a real chart/progress ring (per DESIGN.md), not a bare number.
- Every empty state (no sessions yet, no patients yet) gets a real illustration + copy,
  not a blank list.
- Tabular figures for all numeric tables/charts (DESIGN.md requirement).
- Cmd+K command palette across Patients/Appointments/Agent settings — a real,
  functional one, not decoration.

## Build order (phases)

1. **Overview + Agent Sessions (unified inbox)** — done (frontend, mock data).
   Sidebar's "Agent Sessions" and "Agents" are collapsible parents that expand
   to their sub-items (`layout/Sidebar.tsx`) rather than sitting flat.
2. **Patient profile pages** — done (frontend, mock data). `patients/PatientsPage.tsx`
   (searchable table) → `patients/PatientDetailPage.tsx` (profile + that
   patient's session history, reusing `sessions/SessionsView`). A session's
   patient header links here (`sessions/SessionDetailPane.tsx`).
3. **Per-category agent pages, one level deeper** — done (frontend, mock data).
   Each agent chip on `agents/AgentCategoryPage.tsx` now links to
   `agents/AgentDetailPage.tsx` (`/dashboard/agents/:categoryId/:agentSlug`):
   agent info, a live/not-yet-active status badge (only `receptionist` is
   marked live — matches its actual backend state, see `LIVE_AGENT_SLUGS`),
   and that agent's own filtered sessions.
4. **Analytics** — done (frontend, real API). `analytics/AnalyticsPage.tsx`
   reads `GET /api/v1/analytics/sessions` (real SQL aggregates over the
   `Conversation` table); `analytics/computeAnalytics.ts` is now a pure mapper
   that only enriches the raw channel/category codes with the CHANNELS/
   AGENT_CATEGORIES labels and colors the chart components expect.
5. **Agent Settings** — done (frontend + real API). `settings/AgentSettingsPage.tsx` lists
   all 31 agents grouped by category with an enabled toggle, tone, and
   escalation-sensitivity control per agent. Writes now go through the real
   per-practice `AgentConfig` model via `GET/PUT /api/v1/agent-config`
   (`settings/useAgentSettings.ts` — optimistic PUTs, Owner-authorized on the
   backend) instead of `localStorage`; a new `GET /api/v1/agent-config` list
   endpoint loads the practice's rows in one call.
6. **Auth (Clerk) + practice profile** — done (frontend). `app/auth/RequireAuth.tsx`
   gates every `/dashboard/*` route behind Clerk (`<SignedIn>`/`<SignedOut>`),
   wired into `DashboardRouter.tsx`; a signed-out visitor sees a sign-in
   prompt instead of the dashboard. `profile/ProfilePage.tsx` shows the real
   signed-in Clerk user (name/email/avatar via `useUser()`) plus editable
   practice fields (`profile/usePracticeProfile.ts`, `localStorage` for now —
   shaped to match the real `Practice` model). **Not yet real multi-tenant
   auth** — see `app/auth/README.md` for what's still missing (verifying the
   signed-in user belongs to the practice whose data they see; attaching a
   Clerk session token to backend API calls, which don't exist yet either).

7. **Doctors directory** — done (frontend, `IndexedDB`). `doctors/DoctorsPage.tsx`
   (grid, "Add doctor") → `doctors/DoctorFormPage.tsx` (shared add/edit form) →
   `doctors/DoctorDetailPage.tsx` (profile). The `Doctor` type
   (`doctors/types.ts`) properly defines a doctor beyond just a name: `specialty`
   (primary), `capabilities` (procedures they're credentialed to perform, tag
   list), `availability` (per-weekday time-range slots — which days they're in
   and what hours), `photoUrl`, and `documents` (license/certification/CV —
   PDF or Word, also uploaded via the form and stored as a data URI for now).
   Documents open in a full-screen viewer (`doctors/DocumentViewerModal.tsx`
   — inline `<iframe>` preview for PDFs, download-to-view for Word since
   browsers can't render it inline) with a real download action either way.
   **The iframe uses a `blob:` URL, not the raw `data:` URI, for its `src`**
   — confirmed in real Chrome (not just headless test tooling) that a `data:`
   URI PDF renders fine at a couple KB but silently renders blank once it's
   several MB, with zero error to explain why (a real scanned license/
   certification PDF is easily 5-20MB). Converting the data URI to a `Blob`
   via `URL.createObjectURL()` before handing it to the iframe fixes it at
   any size — verified with a real 15MB multi-page PDF rendering correctly
   in under a second. If a future feature needs to show a large file inline
   again, use this same pattern rather than a raw `data:` URI.
   Persisted via `doctors/useDoctors.ts` + `doctors/doctorsDB.ts` — **IndexedDB,
   not `localStorage`**: photos/documents are base64 data URIs (~33% bigger
   than the file), and localStorage's ~5-10MB per-origin cap filled up after
   a couple of real PDFs, silently failing the save (each `/dashboard/doctors/*`
   page mounts its own hook instance and re-reads on mount, so a page you
   navigated to next would show the doctor/document as if it had never been
   added — that was a real bug hit in practice, not a hypothetical one).
   IndexedDB's quota is a large fraction of free disk space, so this doesn't
   recur; `addDoctor`/`updateDoctor` are now async and return a boolean so a
   genuine failure — private browsing with storage fully disabled, the one
   remaining case — still surfaces a clear inline error instead of silently
   losing the edit. A real doctor is the existing `User` model (role="doctor")
   plus this specialty/capabilities/availability/license/bio/documents
   extension, which doesn't exist on that model yet (documents specifically
   would need real object storage, not a DB column, once files get numerous
   or large).
   Doctor-side finance ("My performance") stays a stub on the detail page,
   deliberately separate from payroll/compensation (admin-only, not built).

8. **Plan-tier gating + post-purchase onboarding** — done, including real
   backend provisioning (Phases 0–4 of the plan doc). `plan/README.md` has
   the full mapping table and derivation from `data/plans.ts`'s marketing
   copy — short version: Solo unlocks Front Desk & Intake only, Practice
   adds Consultation/Surgery/Post-Care + Analytics, Enterprise adds Business
   & Operations (billing agents) + unlimited doctors/channels/locations.
   Every gated surface is **visible-but-locked**, not hidden
   (`plan/UpgradeRequired.tsx`) — Sidebar, Agent Settings, Command Palette,
   Doctors' add-limit, and the Analytics route all read from the same
   `plan/planCapabilities.ts` source of truth. `billing/PlanBillingPage.tsx`
   only displays the current plan; there is no client-side plan switch (the
   plan comes from the clinic's Stripe-backed subscription).
   `app/onboarding/` (own README) covers the Stripe-redirect-to-dashboard
   flow: `/pricing/success` → Clerk sign-up → `/onboarding/claim` → a
   3-step skippable setup wizard → `/dashboard`.
   **Real backend provisioning is live**: `POST /api/v1/practice/claim`
   (`router/practice/`, `services/checkout/provisioning_service.py`) creates
   a real `Practice`/`User`/`Subscription`/`AgentConfig` set from a paid
   `PendingSignup` — verified directly against a real local Postgres
   (a Practice-tier claim produced exactly the expected 24 `AgentConfig`
   rows). `GET /api/v1/practice/me` (`usePlanTier.ts`'s source #1, via the
   new `api/authFetch.ts` Clerk-token attachment — this closes the
   "no Clerk token attached to backend calls" gap `app/auth/README.md`
   documented) is what a signed-in practice's dashboard actually reads its
   tier from now, not just the local override. Real backend enforcement
   (`services/practice/plan_capabilities.py` + `require_plan_feature()`/
   `require_agent_category()` in `server/dependencies.py`) exists and is
   wired into `get_current_practice_context`; `require_plan_feature("analytics")`
   now guards `GET /api/v1/analytics/sessions` (the Analytics page), while
   `/analytics/overview` stays open because it backs the Owner home screen for
   every tier. Checkout is always real Stripe (embedded payment form); there
   is no demo/simulated payment, and without Stripe configured the backend
   answers 503.

Phases 1–6 above were originally shaped on `data/mockSessions.ts` /
`data/mockPatients.ts` and `localStorage` (settings/profile) — the mocks matched
the real `Conversation`/`Message`/`Patient`/`AgentConfig`/`Practice` backend
models so swapping in real data is a data-source change, not a UI rewrite. Now
that the `conversations`/`analytics` APIs, real auth, and the real `AgentConfig`
settings API are live, every session list on the dashboard reads real
conversations, and `data/mockSessions.ts` plus `data/mockPatients.ts` are both
deleted — agent settings persist via `/api/v1/agent-config`; patients fall back
to the IndexedDB cache of real API data (never fabricated rosters) and the
signed-out doctor "My Day" screen shows an honest empty schedule (the profile
`localStorage` still stands in for its real API). Remaining gaps are the real
multi-tenant auth polish and the agent-level runtime work described in
`backend/src/services/agents/*/README.md` (the 31-agent specs written alongside
this dashboard work), which is the next real build target.

## Backend LLM: Mistral added (low-stakes tier)

`backend/src/services/llm/llm_service.py` now supports two providers:
OpenAI (default, `tier="high"`) and Mistral (`tier="low"`, via Mistral's
OpenAI-SDK-compatible endpoint — no new pip dependency). Falls back to OpenAI
if Mistral hits its rate limit. Matches the tiered strategy already described
in `frontend/system.md`. `MISTRAL_API_KEY` is set in `backend/.env`
(gitignored). Existing call sites (`receptionist_agent_services.py`) are
unaffected — they default to `tier="high"` (OpenAI) unless changed.

Competitor reference points used for this direction: Intercom Fin / Decagon / Sierra
(unified AI-agent conversation inbox, escalation/handoff patterns, per-conversation
analytics) and Klara / Weave / NexHealth (clinic-specific: unify phone+text+chat into
one dashboard, real-time scheduling sync) — full research notes were part of the
conversation that produced this doc, not duplicated here.
