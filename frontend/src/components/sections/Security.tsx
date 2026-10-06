import { motion } from "framer-motion";
import { ShieldCheckIcon } from "lucide-react";
import { Container } from "../ui";
import { SECURITY_ITEMS } from "../../data/features";

export function Security() {
  return (
    <section id="security" className="scroll-mt-24 py-24 sm:py-32">
      <Container>
        <div className="rounded-4xl border border-teal-100 bg-teal-50/50 p-8 sm:p-14">
          <div className="mx-auto max-w-2xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-sm font-semibold text-teal-700 shadow-soft">
              <ShieldCheckIcon className="h-4 w-4" /> Trust & compliance
            </span>
            <h2 className="mt-5 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              Patient data, treated like patient data.
            </h2>
            <p className="mt-4 text-lg text-ink-soft">
              Automation in healthcare only works if it's safe. Every agent operates inside strict
              clinical and privacy guardrails — with your team always in control.
            </p>
          </div>

          <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {SECURITY_ITEMS.map((it, i) =>
            <motion.div
              key={it.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="rounded-3xl bg-white p-6 shadow-soft">

                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal-50 text-teal-600">
                  <it.icon className="h-5.5 w-5.5" />
                </span>
                <h3 className="mt-4 font-bold text-ink">{it.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{it.desc}</p>
              </motion.div>
            )}
          </div>
        </div>
      </Container>
    </section>);

}
