import { motion } from "framer-motion";
import { CameraIcon, HeartPulseIcon, CheckIcon, ShieldAlertIcon } from "lucide-react";
import { Container } from "../ui";
import { SCREENING_FEATURES, RECOVERY_STATS } from "../../data/features";

export function FeatureShowcase() {
  return (
    <section id="platform" className="scroll-mt-24 py-24 sm:py-32">
      <Container className="space-y-28">
        {/* Photo analysis / screening */}
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, x: -24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="relative order-2 lg:order-1">

            <img
              src="/b939467f-8a25-47ed-957f-681af02fa420.jpg"
              alt="Surgeon reviewing patient screening on a tablet"
              className="w-full rounded-4xl border border-sand-200 object-cover shadow-lift" />

            <div className="absolute -right-4 bottom-6 flex items-center gap-2.5 rounded-2xl border border-sand-200 bg-white px-4 py-3 shadow-soft">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
                <ShieldAlertIcon className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-bold text-ink">Screening only</p>
                <p className="text-xs text-ink-muted">Never a diagnosis</p>
              </div>
            </div>
          </motion.div>

          <div className="order-1 lg:order-2">
            <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-sm font-semibold text-teal-700">
              <CameraIcon className="h-4 w-4" /> Consultation & screening
            </span>
            <h2 className="mt-4 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              Qualify patients before they arrive.
            </h2>
            <p className="mt-4 text-lg text-ink-soft">
              Patients submit photos and history, and the screening agents structure everything for
              your surgeon to review — flagging candidacy and risk factors while making it explicit
              that this is <strong className="text-ink">screening, not a diagnosis</strong>.
            </p>
            <ul className="mt-6 space-y-3">
              {SCREENING_FEATURES.map((t) =>
              <li key={t} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-500 text-white">
                    <CheckIcon className="h-3.5 w-3.5" strokeWidth={3} />
                  </span>
                  <span className="text-ink-soft">{t}</span>
                </li>
              )}
            </ul>
          </div>
        </div>

        {/* Recovery */}
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full bg-teal-50 px-3 py-1 text-sm font-semibold text-teal-700">
              <HeartPulseIcon className="h-4 w-4" /> Post-surgery care
            </span>
            <h2 className="mt-4 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              Recovery that runs itself — safely.
            </h2>
            <p className="mt-4 text-lg text-ink-soft">
              From the moment a patient leaves, the care agents keep them on track: timed check-ins,
              medication reminders, wound-care guidance, and healing photos — with instant triage
              escalation to your team the moment something looks off.
            </p>
            <div className="mt-6 grid grid-cols-2 gap-4">
              {RECOVERY_STATS.map((s) =>
              <div key={s.v} className="rounded-2xl border border-sand-200 bg-white p-5 shadow-soft">
                  <p className="font-display text-3xl font-600 text-teal-600">{s.k}</p>
                  <p className="mt-1 text-sm text-ink-muted">{s.v}</p>
                </div>
              )}
            </div>
            <p className="mt-3 text-sm text-ink-muted">Example targets — actual results vary by practice.</p>
          </div>

          <motion.div
            initial={{ opacity: 0, x: 24 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="rounded-4xl border border-sand-200 bg-white p-6 shadow-lift">

            <div className="flex items-center justify-between border-b border-sand-100 pb-4">
              <p className="font-semibold text-ink">Recovery Progress · Maya R.</p>
              <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700">
                Day 7 · On track
              </span>
            </div>
            <div className="mt-5 space-y-4">
              <ProgressRow label="Healing score" value={86} />
              <ProgressRow label="Medication adherence" value={100} />
              <ProgressRow label="Check-ins completed" value={72} />
            </div>
            <div className="mt-5 flex items-center gap-3 rounded-2xl bg-amber-50 p-3">
              <ShieldAlertIcon className="h-5 w-5 shrink-0 text-amber-600" />
              <p className="text-sm text-amber-800">
                Emergency Triage flagged mild swelling — routed to Dr. Reyes for review.
              </p>
            </div>
          </motion.div>
        </div>
      </Container>
    </section>);

}

function ProgressRow({ label, value }: {label: string;value: number;}) {
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-ink-soft">{label}</span>
        <span className="font-semibold text-ink">{value}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-sand-100">
        <motion.div
          initial={{ width: 0 }}
          whileInView={{ width: `${value}%` }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: "easeOut" }}
          className="h-full rounded-full bg-teal-500" />

      </div>
    </div>);

}
