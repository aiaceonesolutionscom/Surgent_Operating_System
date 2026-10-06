import { Link } from "react-router-dom";
import { Container, Logo } from "../ui";
import { FOOTER_COLUMNS, type FooterLink } from "../../data/footer";

function FooterLinkItem({ link }: { link: FooterLink }) {
  const className = "text-sm text-ink-muted transition-colors hover:text-teal-600";
  if (link.to) {
    return <Link to={link.to} className={className}>{link.label}</Link>;
  }
  return <a href={link.href} className={className}>{link.label}</a>;
}

export function Footer() {
  return (
    <footer className="border-t border-sand-200 bg-white">
      <Container className="py-16">
        <div className="grid gap-10 lg:grid-cols-[1.4fr_1fr_1fr]">
          <div>
            <Link to="/" className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-sand-200 bg-white shadow-soft">
                <Logo className="h-6 w-6" />
              </span>
              <span className="text-lg font-bold tracking-tight text-ink">
                <span className="text-teal-500">Ai</span>aceone
              </span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-ink-muted">
              The autonomous AI workforce for plastic surgery and aesthetic practices. Every patient
              touchpoint, fully automated.
            </p>
          </div>

          {FOOTER_COLUMNS.map((col) =>
          <div key={col.title}>
              <h4 className="text-sm font-bold uppercase tracking-wide text-ink">{col.title}</h4>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) =>
              <li key={l.label}>
                    <FooterLinkItem link={l} />
                  </li>
              )}
              </ul>
            </div>
          )}
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-sand-200 pt-6 sm:flex-row">
          <p className="text-sm text-ink-muted">
            © {new Date().getFullYear()} Aiaceone. All rights reserved.
          </p>
          <a href="/#security" className="text-sm text-ink-muted hover:text-teal-600">HIPAA</a>
        </div>
        <p className="mt-6 text-center text-xs leading-relaxed text-ink-muted sm:text-left">
          Screening agents provide informational screening only and do not provide medical diagnoses.
          All clinical decisions are made by licensed surgeons.
        </p>
      </Container>
    </footer>);

}
