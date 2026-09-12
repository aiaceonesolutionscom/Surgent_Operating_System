import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "lucide-react";
import { Navbar, Footer } from "../components/layout";
import { AgentSuite } from "../components/features";
import { CTA } from "../components/cta";
import { Container } from "../components/ui";
import { AGENT_CATEGORIES, TOTAL_AGENTS } from "../data/agents";

export function AgentsPage() {
  return (
    <div className="min-h-screen w-full bg-canvas font-sans text-ink">
      <Navbar />
      <main className="pt-28 pb-24">
        <Container>
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition-colors hover:text-teal-600">

            <ArrowLeftIcon className="h-4 w-4" />
            Back to home
          </Link>

          <div className="mx-auto mt-10 max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
              {TOTAL_AGENTS} specialist agents, one team
            </p>
            <h1 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              Every corner of your practice, covered
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-ink-soft">
              Each agent is a specialist in one job — answering calls, qualifying
              leads, writing notes, chasing invoices, following up recovery. Together
              they run the full patient journey, from the first Instagram DM to the
              final recovery check-in.
            </p>
          </div>

          <div className="mx-auto mt-10 grid max-w-3xl gap-4 sm:grid-cols-4">
            {AGENT_CATEGORIES.map((c) => (
              <div key={c.id} className="rounded-3xl border border-sand-200 bg-white p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal-600">{c.label}</p>
                <p className="mt-2 text-sm leading-relaxed text-ink-soft">{c.tagline}</p>
              </div>
            ))}
          </div>
        </Container>

        <div className="mt-16">
          <AgentSuite />
        </div>
        <CTA />
      </main>
      <Footer />
    </div>);

}