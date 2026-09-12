import { Link } from "react-router-dom";
import { CompassIcon, HomeIcon } from "lucide-react";

// App-level 404 catch-all. Before this existed, ANY unknown URL (a typo like
// /staff, a retired link, a broken bookmark) rendered a silent blank page —
// which is exactly what was confusing during the cache-broken testing.
// Now every unmatched path gets a real branded page with a way home.
export function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-sand-50 px-4 py-16">
      <div className="w-full max-w-md rounded-3xl border border-sand-200 bg-white p-8 text-center shadow-[0_4px_20px_rgba(15,23,42,0.08)]">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink/[0.04] text-ink-soft">
          <CompassIcon className="h-6 w-6" />
        </span>
        <h1 className="mt-4 font-display text-3xl font-bold text-ink">404</h1>
        <p className="mt-1 font-display text-xl font-semibold text-ink">Page not found</p>
        <p className="mt-2 text-sm leading-relaxed text-ink-muted">
          This address doesn&apos;t exist — it may be a typo, or the link may have changed.
          Head back home to find your way again.
        </p>
        <Link
          to="/"
          className="mt-6 inline-flex items-center justify-center gap-2 rounded-full bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600">

          <HomeIcon className="h-4 w-4" /> Back to home
        </Link>
      </div>
    </div>);

}