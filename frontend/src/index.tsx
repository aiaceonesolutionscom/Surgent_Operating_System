import "./index.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { ClerkProvider } from "@clerk/clerk-react";
import { ErrorBoundary } from "./components/layout";
import { App } from "./App";

const rootEl = document.getElementById("root");
const clerkKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

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
