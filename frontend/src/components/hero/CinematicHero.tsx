import React, { useEffect, useRef } from "react";
import { mountLetsScroll } from "./scrub-engine";
import type { HeroChatSeed } from "../chat/LandingChat";

const SECTIONS = [
{
  id: "reception",
  label: "First Call",
  still: "/lets-scroll/reception.png",
  stillMobile: "/lets-scroll/reception-mobile.png",
  clip: "/lets-scroll/reception.mp4",
  clipMobile: "/lets-scroll/reception-mobile.mp4",
  accent: "#0B6362",
  eyebrow: "First Call, Answered",
  title: "Never miss another patient call",
  body: "A missed call becomes a missed patient. Aiaceone's AI receptionist answers instantly — day or night — so every inquiry turns into a booked consult, not a call to the practice next door.",
  tags: ["24/7 coverage", "Phone · Chat · WhatsApp"]
},
{
  id: "booking",
  label: "Consultations",
  still: "/lets-scroll/booking.png",
  stillMobile: "/lets-scroll/booking-mobile.png",
  clip: "/lets-scroll/booking.mp4",
  clipMobile: "/lets-scroll/booking-mobile.mp4",
  accent: "#0B6362",
  eyebrow: "Consultations, Booked",
  title: "Every inquiry becomes an appointment",
  body: "AI agents book consultations instantly, with zero double-bookings.",
  tags: ["Auto-scheduling", "Instant confirmation"]
},
{
  id: "care",
  label: "Recovery",
  still: "/lets-scroll/care.png",
  stillMobile: "/lets-scroll/care-mobile.png",
  clip: "/lets-scroll/care.mp4",
  clipMobile: "/lets-scroll/care-mobile.mp4",
  accent: "#0B6362",
  eyebrow: "Healing, Watched Over",
  title: "Recovery checked in on, automatically",
  body: "Agents monitor healing and follow up with every patient after every procedure.",
  tags: ["Post-op check-ins", "HIPAA-aware"]
},
{
  id: "growth",
  label: "Growth",
  still: "/lets-scroll/growth.png",
  stillMobile: "/lets-scroll/growth-mobile.png",
  clip: "/lets-scroll/growth.mp4",
  clipMobile: "/lets-scroll/growth-mobile.mp4",
  accent: "#C9A24B",
  eyebrow: "Growth, Visualized",
  title: "See your practice grow",
  body: "Track revenue and every conversation, across every channel, in one view.",
  tags: ["Revenue up", "Multi-channel"],
  // The engine renders this as a raw <a href> inside DOM it builds itself
  // (not a React element), so it can't be a react-router <Link> — a real
  // (full-reload) navigation to /demo is the closest this can get.
  cta: { primary: { label: "Book a demo", href: "/demo" } }
}];


export function CinematicHero({ onOpenChat }: { onOpenChat?: (seed: HeroChatSeed) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const onOpenChatRef = useRef(onOpenChat);

  useEffect(() => {
    onOpenChatRef.current = onOpenChat;
  }, [onOpenChat]);

  useEffect(() => {
    if (!ref.current) return;
    const container = ref.current;
    container.innerHTML = "";
    const engine = mountLetsScroll(container, {
      // brand/cta/nav are left off — the site's own <Navbar /> already covers
      // that role and sits fixed above this section, so the engine's built-in
      // topbar would just duplicate/overlap it.
      nav: false,
      hint: "scroll to fly in",
      diveScroll: 1.3,
      sections: SECTIONS,
      connectors: [],
      crossfade: 0.08
    });
    // Tells index.html's inline scroll-lock script (see its own comment)
    // that the hero has measured its real (very tall) track height and
    // positioned its first scene — mountLetsScroll's layout() call runs
    // synchronously during construction, so this is accurate the instant
    // the function returns, not just "mount started."
    (window as unknown as { __heroReady?: boolean }).__heroReady = true;

    // Make the flying copy interactive: clicking a headline/body opens the
    // landing chat (LandingChat.tsx) seeded with that section's text, so a
    // visitor can press a claim and immediately ask Aria about it. The
    // engine builds this DOM itself (scrub-engine.js), so enrichment happens
    // after mount: enable pointer events on title/body, then a single
    // delegated click reads whichever .sw-copy got clicked.
    const copylayer = container.querySelector<HTMLElement>(".sw-copylayer");
    let copyStyleEl: HTMLStyleElement | null = null;
    const onCopyClick = (ev: MouseEvent) => {
      const target = ev.target as HTMLElement;
      const copyEl = target.closest<HTMLElement>(".sw-copy");
      if (!copyEl || !onOpenChatRef.current) return;
      const text = (sel: string) => copyEl.querySelector<HTMLElement>(sel)?.textContent?.trim() || "";
      const title = text(".sw-copy__title");
      const body = text(".sw-copy__body");
      if (!title && !body) return;
      onOpenChatRef.current({ eyebrow: text(".sw-copy__eyebrow"), title, body });
    };
    if (copylayer) {
      copyStyleEl = document.createElement("style");
      copyStyleEl.textContent =
        ".sw-copy__title,.sw-copy__body{cursor:pointer;pointer-events:auto;user-select:text;}" +
        ".sw-copy__title:hover,.sw-copy__body:hover{text-decoration:underline;text-decoration-color:var(--sw-accent);text-decoration-thickness:2px;text-underline-offset:6px;}";
      container.appendChild(copyStyleEl);
      copylayer.addEventListener("click", onCopyClick);
    }

    // The track carries one extra viewport-height of scroll after the last
    // scene ("so the last flight completes") — that trailing stretch is where
    // the ambient sky/particles keep showing with nothing new happening, and
    // where the scroll-guide avatar's big intro takes over (see
    // ScrollGuideAvatar.tsx). The engine holds the last scene's copy at full
    // opacity through that whole stretch and beyond (by design, for a hero
    // that IS the whole page) — this site has content below, so the Growth
    // copy shouldn't linger into the avatar moment. Fade it out across the
    // second half of the scene's own settle (finishing right as the trailing
    // stretch/avatar begins, not overlapping it), and hide the hero's other
    // fixed layers (sky/stage/route/etc.) once the container is fully behind
    // the viewport, same as before.
    let ticking = false;
    const update = () => {
      ticking = false;
      const rect = container.getBoundingClientRect();
      const vh = window.innerHeight;
      const padStart = rect.height - vh; // scroll-distance where the trailing stretch begins
      const distancePastPadStart = -rect.top - padStart; // 0 at that point, vh once fully cleared

      const copylayer = container.querySelector<HTMLElement>(".sw-copylayer");
      if (copylayer) {
        const fadeStart = padStart - vh * 0.5;
        const fade = Math.min(Math.max((-rect.top - fadeStart) / (vh * 0.5), 0), 1);
        copylayer.style.opacity = String(1 - fade);
      }

      // The engine reserves one full extra viewport-height of scroll track
      // beyond the last scene ("so the last flight completes" — see
      // scrub-engine.js's `track.style.height = ... + vh`). Waiting for the
      // FULL extra vh before hiding the sky/particles left a long stretch of
      // scrolling with nothing on screen but drifting decorative dots and a
      // flat background — no text, no next section, reads as a broken/empty
      // page rather than a settling animation. The flight itself visually
      // finishes well before the full buffer is used up, so hiding at a
      // fraction of it removes the dead zone without cutting the motion off
      // mid-flight.
      container.classList.toggle("sw-past-end", distancePastPadStart >= vh * 0.15);
    };
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (copylayer) copylayer.removeEventListener("click", onCopyClick);
      if (copyStyleEl) copyStyleEl.remove();
      // Real routing exists now (Home → /agents → back to Home unmounts and
      // remounts this component) — without disposing the engine, each round
      // trip leaked another full set of its own listeners plus an orphaned
      // rAF loop scrubbing DOM this same cleanup just cleared.
      engine.dispose();
    };
  }, []);

  return <div ref={ref} className="cinematic-hero" />;
}
