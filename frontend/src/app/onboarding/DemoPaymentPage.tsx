import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { LockIcon, Loader2Icon, CalendarIcon, ShieldCheckIcon, MailIcon, CheckIcon, CheckCircle2Icon } from "lucide-react";
import { Logo } from "../../components/ui";
import { planFor } from "../dashboard/plan/plan";
import { useLivePlans } from "../../hooks/useLivePlans";
import type { PlanTier } from "../../data/planTiers";
import { confirmDemoPayment } from "../../api/commerce";
import { ApiError } from "../../api/client";

function formatCardNumber(v: string) {
  return v.replace(/\D/g, "").slice(0, 16).replace(/(.{4})/g, "$1 ").trim();
}

function formatExpiry(v: string) {
  const digits = v.replace(/\D/g, "").slice(0, 4);
  return digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits;
}

type CardBrand = "visa" | "mastercard" | "amex" | "discover" | null;

function detectBrand(digits: string): CardBrand {
  if (/^4/.test(digits)) return "visa";
  if (/^5[1-5]/.test(digits) || /^2[2-7]/.test(digits)) return "mastercard";
  if (/^3[47]/.test(digits)) return "amex";
  if (/^6(?:011|5)/.test(digits)) return "discover";
  return null;
}

const BRAND_LABEL: Record<Exclude<CardBrand, null>, string> = {
  visa: "VISA",
  mastercard: "Mastercard",
  amex: "AMEX",
  discover: "Discover"
};

function CardBrandBadge({ brand, active }: { brand: Exclude<CardBrand, null>; active: boolean }) {
  return (
    <span
      className={`rounded border px-1.5 py-0.5 text-[9px] font-bold tracking-wide transition-colors ${
      active ? "border-teal-600 bg-teal-600/8 text-teal-600" : "border-sand-200 text-ink-muted/50"}`
      }>

      {BRAND_LABEL[brand]}
    </span>);

}

// A real card-entry step — not a skip-straight-to-success shortcut. Styled
// to read as a genuine hosted payment page (order summary, live card-brand
// detection, a locked "Pay" action, "Powered by Stripe" footer) but is
// entirely our own UI: no card data leaves the browser, nothing is
// validated beyond shape, and "Pay" just calls confirm-demo-payment
// (backend/.env's Stripe keys are still placeholders — see
// checkout_services.py's _stripe_configured()). Swapping in Stripe's real
// Elements/Checkout here is the natural next step once real keys exist;
// this page's route (/pricing/pay) and query params stay the same.
export function DemoPaymentPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const sessionId = params.get("session_id") || "";
  const planTier = (params.get("plan_tier") as PlanTier) || "practice";
  const email = params.get("email") || "";
  const livePlans = useLivePlans();
  const plan = livePlans.find((p) => p.id === planTier) || planFor(planTier);

  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const cardDigits = cardNumber.replace(/\D/g, "");
  const brand = useMemo(() => detectBrand(cardDigits), [cardDigits]);
  const canPay = cardDigits.length === 16 && /^\d{2}\/\d{2}$/.test(expiry) && cvc.length >= 3 && name.trim().length > 1;

  async function handlePay(e: React.FormEvent) {
    e.preventDefault();
    if (!canPay || loading) return;
    setLoading(true);
    setError(null);
    try {
      await confirmDemoPayment(sessionId);
      navigate(`/pricing/success?session_id=${encodeURIComponent(sessionId)}&plan_tier=${planTier}&email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof ApiError ? "Payment couldn't be confirmed. Please try again." : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen bg-canvas font-sans">
      <div className="relative hidden w-[44%] max-w-[560px] flex-col overflow-hidden bg-[#15171A] px-14 py-14 lg:flex">
        <div
          className="pointer-events-none absolute -bottom-32 -left-24 h-[460px] w-[460px] rounded-full bg-accent-500/30 blur-[130px]" />

        <Link to="/" className="relative flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-white">
            <Logo className="h-6 w-6" />
          </span>
          <span className="text-lg font-bold tracking-tight text-white">Aiaceone</span>
        </Link>

        <div className="relative mt-16 flex flex-col gap-5">
          <h1 className="max-w-[420px] font-display text-[2rem] font-600 leading-[1.2] tracking-tight text-white">
            You&apos;re one step away from your AI practice team.
          </h1>
        </div>

        <div className="relative mt-9 flex flex-col gap-4 rounded-[20px] border border-white/10 bg-white/[0.06] p-6">
          <div className="flex items-center justify-between">
            <p className="text-[15px] font-semibold text-white">{plan.name} Plan</p>
            <p className="font-display text-xl font-bold text-cyan-400">
              {plan.price}<span className="text-sm font-medium text-white/60">{plan.period}</span>
            </p>
          </div>
          <div className="flex flex-col gap-3">
            {plan.features.map((f) =>
            <div key={f} className="flex items-start gap-2.5">
                <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-400" />
                <span className="text-[13px] text-white/80">{f}</span>
              </div>
            )}
          </div>
        </div>

        <div className="relative mt-auto flex items-center gap-2 pt-8 text-xs text-white/50">
          <ShieldCheckIcon className="h-3.5 w-3.5" /> Test mode — no card data leaves your browser
        </div>
      </div>

      <div className="flex flex-1 flex-col">
        <div className="flex h-16 items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2.5 lg:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-sand-200 bg-white">
              <Logo className="h-5 w-5" />
            </span>
            <span className="text-[15px] font-bold tracking-tight text-ink">Aiaceone</span>
          </Link>
          <div className="ml-auto flex items-center gap-1.5">
            {[1, 2, 3].map((i) =>
            <span key={i} className={`h-1.5 w-8 rounded-full ${i === 1 ? "bg-accent-500" : "bg-sand-200"}`} />
            )}
          </div>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 py-8">
          <div className="w-full max-w-[440px] overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_20px_50px_-20px_rgba(11,29,38,0.25)]">
            <div className="px-8 pb-2 pt-8">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-2xl font-600 text-ink">Secure checkout</h2>
                <span className="flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-bold text-success">
                  <ShieldCheckIcon className="h-3 w-3" /> 256-bit SSL
                </span>
              </div>
            </div>

            <form onSubmit={handlePay} className="space-y-4 px-8 py-6">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                  <MailIcon className="h-3.5 w-3.5" /> Email
                </span>
                <div className="flex items-center justify-between rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5">
                  <span className="truncate text-sm text-ink-soft">{email}</span>
                  <CheckIcon className="h-4 w-4 shrink-0 text-success" />
                </div>
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Card information</span>
                <div className="flex items-center gap-2 rounded-t-xl border border-b-0 border-accent-500/50 bg-white px-3.5 py-2.5 transition-colors focus-within:border-accent-500">
                  <input
                    autoFocus
                    inputMode="numeric"
                    value={cardNumber}
                    onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
                    placeholder="1234 1234 1234 1234"
                    className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />

                  <div className="flex shrink-0 gap-1">
                    {(["visa", "mastercard", "amex", "discover"] as const).map((b) =>
                    <CardBrandBadge key={b} brand={b} active={brand === b} />
                    )}
                  </div>
                </div>
                <div className="flex rounded-b-xl border border-accent-500/50 bg-white transition-colors focus-within:border-accent-500">
                  <div className="flex w-1/2 items-center gap-1.5 border-r border-sand-200 px-3.5 py-2.5">
                    <CalendarIcon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
                    <input
                      inputMode="numeric"
                      value={expiry}
                      onChange={(e) => setExpiry(formatExpiry(e.target.value))}
                      placeholder="MM / YY"
                      className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />

                  </div>
                  <div className="flex w-1/2 items-center gap-1.5 px-3.5 py-2.5">
                    <ShieldCheckIcon className="h-3.5 w-3.5 shrink-0 text-ink-muted" />
                    <input
                      inputMode="numeric"
                      value={cvc}
                      onChange={(e) => setCvc(e.target.value.replace(/\D/g, "").slice(0, 4))}
                      placeholder="CVC"
                      className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-muted" />

                  </div>
                </div>
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-muted">Name on card</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Full name"
                  className="w-full rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition-colors focus:border-accent-500/50 focus:bg-white" />

              </label>

              {error && <p className="text-sm text-danger">{error}</p>}

              <button
                type="submit"
                disabled={!canPay || loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent-500 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-accent-700 disabled:cursor-not-allowed disabled:opacity-40">

                {loading ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <LockIcon className="h-3.5 w-3.5" />}
                Pay {plan.price}{plan.period} and activate
              </button>

              <div className="flex items-center justify-center gap-4 pt-1 text-[11px] text-ink-muted">
                <span className="flex items-center gap-1"><CheckCircle2Icon className="h-3 w-3 text-success" /> Cancel anytime</span>
                <span className="flex items-center gap-1"><CheckCircle2Icon className="h-3 w-3 text-success" /> No setup fees</span>
              </div>
            </form>

            <div className="border-t border-sand-200 bg-sand-50 px-8 py-4">
              <div className="flex items-center justify-center gap-1.5 text-xs text-ink-muted">
                <LockIcon className="h-3 w-3" />
                <span>Powered by</span>
                <span className="font-display text-sm font-bold italic text-[#635BFF]">stripe</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>);

}
