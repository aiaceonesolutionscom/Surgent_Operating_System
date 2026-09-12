import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeftIcon, CheckIcon } from "lucide-react";
import { Navbar, Footer } from "../components/layout";
import { Button, Container } from "../components/ui";
import { AGENT_CATEGORIES, AGENTS_BY_SLUG } from "../data/agents";

const AGENT_LOGOS: Record<string, string> = {
  receptionist: "/agent-logos/receptionist.png"
};

export function AgentDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const agent = slug ? AGENTS_BY_SLUG[slug] : undefined;

  if (!agent) return <Navigate to="/agents" replace />;

  const category = AGENT_CATEGORIES.find((c) => c.id === agent.categoryId);

  return (
    <div className="min-h-screen w-full bg-canvas font-sans text-ink">
      <Navbar />
      <main className="pt-28 pb-24">
        <Container className="max-w-4xl">
          <Link
            to="/agents"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft transition-colors hover:text-teal-600">

            <ArrowLeftIcon className="h-4 w-4" />
            Back to all agents
          </Link>

          {/* Hero */}
          <div className="mt-8 flex items-start gap-5">
            <span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-teal-50 text-teal-600">
              {AGENT_LOGOS[agent.slug] ? (
                <img src={AGENT_LOGOS[agent.slug]} alt={agent.name} className="h-10 w-10 object-contain" />
              ) : (
                <agent.icon className="h-8 w-8" />
              )}
            </span>
            <div>
              {category &&
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
                  {category.label}
                </p>
              }
              <h1 className="mt-1 font-display text-3xl font-500 tracking-tight text-ink sm:text-4xl">
                {agent.name}
              </h1>
            </div>
          </div>

          <p className="mt-5 text-lg font-medium text-ink">{agent.tagline}</p>
          <p className="mt-3 text-lg leading-relaxed text-ink-soft">{agent.desc}</p>
          <p className="mt-4 text-base leading-relaxed text-ink-soft">{agent.howItWorks}</p>

          {/* Outcome stat */}
          <div className="mt-8 flex items-center gap-4 rounded-3xl border border-teal-100 bg-teal-50/60 p-6">
            <span className="font-display text-4xl font-bold tracking-tight text-teal-600">
              {agent.outcome.stat}
            </span>
            <span className="text-base text-ink-soft">{agent.outcome.label}</span>
          </div>

          {/* Capabilities + use cases */}
          <div className="mt-10 grid gap-8 sm:grid-cols-2">
            <div>
              <h2 className="font-display text-xl font-600 tracking-tight text-ink">What it does</h2>
              <ul className="mt-4 space-y-3">
                {agent.capabilities.map((cap) =>
                <li key={cap} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-soft">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-100 text-teal-600">
                      <CheckIcon className="h-3 w-3" />
                    </span>
                    {cap}
                  </li>
                )}
              </ul>
            </div>
            <div>
              <h2 className="font-display text-xl font-600 tracking-tight text-ink">Where clinics use it</h2>
              <ul className="mt-4 space-y-3">
                {agent.useCases.map((useCase) =>
                <li key={useCase} className="flex items-start gap-2.5 text-sm leading-relaxed text-ink-soft">
                    <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-teal-500" />
                    {useCase}
                  </li>
                )}
              </ul>
            </div>
          </div>

          <div className="mt-12 flex flex-wrap gap-3">
            <Button to="/demo" arrow>Book a demo</Button>
            <Button to="/agents" variant="ghost">See all agents</Button>
          </div>
        </Container>
      </main>
      <Footer />
    </div>);

}