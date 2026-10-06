import { motion } from "framer-motion";
import { PAIN_POINT_STATS } from "../../data/painPoints";

// Sits right after the hero's opening scene, which now leads with a missed
// calls hook — this is that hook's supporting evidence. Framed as industry
// research, not Aiaceone's own results, with a visible source link per stat
// so nothing here reads as an unqualified or fabricated claim.
export function PainPointStats() {
  return (
    <section className="bg-ink py-16 text-white sm:py-20">
      <div className="mx-auto max-w-5xl px-5 sm:px-8">
        <p className="text-center text-sm font-semibold uppercase tracking-[0.18em] text-teal-300">
          The cost of a missed call
        </p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2">
          {PAIN_POINT_STATS.map((s, i) =>
          <motion.div
            key={s.stat}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-40px" }}
            transition={{ duration: 0.5, delay: i * 0.1 }}
            className="rounded-3xl border border-white/10 bg-white/[0.03] p-8 text-center">

              <p className="font-display text-6xl font-600 tracking-tight text-white">{s.stat}</p>
              <p className="mx-auto mt-3 max-w-xs text-base text-white/70">{s.label}</p>
              <a
              href={s.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block text-xs text-white/40 underline-offset-2 transition-colors hover:text-teal-300 hover:underline">

                Source: {s.source}
              </a>
            </motion.div>
          )}
        </div>
      </div>
    </section>);

}
