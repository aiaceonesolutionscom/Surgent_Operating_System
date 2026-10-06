
// Inline SVG brand mark — replaces the old public/logo.png (a generic
// flaticon-style torso/spine icon that read as stock art, not a real
// wordmark). A rounded medical cross in the marketing teal, with a small
// gold node-graph accent nodding to "AI" without literally copying the
// blue reference concept at design-references/For.UI/aiaceone_logo — that
// reference uses a blue reserved for the dashboard's separate `accent`
// palette, not the marketing site's teal/sand/gold system.
export function Logo({ className = "h-5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="Aiaceone">
      <rect x="12" y="4" width="8" height="24" rx="4" className="fill-teal-600" />
      <rect x="4" y="12" width="24" height="8" rx="4" className="fill-teal-600" />
      <g className="stroke-gold" strokeWidth="1.2" strokeLinecap="round">
        <line x1="23" y1="6" x2="29" y2="10" />
        <line x1="23" y1="6" x2="25" y2="14" />
        <line x1="29" y1="10" x2="25" y2="14" />
      </g>
      <circle cx="23" cy="6" r="2" className="fill-gold" />
      <circle cx="29" cy="10" r="1.6" className="fill-gold" />
      <circle cx="25" cy="14" r="1.6" className="fill-gold" />
    </svg>
  );
}
