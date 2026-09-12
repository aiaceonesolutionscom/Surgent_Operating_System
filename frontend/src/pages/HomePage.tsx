import React, { useState } from "react";
import { Navbar, Footer } from "../components/layout";
import { CinematicHero, ScrollGuideAvatar } from "../components/hero";
import { LandingChat, type HeroChatSeed } from "../components/chat/LandingChat";
import {
  SpecialtySelector,
  PainPointStats,
  HowItWorks,
  FeatureShowcase,
  DashboardPreview,
  Security,
  Testimonials,
  Pricing
} from "../components/sections";
import { SectionTeaser, CHANNELS } from "../components/features";
import { CTA } from "../components/cta";
import { BookConsultationSection } from "../components/book-consultation/BookConsultationSection";

// Static constant — avoids importing all 9 agent definition files on the
// landing page (they are only needed on the /agents pages).
const TOTAL_AGENTS = 9;

export function HomePage() {
  const [chatOpen, setChatOpen] = useState(false);
  const [chatSeed, setChatSeed] = useState<HeroChatSeed | null>(null);

  return (
    <div className="min-h-screen w-full bg-canvas font-sans text-ink">
      <Navbar />
      <ScrollGuideAvatar
        onAskAria={(message) => {
          setChatSeed({ eyebrow: "", title: message, body: "" });
          setChatOpen(true);
        }}
      />
      <main>
        <CinematicHero
          onOpenChat={(seed) => {
            setChatSeed(seed);
            setChatOpen(true);
          }}
        />
        <PainPointStats />
        <SpecialtySelector />
        <HowItWorks />
        <SectionTeaser
          id="agents"
          image="/screenshots/executive-dashboard.png"
          eyebrow="The agent suite"
          title={`${TOTAL_AGENTS} agents. Every corner of your practice.`}
          body="An entire agent factory working your practice — from the first call to the final recovery check-in. Meet the full roster."
          chips={[
          "AI Receptionist",
          "AI Consultation",
          "Surgery Scheduling",
          "Recovery Follow-up",
          "Lead Nurturing"]}

          ctaLabel="See all agents"
          ctaHref="/agents"
          dark />

        <SectionTeaser
          id="channels"
          image="/screenshots/ai-voice-receptionist.png"
          eyebrow="Everywhere your patients are"
          title="One inbox. Every channel. Fully automated."
          body="Your agents answer, qualify, and book across every social channel your patients already use."
          chips={CHANNELS.map((c) => ({ label: c.name, icon: c.icon, color: c.color }))}
          ctaLabel="See every channel"
          ctaHref="/channels"
          reverse />

        <FeatureShowcase />
        <DashboardPreview />
        <Security />
        <Testimonials />
        <Pricing />
        <BookConsultationSection />
        <CTA />
      </main>
      <Footer />
      <LandingChat
        open={chatOpen}
        seed={chatSeed}
        onClose={() => setChatOpen(false)}
        onSeedConsumed={() => setChatSeed(null)}
      />
    </div>);

}
