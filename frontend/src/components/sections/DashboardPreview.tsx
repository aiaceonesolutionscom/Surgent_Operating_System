import { motion } from "framer-motion";
import { Container } from "../ui";

// Previously a hand-built <div> dashboard with fabricated KPI/chart numbers
// (86 calls, $1.24M revenue, etc. — none of it real). Replaced with an
// actual product screenshot, framed in a simple browser-chrome header so it
// reads as "a peek at the real product" rather than a raw design-tool
// export. The "Illustrative example" caption below is unchanged — it was
// honest before (this is a mockup, not your practice's live numbers) and
// stays exactly as true now that a real screenshot fills the frame.
export function DashboardPreview() {
  return (
    <section className="py-24 sm:py-32">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
            Analytics dashboard
          </p>
          <h2 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
            See exactly what your agents are doing.
          </h2>
          <p className="mt-4 text-lg text-ink-soft">
            Every call, booking, procedure, and dollar — measured in one place, in real time.
          </p>
          <p className="mt-2 text-sm text-ink-muted">
            Illustrative example — your dashboard reflects your practice's real numbers.
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.7 }}
          className="mx-auto mt-14 max-w-5xl overflow-hidden rounded-4xl border border-sand-200 bg-white shadow-lift">

          <div className="flex items-center gap-1.5 border-b border-sand-200 bg-sand-50 px-5 py-3.5">
            <span className="h-2.5 w-2.5 rounded-full bg-sand-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-sand-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-sand-300" />
          </div>
          <div className="aspect-[16/10] overflow-hidden">
            <img
              src="/screenshots/advanced-analytics.png"
              alt="Aiaceone analytics dashboard showing revenue projections and performance metrics"
              className="h-full w-full object-cover object-top" />
          </div>
        </motion.div>
      </Container>
    </section>);

}
