# Stripe integration — status and remaining steps

The signup subscription now uses **Stripe's embedded payment form** (Checkout Session, `ui_mode: form`) instead of the
old hand-built card UI. This file is the single source of truth for what was configured and what is left.

## What was found

An existing Checkout Session call was already in the codebase (**Scenario A**), so only its parameters were changed:
[backend/src/services/payment/payment_service.py](backend/src/services/payment/payment_service.py) → `PaymentService.create_checkout_session`.

Two other Checkout Session calls exist in the same file (`create_invoice_checkout_session` for patient invoice payments,
`create_wallet_topup_checkout_session` for wallet top-ups). They were **deliberately left on Stripe's hosted page**: their
dashboard screens redirect to a hosted URL and have no embedded-form UI, so switching them would break them. Say the word
if you want them moved to the embedded form too.

## Values to Replace

**Files containing placeholders:** none — nothing in code is a placeholder any more.

| Field | Current Value | What to Set |
|-------|--------------|-------------|
| `mode` | `subscription` (real, kept) | Nothing — the Practice plan is a monthly subscription. |
| `line_items[].price` | `price_1UOW7g9zQsQdHwaF1Cal8F5t` (a **test-mode** price, $999/mo, created in your Stripe test account) | Not hardcoded: it is read from the plan's `stripe_price_id` (column on the `plans` table; the Admin → Plans drawer has no field for it yet, so set it with SQL). For live mode create the real price in Stripe (live) and store its ID there. |
| `STRIPE_SECRET_KEY` | `sk_test_…` | Live `sk_live_…` key when you go live (backend env). |
| `VITE_STRIPE_PUBLISHABLE_KEY` | `pk_test_…` | Live `pk_live_…` key when you go live (frontend build env). |
| `STRIPE_WEBHOOK_SECRET` | secret of the **test** endpoint `we_1UOWBu9zQsQdHwaFZ7TehM9l` | Create a separate **live** webhook endpoint and use its secret. |

## Configured Parameters

These come from Checkout Studio and are sent exactly as configured.

**Files containing these parameters:**
- [backend/src/services/payment/payment_service.py](backend/src/services/payment/payment_service.py)

| Parameter | Value |
|-----------|-------|
| `ui_mode` | `form` — see the note below (the spec said `custom` for SDKs < 21; Stripe rejects that) |
| `billing_address_collection` | `auto` |
| `phone_number_collection` | `{enabled: false}` |
| `automatic_tax` | `{enabled: false}` |
| `payment_method_collection` | `always` (subscription mode only) |
| `submit_type` | `auto` |
| `shipping_address_collection.allowed_countries` | 230 countries (the full Studio list) |
| `name_collection` | individual **and** business, both enabled, both optional |
| `integration_identifier` | `custom_embedded_web_0001` |
| Stripe API version (this call only) | `2026-03-25.dahlia; custom_checkout_payment_form_preview=v1` |

App-specific parameters kept alongside them: `client_reference_id` (links the session to our `PendingSignup`), `customer_email`
(prefills the receipt address) and `return_url` (`/pricing/success?session_id={CHECKOUT_SESSION_ID}…`, replaces
`success_url`/`cancel_url`, which embedded modes don't accept).

### Notes worth knowing

- **`ui_mode`.** The Studio spec says `custom` for SDKs older than 21.0.0 (this project uses `stripe` 15.5.0). On the required API version
  Stripe answers *"The ui_mode value `custom` is no longer supported. Use `elements` instead."* and accepts `form`, so `form` is used
  (verified against the live test API, not assumed). The SDK-version rule is about which value a given SDK's bundled API understands;
  here the API version is pinned per request, so the API decides.
- **The API version is passed per request** (`stripe_version=`) and not set globally, so cancel / resume / change-plan, invoice and wallet
  calls keep running on your account's own API version and response shapes.
- **Shipping address.** The Studio configuration collects a shipping address. For a software subscription there is nothing to ship, so
  customers are asked for one needlessly — consider turning it off in Checkout Studio and removing `shipping_address_collection`.

## Setup

**Backend** (`backend/.env`, or the host's env): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`. Dependency: `stripe` (already in `requirements.txt`).
**Frontend** (`frontend/.env.local`, or `insforge deployments env set …`): `VITE_STRIPE_PUBLISHABLE_KEY` (browser-safe; the secret key never goes here).
**Database:** the plan's `stripe_price_id` (`plans` table). In the staging deployment it is already set to the test price above.
**Webhook:** `POST /api/v1/webhooks/stripe`, events `checkout.session.completed`, `customer.subscription.created|updated|deleted`,
`invoice.paid`, `invoice.payment_failed`. A test-mode endpoint pointing at the staging backend already exists.

### Files

| File | Role |
|------|------|
| [backend/src/services/payment/payment_service.py](backend/src/services/payment/payment_service.py) | the Checkout Session call + `get_checkout_subscription_id` |
| [backend/src/services/checkout/checkout_services.py](backend/src/services/checkout/checkout_services.py) | builds `return_url`, remembers the session on `PendingSignup`; **no simulated payments** — 503 when Stripe/price isn't configured |
| [backend/src/router/checkout/checkout_router.py](backend/src/router/checkout/checkout_router.py) | `POST /checkout/create-session` → `{client_secret, session_id}`; `GET /checkout/session/{id}` |
| [backend/src/services/checkout/provisioning_service.py](backend/src/services/checkout/provisioning_service.py) | after signup, links the Stripe subscription and marks the clinic ACTIVE |
| [frontend/src/app/onboarding/CheckoutPage.tsx](frontend/src/app/onboarding/CheckoutPage.tsx) | `/pricing/pay`: Stripe's form and nothing else of ours (Stripe.js from `js.stripe.com/dahlia`, `initCheckoutFormSdk` → `createForm` → `loadActions` → `confirm`) |

Removed: the hand-built card form (`DemoPaymentPage.tsx`), the email-first modal (`CheckoutModal.tsx`), the demo "pay" endpoint and the demo-checkout mode, our own plan-summary panel and header on the checkout page, the unused `/pricing/cancel` page, the dashboard's fake "Switch to this plan" button, the unused `STRIPE_PRICE_SOLO/PRACTICE` settings.

### Flow

1. Pricing → *Get started* → straight to `/pricing/pay?plan_tier=practice` (no email step; Stripe's own form asks for the email).
2. The page calls `POST /checkout/create-session` (email optional); the backend creates the Checkout Session and a `PendingSignup`, returns the `client_secret`.
3. Stripe's form mounts in `#checkout-form`; the customer pays; Stripe redirects to `/pricing/success?session_id=…`.
4. Stripe's `checkout.session.completed` webhook marks the `PendingSignup` paid **and stores the email Stripe collected**; the success page polls until it is, then uses that email to prefill sign-up.
5. The customer creates a Clerk account → `/onboarding/claim` → the clinic is created, the Stripe subscription is linked, status **ACTIVE**.
   (Before this change a paying clinic stayed a *trial* with no Stripe link, so no later Stripe event could update it.)

## Testing

Test mode only needs a test card: **4242 4242 4242 4242**, any future expiry, any CVC, any ZIP. Declines: `4000 0000 0000 0002`;
3-D Secure: `4000 0025 0000 3155`. The page shows a "Test mode" hint while a `pk_test_` key is in use.
Watch the result under Stripe Dashboard → Payments / Subscriptions / Developers → Webhooks.

## Before going live

1. Create the live Product + recurring Price → store its ID in `plans.stripe_price_id`.
2. Swap in live `sk_live_…` / `pk_live_…`; create a **live** webhook endpoint and use its secret.
3. Set `APP_ENV=production` (the app then refuses to boot with test keys or a missing webhook secret).
4. Decide on the shipping-address step (see notes).

## Not done yet / next steps

- The pricing button used to say "Start free trial"; the subscription is charged immediately (no trial period is configured on the Price), so it now says "Get started". If you want a real trial, set `trial_period_days` on the Stripe price / `subscription_data`.

- A complete card payment through the deployed site has **not** been exercised end to end (that needs a person to type a test card);
  everything up to the mounted Stripe form was verified: session creation against Stripe's test API, the form rendering on the live site, and unit tests.
- Billing portal / plan change UI, invoices emailed from Stripe, tax (`automatic_tax` is off), and refunds are out of scope here.

Resources: https://support.stripe.com · https://docs.stripe.com/mcp
