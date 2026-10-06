import React, { useState } from "react";
import { Link } from "react-router-dom";
import { XIcon, Loader2Icon, ArrowRightIcon } from "lucide-react";
import { createCheckoutSession } from "../../api/commerce";
import { ApiError } from "../../api/client";

interface CheckoutModalProps {
  planId: "solo" | "practice";
  planName: string;
  onClose: () => void;
}

export function CheckoutModal({ planId, planName, onClose }: CheckoutModalProps) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { url } = await createCheckoutSession(email, planId);
      window.location.href = url;
    } catch (err) {
      // Expected today — Stripe is wired with placeholder price IDs until
      // real ones are set in backend/.env (STRIPE_PRICE_SOLO/PRACTICE).
      const message =
      err instanceof ApiError ?
      "Checkout isn't fully connected yet — our team has been notified. Please try again shortly or book a demo instead." :
      "Something went wrong. Please try again.";
      setError(message);
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-ink/50 backdrop-blur-sm px-4" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-4xl border border-sand-200 bg-white p-7 shadow-lift"
        onClick={(e) => e.stopPropagation()}>

        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.14em] text-teal-600">{planName} plan</p>
            <h3 className="mt-1 font-display text-2xl font-600 text-ink">Start your free trial</h3>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-full p-1.5 text-ink-muted transition-colors hover:bg-sand-100 hover:text-ink">

            <XIcon className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={submit} className="mt-6">
          <label className="block text-sm font-medium text-ink-soft">
            Work email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@practice.com"
              className="mt-1.5 w-full rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-teal-400" />

          </label>

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-ink py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700 disabled:opacity-60">

            {loading && <Loader2Icon className="h-4 w-4 animate-spin" />}
            {loading ? "Redirecting to checkout…" : "Continue to checkout"}
          </button>
          <p className="mt-3 text-center text-xs text-ink-muted">
            You'll be redirected to Stripe to complete payment securely.
          </p>
        </form>

        {/* G-1 (see multiclinic.md): without this escape hatch, a prospect who
            isn't ready to pay has nowhere to go but Stripe or the back button —
            the free org-request path is invisible from here. */}
        <div className="mt-5 rounded-xl border border-sand-200 bg-canvas p-4 text-center">
          <p className="text-xs text-ink-soft">
            Not ready to pay yet? Request free access and we&apos;ll set your organization up
            personally first — no card needed.
          </p>
          <Link
            to="/sign-up"
            className="mt-2.5 inline-flex items-center gap-1 text-sm font-semibold text-teal-700 underline-offset-4 hover:underline">
            Request free access
            <ArrowRightIcon className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>
    </div>);

}
