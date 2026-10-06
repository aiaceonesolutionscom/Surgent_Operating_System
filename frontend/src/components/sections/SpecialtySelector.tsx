import { motion } from "framer-motion";
import { PRACTICE_TYPES } from "../../data/practiceTypes";

// Replaces the old TrustBar, which rendered the same 5 categories as plain
// text with no visual weight — the weakest, plainest section on the page.
// Same honest content (practice types Aiaceone actually serves), rebuilt as
// a proper icon+label tile grid.
export function SpecialtySelector() {
  return (
    <section className="py-16 sm:py-20">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <p className="text-center text-xs font-semibold uppercase tracking-[0.18em] text-ink-muted">
          Built for every kind of aesthetic practice
        </p>
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {PRACTICE_TYPES.map((p, i) =>
          <motion.div
            key={p.label}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: i * 0.06 }}
            className="flex flex-col items-center gap-3 rounded-3xl border border-sand-200 bg-white px-4 py-6 text-center shadow-soft">

              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal-50 text-teal-600">
                <p.icon className="h-5.5 w-5.5" />
              </span>
              <span className="text-sm font-semibold text-ink-soft">{p.label}</span>
            </motion.div>
          )}
        </div>
      </div>
    </section>);

}
