import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { LockIcon, Loader2Icon, ShieldCheckIcon, MailIcon, CheckIcon, CheckCircle2Icon, AlertTriangleIcon } from "lucide-react";
import { Logo } from "../../components/ui";
import { planFor } from "../dashboard/plan/plan";
import { useLivePlans } from "../../hooks/useLivePlans";
import type { PlanTier } from "../../data/planTiers";
import { createCheckoutSession } from "../../api/commerce";
import { ApiError } from "../../api/client";

// --- Stripe.js -----------------------------------------------------------------
// Loaded straight from Stripe (never bundled or self-hosted - PCI requirement),
// and only on this page. The "dahlia" build is the one that provides
// initCheckoutFormSdk(), the embedded payment form.
const STRIPE_JS_URL = "https://js.stripe.com/dahlia/stripe.js";

interface StripeFormActions {
  confirm: (args: { formConfirmEvent: unknown }) => Promise<unknown>;
}
interface StripeForm {
  mount: (selector: string) => void;
  unmount?: () => void;
  destroy?: () => void;
  on: (event: "confirm", handler: (event: unknown) => void | Promise<void>) => void;
}
interface StripeCheckout {
  createForm: (options: { layout: "expanded" | "compact" }) => StripeForm;
  loadActions: () => Promise<{ type: string; actions: StripeFormActions }>;
}
interface StripeInstance {
  initCheckoutFormSdk: (options: { clientSecret: string; appearance: unknown }) => StripeCheckout;
}
type StripeFactory = (key: string, options: { betas: string[] }) => StripeInstance;

declare global {
  interface Window {
    Stripe?: StripeFactory;
  }
}

let stripeJsPromise: Promise<StripeFactory> | null = null;

function loadStripeJs(): Promise<StripeFactory> {
  if (window.Stripe) return Promise.resolve(window.Stripe);
  if (!stripeJsPromise) {
    stripeJsPromise = new Promise<StripeFactory>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = STRIPE_JS_URL;
      script.async = true;
      script.onload = () => (window.Stripe ? resolve(window.Stripe) : reject(new Error("Stripe.js loaded without Stripe")));
      script.onerror = () => {
        stripeJsPromise = null; // allow a retry
        reject(new Error("Couldn't load Stripe.js"));
      };
      document.head.appendChild(script);
    });
  }
  return stripeJsPromise;
}

// Configured in Stripe's Checkout Studio - passed through as-is.
const STRIPE_APPEARANCE = {
  theme: "stripe",
  labels: "auto",
  inputs: "spaced",
  variables: {
    borderRadius: "4px",
    colorBackground: "#ffffff",
    colorDanger: "#df1b41",
    colorPrimary: "#0570de",
    colorSuccess: "#00c853",
    colorText: "#30313d",
    fontFamily: "default",
    fontSizeBase: "16px",
    spacingUnit: "4px"
  }
};

const publishableKey = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY as string | undefined;
const isTestMode = Boolean(publishableKey?.startsWith("pk_test_"));

// The payment step of the signup flow. Our own summary (plan, price, what's
// included) sits beside Stripe's embedded payment form; card details are typed
// into Stripe's iframe and never touch our page or servers. After Stripe
// confirms, it sends the browser to /pricing/success (the return_url the backend
// put on the session), which waits for the webhook to mark the signup paid.
export function CheckoutPage() {
  const [params] = useSearchParams();
  const planTier = (params.get("plan_tier") as PlanTier) || "practice";
  const email = params.get("email") || "";
  const livePlans = useLivePlans();
  const plan = livePlans.find((p) => p.id === planTier) || planFor(planTier);

  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const started = useRef<number>(-1);

  useEffect(() => {
    // one session per attempt, even if React re-runs the effect
    if (started.current === attempt) return;
    started.current = attempt;

    let cancelled = false;
    let form: StripeForm | null = null;
    setReady(false);
    setError(null);

    (async () => {
      try {
        if (!publishableKey) throw new Error("not-configured");

        const [session, Stripe] = await Promise.all([createCheckoutSession(email || undefined, planTier as "solo" | "practice"), loadStripeJs()]);
        if (cancelled) return;

        const stripe = Stripe(publishableKey, { betas: ["custom_checkout_payment_form_1"] });
        const checkout = stripe.initCheckoutFormSdk({ clientSecret: session.client_secret, appearance: STRIPE_APPEARANCE });
        form = checkout.createForm({ layout: "expanded" });
        form.mount("#checkout-form");

        const loaded = await checkout.loadActions();
        if (cancelled) return;
        if (loaded.type === "success") {
          form.on("confirm", async (event) => {
            try {
              await loaded.actions.confirm({ formConfirmEvent: event });
            } catch (confirmError) {
              console.error("Payment confirmation error:", confirmError);
              setError("We couldn't confirm your payment. Please check your details and try again.");
            }
          });
        }
        setReady(true);
      } catch (err) {
        if (cancelled) return;
        console.error("Checkout failed to start:", err);
        if (err instanceof Error && err.message === "not-configured") {
          setError("Online checkout isn't available yet. Please contact us and we'll set you up.");
        } else if (err instanceof ApiError && err.status === 503) {
          setError("Online checkout isn't available yet. Please contact us and we'll set you up.");
        } else {
          setError("We couldn't start checkout. Please try again.");
        }
      }
    })();

    return () => {
      cancelled = true;
      try {
        form?.unmount?.();
        form?.destroy?.();
      } catch {
        // already torn down
      }
    };
  }, [attempt, email, planTier]);

  return (
    <div className="flex min-h-screen bg-canvas font-sans">
      <div className="relative hidden w-[44%] max-w-[560px] flex-col overflow-hidden bg-[#15171A] px-14 py-14 lg:flex">
        <div className="pointer-events-none absolute -bottom-32 -left-24 h-[460px] w-[460px] rounded-full bg-accent-500/30 blur-[130px]" />

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
          <ShieldCheckIcon className="h-3.5 w-3.5" /> Card details go straight to Stripe — they never touch our servers
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

        <div className="flex flex-1 items-start justify-center px-4 py-8 sm:items-center sm:px-6">
          <div className="w-full max-w-[520px] overflow-hidden rounded-3xl border border-sand-200 bg-white shadow-[0_20px_50px_-20px_rgba(11,29,38,0.25)]">
            <div className="px-6 pb-2 pt-7 sm:px-8 sm:pt-8">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-2xl font-600 text-ink">Secure checkout</h2>
                <span className="flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-bold text-success">
                  <ShieldCheckIcon className="h-3 w-3" /> 256-bit SSL
                </span>
              </div>
              <p className="mt-1 text-sm text-ink-muted">
                {plan.name} plan · {plan.price}{plan.period}
              </p>
            </div>

            <div className="space-y-5 px-6 py-6 sm:px-8">
              {email &&
              <div>
                  <span className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                    <MailIcon className="h-3.5 w-3.5" /> Receipt sent to
                  </span>
                  <div className="flex items-center justify-between rounded-xl border border-sand-200 bg-canvas px-3.5 py-2.5">
                    <span className="truncate text-sm text-ink-soft">{email}</span>
                    <CheckIcon className="h-4 w-4 shrink-0 text-success" />
                  </div>
                </div>
              }

              {isTestMode && !error &&
              <p className="rounded-xl border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-xs text-ink-soft">
                  <span className="font-semibold">Test mode.</span> Use card <span className="font-mono">4242 4242 4242 4242</span>, any future expiry, any CVC. No real money is charged.
                </p>
              }

              {/* Stripe mounts its payment form into this element. */}
              <div id="checkout-form" className={ready ? "" : "hidden"} />

              {!ready && !error &&
              <div className="flex flex-col items-center gap-3 py-10 text-ink-muted">
                  <Loader2Icon className="h-6 w-6 animate-spin text-accent-500" />
                  <p className="text-sm">Loading secure payment form…</p>
                </div>
              }

              {error &&
              <div className="rounded-2xl border border-danger/25 bg-danger/5 p-5 text-center">
                  <AlertTriangleIcon className="mx-auto h-6 w-6 text-danger" />
                  <p className="mt-2 text-sm text-ink">{error}</p>
                  {publishableKey &&
                <button
                  type="button"
                  onClick={() => setAttempt((n) => n + 1)}
                  className="mt-3 rounded-xl bg-accent-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-accent-700">
                      Try again
                    </button>
                }
                  <Link to="/#pricing" className="mt-3 block text-xs font-semibold text-accent-700 underline-offset-4 hover:underline">
                    Back to pricing
                  </Link>
                </div>
              }

              {ready &&
              <div className="flex items-center justify-center gap-4 pt-1 text-[11px] text-ink-muted">
                  <span className="flex items-center gap-1"><CheckCircle2Icon className="h-3 w-3 text-success" /> Cancel anytime</span>
                  <span className="flex items-center gap-1"><CheckCircle2Icon className="h-3 w-3 text-success" /> No setup fees</span>
                </div>
              }
            </div>

            <div className="border-t border-sand-200 bg-sand-50 px-8 py-4">
              <p className="mb-3 text-center text-xs text-ink-soft">
                Not ready to pay yet?{" "}
                <Link to="/sign-up" className="font-semibold text-teal-700 underline-offset-4 hover:underline">
                  Request free access
                </Link>{" "}
                - we&apos;ll set your organization up personally first, no card needed.
              </p>
              <div className="flex items-center justify-center gap-1.5 text-xs text-ink-muted">
                <LockIcon className="h-3 w-3" />
                <span>Payments powered by</span>
                <span className="font-display text-sm font-bold italic text-[#635BFF]">stripe</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>);

}
