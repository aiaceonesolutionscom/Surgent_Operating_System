# Post-purchase onboarding

The path from "just paid on Stripe" to "looking at my own dashboard":

```
Pricing (#pricing on /) → CheckoutModal (collects the email)
  → /pricing/pay  (CheckoutPage: our plan summary + Stripe's EMBEDDED payment form)
  paid      → Stripe redirects to /pricing/success?session_id=...&plan_tier=...&email=...  (CheckoutSuccessPage)
                → already signed in?  → straight to /onboarding/claim
                → not signed in?      → Clerk sign-up (prefilled email) → forceRedirectUrl=/onboarding/claim
                → /onboarding/claim  (ClaimPlanPage)
                → /onboarding/setup  (SetupWizardPage: 3 skippable steps)
                → /dashboard  (now tier-gated, see ../dashboard/plan/README.md)
```

`/pricing/pay` (`CheckoutPage.tsx`) asks the backend for a Checkout Session
(`POST /checkout/create-session` → `client_secret`), loads Stripe.js from
`js.stripe.com/dahlia` and mounts Stripe's payment form into `#checkout-form`
(`initCheckoutFormSdk` → `createForm` → `loadActions` → `confirm`). Card details
are typed into Stripe's iframe - they never touch our page or servers. There is
no simulated payment anywhere: without `STRIPE_SECRET_KEY` and the plan's
`stripe_price_id` the backend answers 503 and the page says checkout is
unavailable. Needs `VITE_STRIPE_PUBLISHABLE_KEY` at build time. The signup is
marked paid by the Stripe webhook (`checkout.session.completed`), which is why
the success page polls. See `STRIPE_INTEGRATION_TODO.md` at the repo root.

**`CheckoutSuccessPage` checks `useUser().isSignedIn` before showing
"Create your account".** Clerk's default single-session mode throws
`cannot_render_single_session_enabled` if `SignUpButton` opens while already
signed in (a real error hit during testing — anyone who already has an
active session, e.g. re-running this flow or already using the product,
would trip it). If already signed in, the button becomes "Continue to
setup" and goes straight to `/onboarding/claim` using the existing session —
no attempt to open a sign-up modal at all.

## What's real now (Phase 4 is done)

`POST /api/v1/practice/claim` (`backend/src/router/practice/practice_router.py`)
is real — it calls `provisioning_service.py`'s
`provision_from_pending_signup()`, which creates a real `Practice` + `User`
(role="owner") + `Subscription` + seeds `AgentConfig` rows for every agent
the tier includes. Idempotent on both `pending_signup.id` and
`Practice.email` (a repeat buyer attaches a new `Subscription` instead of
erroring). Verified directly against a real local Postgres: claiming a
Practice-tier session produced exactly 24 `AgentConfig` rows (5 front-desk +
7 consultation + 6 surgery + 6 post-care), matching
`dashboard/plan/planCapabilities.ts`'s mapping exactly.

`CheckoutSuccessPage` polls the real `GET /checkout/session/{id}` a few
times before showing "Payment confirmed" — matters once real Stripe is
connected (its webhook can race the browser redirect); in demo mode (below)
there's no race so this resolves immediately.

`usePlanTier.ts`'s source #1 (`GET /api/v1/practice/me`, via
`api/authFetch.ts`'s Clerk-token-attached fetch) is live — a signed-in
practice's dashboard reads its real tier from the database, not the local
override. The local override (`planStorage.ts`) is still the fallback for
Clerk-disabled dev/testing and for `ClaimPlanPage`'s error path (backend
unreachable, session not found, email mismatch) — same
graceful-degradation pattern used everywhere else Clerk is touched in this
app (`Navbar.tsx`, `RequireAuth.tsx`).

**One thing genuinely not verifiable yet**: a full browser-driven Clerk
sign-up → claim round trip. Clerk's device-verification challenge (an email
code) blocks headless/automated sign-in on a "new device," which every fresh
test browser context is. The claim logic itself was verified directly
against the real database (see above) and the route's auth-gating returns
clean 401s for missing/invalid tokens — `get_current_user`'s JWT
verification itself is pre-existing, unmodified code already proven working
elsewhere in this app. A real signed-in browser session should work; it just
wasn't possible to prove with literal pixels in this environment.

## Demo checkout mode

`checkout_services.py`'s `_stripe_configured()` checks for the "xxxx"
placeholders still in `backend/.env`'s `STRIPE_SECRET_KEY`/`STRIPE_PRICE_*`.
While they're placeholders, `create_checkout_session()` skips Stripe
entirely (`_demo_checkout()`) — marks the `PendingSignup` as paid
immediately and redirects straight to `/pricing/success`, so the whole
purchase → claim → dashboard flow can be reviewed end to end before Stripe
is connected. This was an explicit, informed decision (not a default
behavior to leave in production) — the moment real keys are set,
`_stripe_configured()` stops matching and the real Stripe Checkout path
runs; nothing else changes.

## Why a setup wizard, not straight to an empty dashboard

`usePracticeProfile()` defaults to the literal string `"Your Practice"`.
Landing on an Overview page headed that with zero doctors is a bad first
impression of a $690+/mo product. The wizard (3 steps: practice details,
first doctor, connect a channel — each a field subset of the real
`ProfilePage.tsx`/`DoctorFormPage.tsx`) makes the tier tangible at first
contact and gets the essentials filled in.

It's never a dead end: every step is skippable
(`useOnboardingState.ts` tracks progress so a reload mid-wizard resumes,
not restarts), and `../dashboard/overview/SetupChecklist.tsx` on the
Overview page picks up anything left unfinished, derived from real state
(not a one-shot "onboarding complete" flag) — so it disappears once
everything's actually filled in and never traps someone who skipped ahead.

## `RequirePractice`

`../auth/RequirePractice.tsx` wraps the dashboard alongside `RequireAuth` —
closes (partially; see its own comment) the gap `../auth/README.md`
documents: a real Clerk user who never bought a plan (or bought one before
this flow existed) gets a nudge to pricing instead of silently landing on a
Solo-shaped dashboard that isn't really theirs. Presentation-only, same
caveat as `dashboard/plan/`.
