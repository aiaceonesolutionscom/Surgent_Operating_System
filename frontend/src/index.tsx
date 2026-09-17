import "./index.css";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import posthog from "posthog-js";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { ErrorBoundary } from "./components/layout";
import { App } from "./App";

const rootEl = document.getElementById("root");
const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

// Sentry is opt-in via VITE_SENTRY_DSN (empty = disabled). DSN is a public
// client key, safe to ship in the bundle. Deliberately no PII / tracing config:
// first-party tracing is left to the backend, this only surfaces browser errors.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  });
}

// PostHog: auto-captures clicks, pageviews, and session replay (sensitive
// inputs masked by default). Opt-in via VITE_POSTHOG_KEY; no key = off.
const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
if (posthogKey) {
  posthog.init(posthogKey, {
    api_host: import.meta.env.VITE_POSTHOG_HOST || "https://us.i.posthog.com",
    capture_pageview: true,
    capture_pageleave: true,
    session_recording: { maskTextSelector: ".sensitive, input[type=password]" },
    autocapture: { dom_event_allowlist: ["click", "change", "submit"] },
  });
}

// ClerkProvider throws if `publishableKey` is empty, so a clone without
// .env.local set up yet would otherwise get a blank white page. Degrade to
// running without auth instead — sign-in controls just won't render (see
// Navbar), same graceful-fallback pattern used elsewhere in this app.
const app = (
  <ErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ErrorBoundary>
);

if (rootEl) {
  ReactDOM.createRoot(rootEl).render(
    clerkKey ?
    <ClerkProvider publishableKey={clerkKey} afterSignInUrl="/" afterSignUpUrl="/">{app}</ClerkProvider> :
    app
  );
}
