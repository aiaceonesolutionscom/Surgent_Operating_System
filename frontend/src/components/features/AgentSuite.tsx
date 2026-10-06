import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Link, useSearchParams } from "react-router-dom";
import { Container } from "../ui";
import { AGENT_CATEGORIES, TOTAL_AGENTS } from "../../data/agents";

export function AgentSuite() {
  const [searchParams] = useSearchParams();
  const requested = searchParams.get("category");
  const initial = AGENT_CATEGORIES.find((c) => c.id === requested)?.id || AGENT_CATEGORIES[0].id;
  const [active, setActive] = useState(initial);
  const category = AGENT_CATEGORIES.find((c) => c.id === active)!;

  return (
    <section id="agents" className="scroll-mt-24 bg-ink py-24 text-white sm:py-32">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-300">
            The agent suite
          </p>
          <h2 className="mt-3 font-display text-4xl font-500 tracking-tight sm:text-5xl">
            {TOTAL_AGENTS} agents. Every corner of your practice.
          </h2>
          <p className="mt-4 text-lg text-white/60">
            Each agent is a specialist. Together they run the full patient journey — from the
            first Instagram DM to the final recovery check-in.
          </p>
        </div>

        {/* Tabs */}
        <div className="mt-12 flex flex-wrap justify-center gap-2">
          {AGENT_CATEGORIES.map((c) => {
            const isActive = c.id === active;
            return (
              <button
                key={c.id}
                onClick={() => setActive(c.id)}
                className={`relative rounded-full px-5 py-2.5 text-sm font-semibold transition-colors ${
                isActive ? "text-ink" : "text-white/70 hover:text-white"}`
                }>

                {isActive &&
                <motion.span
                  layoutId="agentTabPill"
                  className="absolute inset-0 rounded-full bg-teal-300"
                  transition={{ type: "spring", stiffness: 400, damping: 34 }} />

                }
                <span className="relative z-10">{c.label}</span>
              </button>);

          })}
        </div>

        <p className="mt-6 text-center text-base text-white/70">{category.tagline}</p>

        {/* Grid */}
        <AnimatePresence mode="wait">
          <motion.div
            key={category.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.35 }}
            className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

            {category.agents.map((agent, i) =>
            <motion.div
              key={agent.slug}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: i * 0.05 }}>

                <Link
                to={`/agents/${agent.slug}`}
                className="group block h-full rounded-3xl border border-white/10 bg-white/[0.04] p-6 transition-colors hover:border-teal-300/40 hover:bg-white/[0.07]">

                  <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-500/15 text-teal-300 transition-colors group-hover:bg-teal-300 group-hover:text-ink">
                    <agent.icon className="h-6 w-6" />
                  </span>
                  <h3 className="mt-5 text-lg font-bold">{agent.name}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-white/60">{agent.desc}</p>
                </Link>
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </Container>
    </section>);

}
