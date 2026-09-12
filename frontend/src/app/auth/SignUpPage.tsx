import React from "react";
import { Link } from "react-router-dom";
import { SignUp } from "@clerk/clerk-react";
import { AuthLayout } from "./AuthLayout";

const clerkEnabled = Boolean(import.meta.env.VITE_CLERK_PUBLISHABLE_KEY);

const clerkAppearance = {
  variables: {
    colorPrimary: "#2563EB",
    colorText: "#0F172A",
    colorTextSecondary: "#64748B",
    colorBackground: "#FFFFFF",
    borderRadius: "0.75rem",
    fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif'
  },
  elements: {
    rootBox: "w-full",
    card: "shadow-[0_20px_50px_-20px_rgba(11,29,38,0.25)] border border-sand-200 rounded-3xl",
    headerTitle: "font-display text-2xl",
    formButtonPrimary: "bg-accent-500 hover:bg-accent-700 text-sm normal-case"
  }
};

export function SignUpPage() {
  return (
    <AuthLayout>
      {clerkEnabled ?
      <SignUp
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        // Deterministically marks this as a genuinely new organization
        // request (mirrors DoctorApplyPage/StaffApplyPage's own
        // unsafeMetadata pattern) — the user.created webhook reads this to
        // file a PendingSignup for Super Admin review instead of granting
        // any practice access. See webhook_router.py's user.created handler
        // and org_request_service.py.
        unsafeMetadata={{ invite_type: "org_request" }}
        appearance={clerkAppearance} /> :

      <ClerkNotConfigured />
      }
    </AuthLayout>);

}

function ClerkNotConfigured() {
  return (
    <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-lift">
      <h1 className="font-display text-2xl font-600 text-ink">Sign-up isn&apos;t configured yet</h1>
      <p className="mt-2 text-sm text-ink-muted">
        Set <code className="rounded bg-sand-100 px-1.5 py-0.5 text-xs">VITE_CLERK_PUBLISHABLE_KEY</code> to enable
        authentication, or start with pricing instead.
      </p>
      <Link
        to="/#pricing"
        className="mt-6 inline-flex items-center justify-center rounded-full bg-ink px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

        See pricing
      </Link>
    </div>);

}
