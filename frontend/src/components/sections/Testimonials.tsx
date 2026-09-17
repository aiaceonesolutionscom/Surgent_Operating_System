import React from "react";
import { motion } from "framer-motion";
import { StarIcon } from "lucide-react";
import { Container } from "../ui";
import { TESTIMONIALS } from "../../data/testimonials";

export function Testimonials() {
  return (
    <section id="results" className="scroll-mt-24 bg-white py-24 sm:py-32">
      <Container>
        <div className="flex flex-col items-start gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
              Loved by practices
            </p>
            <h2 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              Surgeons focus on surgery. Agents do the rest.
            </h2>
          </div>
        </div>

        <p className="mt-3 text-sm text-ink-muted">
          Illustrative feedback from early pilot conversations — not verbatim reviews.
        </p>

        <div className="mt-14 grid gap-6 lg:grid-cols-3">
          {TESTIMONIALS.map((t, i) =>
          <motion.figure
            key={t.name}
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.6, delay: i * 0.1 }}
            className="flex flex-col rounded-4xl border border-sand-200 bg-canvas p-7 shadow-soft">

              <div className="flex gap-0.5 text-gold">
                {Array.from({ length: 5 }).map((_, s) =>
              <StarIcon key={s} className="h-4.5 w-4.5 fill-current" />
              )}
              </div>
              <blockquote className="mt-4 flex-1 text-lg leading-relaxed text-ink">
                “{t.quote}”
              </blockquote>
              <figcaption className="mt-6 flex items-center gap-3 border-t border-sand-200 pt-5">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-teal-50 text-sm font-bold text-teal-700">
                  {t.initials}
                </span>
                <div>
                  <p className="font-bold text-ink">{t.name}</p>
                  <p className="text-sm text-ink-muted">{t.role}</p>
                </div>
              </figcaption>
            </motion.figure>
          )}
        </div>
      </Container>
    </section>);

}
