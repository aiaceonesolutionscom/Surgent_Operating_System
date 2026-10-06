import { motion } from "framer-motion";
import type { IconType } from "react-icons";
import { Button } from "../ui";
import ElasticMesh from "../elastic/ElasticMesh";
import ClickSpark from "../elastic/ClickSpark";

export type Chip = string | {label: string;icon: IconType;color?: string;};

interface SectionTeaserProps {
  id: string;
  image?: string;
  eyebrow: string;
  title: string;
  body: string;
  chips: Chip[];
  ctaLabel: string;
  ctaHref: string;
  dark?: boolean;
  reverse?: boolean;
}

export function SectionTeaser({
  id,
  image,
  eyebrow,
  title,
  body,
  chips,
  ctaLabel,
  ctaHref,
  dark,
  reverse
}: SectionTeaserProps) {
  const showImage = Boolean(image);
  return (
    <section
      id={id}
      className={`scroll-mt-24 py-24 sm:py-32 ${dark ? "bg-ink text-white" : ""}`}>

      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className={`aspect-[4/3] overflow-hidden rounded-4xl border ${reverse ? "lg:order-2" : ""} ${
            dark ? "border-white/10" : "border-sand-200"} ${
            showImage ? "" : "bg-gradient-to-br from-teal-600 via-ink to-[#C9A24B]"}`
            }>

            {showImage &&
            <ClickSpark
              sparkColor={dark ? "#ffffff" : "#0d9488"}
              sparkSize={9}
              sparkRadius={18}
              sparkCount={10}
              duration={450}>
              <ElasticMesh
                image={image}
                interaction="hover"
                borderRadius={0}
                showGrid={false}
                shading={0.45}
                tilt={12}
                className="h-full w-full" />
            </ClickSpark>
            }
          </motion.div>

          <div className={reverse ? "lg:order-1" : ""}>
            <p
              className={`text-sm font-semibold uppercase tracking-[0.18em] ${
              dark ? "text-teal-300" : "text-teal-600"}`
              }>

              {eyebrow}
            </p>
            <h2
              className={`mt-3 font-display text-4xl font-500 tracking-tight sm:text-5xl ${
              dark ? "text-white" : "text-ink"}`
              }>

              {title}
            </h2>
            <p className={`mt-4 text-lg ${dark ? "text-white/60" : "text-ink-soft"}`}>
              {body}
            </p>

            <div className="mt-6 flex flex-wrap gap-2">
              {chips.map((chip, i) => {
                const isIcon = typeof chip !== "string";
                const label = isIcon ? chip.label : chip;
                return (
                  <motion.span
                    key={label}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.4, delay: i * 0.06 }}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-sm font-medium ${
                    dark ?
                    "border-white/15 bg-white/[0.06] text-white/80" :
                    "border-sand-200 bg-white text-ink-soft"}`
                    }>

                    {isIcon &&
                    <chip.icon className="h-3.5 w-3.5" style={{ color: chip.color }} />
                    }
                    {label}
                  </motion.span>);

              })}
            </div>

            <Button to={ctaHref} arrow className="mt-8 shadow-lift">
              {ctaLabel}
            </Button>
          </div>
        </div>
      </div>
    </section>);

}
