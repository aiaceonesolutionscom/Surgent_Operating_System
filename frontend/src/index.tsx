import "./index.css";
import ReactDOM from "react-dom/client";
import * as Sentry from "@sentry/react";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { ErrorBoundary } from "./components/layout";
import { App } from "./App";

const rootEl = document.getElementById("root");
const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

// Sentry is opt-in via VITE_SENTRY_DSN (empty = disabled). DSN is a public
// client key, safe to ship in the bundle. This only surfaces browser errors;
// first-party tracing is left to the backend, and traces_sample_rate here is
// browser-session replay-free error tracing only.
// This one stays a static import on purpose: Sentry has to be listening before
// the first render to catch a crash during app boot, and deferring it would
// lose exactly the errors that matter most. It is split into its own
// `vendor-sentry` chunk in vite.config.ts so it caches independently and
// doesn't weigh down the app code chunk.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    // Without a release, Sentry cannot tell a new error from a pre-existing
    // one, so "regression in this deploy" and "fixed in the next release" stay
    // permanently greyed out and a stack trace can't be tied to a build. Set
    // VITE_APP_VERSION to the SAME string as the backend's APP_VERSION so a
    // browser error and the API stack trace it hit share one release.
    release: import.meta.env.VITE_APP_VERSION,
    // The backend sets this explicitly; do the same here so the guarantee
    // doesn't depend on which side of the wire an event was captured from.
    sendDefaultPii: false,
    tracesSampleRate: 0.1,
  });
}

// PostHog: auto-captures clicks, pageviews, and session replay (sensitive
// inputs masked by default). Opt-in via VITE_POSTHOG_KEY; no key = off.
//
// Loaded lazily on idle rather than statically. posthog-js with session
// replay is ~100 KB gz and analytics must never be in the critical rendering
// path — a statically imported SDK is downloaded, parsed and executed *before*
// the first paint even when the key is absent and `init` never runs. Loading
// it in an idle callback keeps it off that path entirely; the trade-off is
// that a user who leaves within a moment of landing may not have their first
// pageview recorded, which is the right thing to lose to a faster first paint.
const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
if (posthogKey) {
  const startPostHog = () => {
    void import("posthog-js").then(({ default: posthog }) => {
      posthog.init(posthogKey, {
        api_host: import.meta.env.VITE_POSTHOG_HOST || "https://us.i.posthog.com",
        capture_pageview: true,
        capture_pageleave: true,
        // Patient names, chat text and clinical notes are on nearly every
        // dashboard screen, so replay masks ALL text and ALL inputs - the old
        // ".sensitive" selector matched nothing, i.e. nothing was masked.
        // The scroll-scrubbed hero restyles several elements on every scroll frame and
        // holds nothing worth replaying (a canvas of marketing frames), so it is
        // blocked: rrweb then neither observes nor serialises its mutations.
        session_recording: { maskAllInputs: true, maskTextSelector: "*", blockSelector: ".cinematic-hero" },
        autocapture: { dom_event_allowlist: ["click", "change", "submit"] },
      });
    });
  };
  if (typeof requestIdleCallback === "function") {
    requestIdleCallback(startPostHog, { timeout: 3000 });
  } else {
    setTimeout(startPostHog, 2000);
  }
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
    <ClerkProvider publishableKey={clerkKey} signInFallbackRedirectUrl="/">{app}</ClerkProvider> :
    app
  );
}
