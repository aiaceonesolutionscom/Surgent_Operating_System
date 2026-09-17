import { useState } from "react";
import { motion } from "framer-motion";
import { CheckIcon } from "lucide-react";
import { Button, Container } from "../ui";
import { useLivePlans } from "../../hooks/useLivePlans";
import { CheckoutModal } from "./CheckoutModal";

export function Pricing() {
  const [checkoutPlan, setCheckoutPlan] = useState<{ id: "practice"; name: string } | null>(null);
  const PLANS = useLivePlans();

  return (
    <section id="pricing" className="scroll-mt-24 py-24 sm:py-32">
      <Container>
        <div id="pricing-heading" className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
            Pricing
          </p>
          <h2 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
            One flat fee. An entire team of agents.
          </h2>
          <p className="mt-4 text-lg text-ink-soft">
            No per-seat billing. No per-call surprises. Cancel anytime.
          </p>
        </div>

        <div className="mx-auto mt-14 grid max-w-4xl items-stretch gap-6 sm:grid-cols-2">
          {PLANS.map((p, i) =>
          <motion.div
            key={p.name}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.55, delay: i * 0.1 }}
            className={`relative flex flex-col rounded-4xl border p-8 ${
            p.highlight ?
            "border-teal-500 bg-ink text-white shadow-lift" :
            "border-sand-200 bg-white text-ink shadow-soft"}`
            }>

              {p.highlight &&
            <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-teal-300 px-4 py-1 text-xs font-bold uppercase tracking-wide text-ink">
                  Most popular
                </span>
            }
              <h3 className="text-xl font-bold">{p.name}</h3>
              <p className={`mt-1 text-sm ${p.highlight ? "text-white/60" : "text-ink-muted"}`}>
                {p.tagline}
              </p>
              <div className="mt-6 flex items-baseline gap-1">
                <span className="font-display text-4xl font-600">{p.price}</span>
                <span className={p.highlight ? "text-white/60" : "text-ink-muted"}>{p.period}</span>
              </div>

              {p.id === "enterprise" ?
            <Button to="/demo" variant="ink" arrow className="mt-6 w-full">
                  Talk to sales
                </Button> :

            <Button
              onClick={() => setCheckoutPlan({ id: "practice", name: p.name })}
              variant={p.highlight ? "cream" : "ink"}
              arrow
              className="mt-6 w-full">

                  Start free trial
                </Button>
            }

              <ul className="mt-8 space-y-3">
                {p.features.map((f) =>
              <li key={f} className="flex items-start gap-3">
                    <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
                  p.highlight ? "bg-teal-300 text-ink" : "bg-teal-500 text-white"}`
                  }>

                      <CheckIcon className="h-3.5 w-3.5" strokeWidth={3} />
                    </span>
                    <span className={p.highlight ? "text-white/80" : "text-ink-soft"}>{f}</span>
                  </li>
              )}
              </ul>
            </motion.div>
          )}
        </div>
      </Container>
      {checkoutPlan &&
      <CheckoutModal planId={checkoutPlan.id} planName={checkoutPlan.name} onClose={() => setCheckoutPlan(null)} />
      }
    </section>);

}
