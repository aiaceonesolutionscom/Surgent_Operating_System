import { motion } from "framer-motion";
import { Container } from "../ui";
import { STEPS } from "../../data/steps";

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24 sm:py-32">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
            How it works
          </p>
          <h2 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
            One platform. One connected workforce.
          </h2>
          <p className="mt-4 text-lg text-ink-soft">
            Not a chatbot bolted onto your website — an orchestrated team of agents that share
            context and hand work off to each other, and to your staff.
          </p>
        </div>

        <div className="mt-16 grid gap-6 lg:grid-cols-3">
          {STEPS.map((s, i) =>
          <motion.div
            key={s.step}
            initial={{ opacity: 0, y: 28 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.6, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
            className="relative rounded-4xl border border-sand-200 bg-white p-8 shadow-soft">

              <div className="flex items-center justify-between">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-teal-50 text-teal-600">
                  <s.icon className="h-6 w-6" />
                </span>
                <span className="font-display text-4xl font-500 text-sand-300">{s.step}</span>
              </div>
              <h3 className="mt-6 text-xl font-bold text-ink">{s.title}</h3>
              <p className="mt-2 leading-relaxed text-ink-soft">{s.desc}</p>
            </motion.div>
          )}
        </div>
      </Container>
    </section>);

}
