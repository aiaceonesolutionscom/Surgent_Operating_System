




import { motion } from "framer-motion";
import { FaInstagram, FaWhatsapp, FaFacebook, FaLinkedin } from "react-icons/fa6";
import { Container } from "../ui";

export const CHANNELS = [
{ icon: FaInstagram, name: "Instagram", detail: "DMs, comments & story replies", color: "#D6336C" },
{ icon: FaWhatsapp, name: "WhatsApp", detail: "Chats, reminders & follow-ups", color: "#25D366" },
{ icon: FaFacebook, name: "Facebook", detail: "Messenger & lead ads", color: "#1877F2" },
{ icon: FaLinkedin, name: "LinkedIn", detail: "Inbound outreach & referrals", color: "#0A66C2" }];


export function Omnichannel() {
  return (
    <section id="channels" className="scroll-mt-24 py-24 sm:py-32">
      <Container>
        <div className="grid items-center gap-14 lg:grid-cols-2">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-teal-600">
              Everywhere your patients are
            </p>
            <h2 className="mt-3 font-display text-4xl font-500 tracking-tight text-ink sm:text-5xl">
              One inbox. Every channel. Fully automated.
            </h2>
            <p className="mt-4 text-lg text-ink-soft">
              Your agents don't just live on your website. They answer, qualify, and book across
              every social channel — replying in seconds, capturing leads that used to slip away
              overnight and on weekends.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {CHANNELS.map((c, i) =>
              <motion.div
                key={c.name}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="flex items-center gap-3 rounded-2xl border border-sand-200 bg-white p-4 shadow-soft">
                
                  <span
                  className="flex h-11 w-11 items-center justify-center rounded-xl text-white"
                  style={{ backgroundColor: c.color }}>
                  
                    <c.icon className="h-5.5 w-5.5" />
                  </span>
                  <div>
                    <p className="font-bold text-ink">{c.name}</p>
                    <p className="text-sm text-ink-muted">{c.detail}</p>
                  </div>
                </motion.div>
              )}
            </div>
          </div>

          {/* Unified conversation mock */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="rounded-4xl border border-sand-200 bg-white p-6 shadow-lift">
            
            <div className="flex items-center gap-2 border-b border-sand-100 pb-4">
              <FaInstagram className="h-5 w-5 text-[#D6336C]" />
              <span className="text-sm font-semibold text-ink">Instagram DM · @glow.aesthetics</span>
            </div>

            <div className="mt-5 space-y-4">
              <Bubble from="patient" text="Hi! How much is a rhinoplasty and do you have anything next week?" />
              <Bubble
                from="agent"
                text="Hi Maya! Rhinoplasty consultations start at $150 (applied to your procedure). I have Tuesday 11:00 AM or Thursday 2:30 PM open — want me to hold one for you? 💬" />
              
              <Bubble from="patient" text="Thursday works!" />
              <Bubble
                from="agent"
                text="Booked ✅ Thursday 2:30 PM with Dr. Reyes. I've texted you a confirmation and an intake link. See you then!" />
              
            </div>

            <div className="mt-5 flex items-center gap-2 rounded-full bg-teal-50 px-4 py-2.5 text-sm font-medium text-teal-700">
              <span className="h-2 w-2 animate-pulse rounded-full bg-teal-500" />
              Handled by Lead Nurturing + Appointment Booking agents
            </div>
          </motion.div>
        </div>
      </Container>
    </section>);

}

function Bubble({ from, text }: {from: "patient" | "agent";text: string;}) {
  const isAgent = from === "agent";
  return (
    <div className={`flex ${isAgent ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
        isAgent ? "bg-teal-500 text-white" : "bg-sand-100 text-ink"}`
        }>
        
        {text}
      </div>
    </div>);

}