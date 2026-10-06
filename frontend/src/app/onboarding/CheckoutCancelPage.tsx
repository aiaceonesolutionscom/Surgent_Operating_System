import { Link } from "react-router-dom";
import { XCircleIcon } from "lucide-react";
import { OnboardingLayout } from "./OnboardingLayout";

export function CheckoutCancelPage() {
  return (
    <OnboardingLayout>
      <div className="rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(11,29,38,0.05)]">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-sand-100 text-ink-muted">
          <XCircleIcon className="h-7 w-7" />
        </span>
        <p className="mt-4 text-lg font-bold text-ink">Checkout cancelled</p>
        <p className="mt-1.5 text-sm text-ink-muted">No charge was made — nothing was set up.</p>
        <div className="mt-6 flex flex-col gap-2.5">
          <Link
            to="/#pricing"
            className="rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-teal-700">

            Back to pricing
          </Link>
          <Link
            to="/demo"
            className="rounded-xl border border-sand-200 py-3 text-sm font-semibold text-ink-soft transition-colors hover:border-teal-600/40 hover:text-teal-600">

            Book a demo instead
          </Link>
        </div>
      </div>
    </OnboardingLayout>);

}
