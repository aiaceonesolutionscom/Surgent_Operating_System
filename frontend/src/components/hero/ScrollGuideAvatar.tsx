import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { StethoscopeIcon } from "lucide-react";
import { useMediaQuery } from "../../hooks";

interface Stop {
  sectionId: string;
  message: string;
  // where the badge anchors on desktop, in viewport corners
  corner: "bottom-right" | "top-right";
}

const STOPS: Stop[] = [
{
  sectionId: "how-it-works",
  message: "Hey — I'll point out the highlights as you scroll.",
  corner: "bottom-right"
},
{
  sectionId: "agents",
  message: "This is the agent suite — meet the specialists that run your practice.",
  corner: "top-right"
},
{
  sectionId: "channels",
  message: "Same agents, every channel your patients already use.",
  corner: "top-right"
},
{
  // Targets just the section's heading block, not the whole (tall) section —
  // the pricing cards below it run long, and watching the full section let this
  // stop stay "active" deep into the card grid, where a card's own content can
  // scroll up into this same corner. The guide retreats once past this heading
  // (see the pastGuide effect below) instead of trying to dodge the cards.
  sectionId: "pricing-heading",
  message: "Pick the plan that matches your practice size.",
  corner: "top-right"
}];


const BADGE = 56; // avatar circle size, px
const MARGIN = 28;
const NAV_CLEARANCE = 116; // keeps top-anchored stops below the fixed Navbar
// Focus ring shown for keyboard users only (`:focus-visible`), styled to match
// the brand instead of the browser's default blue — a plain `:focus` ring was
// flashing on click, which read as a stray colour glitch.
const FOCUS_RING = "outline-none focus-visible:ring-2 focus-visible:ring-teal-400 focus-visible:ring-offset-2";

function cornerToPoint(corner: Stop["corner"]) {
  const w = window.innerWidth;
  const h = window.innerHeight;
  switch (corner) {
    case "bottom-right":
      return { top: h - BADGE - MARGIN, left: w - BADGE - MARGIN };
    case "top-right":
      return { top: NAV_CLEARANCE, left: w - BADGE - MARGIN };
  }
}

// A lightweight, persistent scroll-companion — a small badge that tracks
// down the right edge of the page and surfaces a one-line hint per section.
// Deliberately NOT a talking-avatar intro anymore: this used to open with a
// full-screen video modal that blocked scrolling for a forced 5-second
// dwell, using a cartoon "chibi" doctor illustration whose tone clashed with
// the rest of the site's editorial, video-led hero. Kept the section-aware
// positioning logic (it's genuinely useful, low-cost wayfinding) and dropped
// everything else — no video, no forced dwell, no character illustration.
export function ScrollGuideAvatar({ onAskAria }: { onAskAria?: (message: string) => void }) {
  const [avatarActive, setAvatarActive] = useState(false);
  const [retreated, setRetreated] = useState(false);
  const [activeStop, setActiveStop] = useState(0);
  const [moving, setMoving] = useState(false);
  const [target, setTarget] = useState(() => cornerToPoint(STOPS[0].corner));

  // The guide becomes active once the visitor has scrolled past the
  // cinematic hero's scroll-scrubbed track (same trailing stretch described
  // in CinematicHero.tsx) — no separate "intro" phase, it just appears.
  useEffect(() => {
    let ticking = false;
    const update = () => {
      ticking = false;
      const hero = document.querySelector(".cinematic-hero");
      // `.sw-root` is only added once `mountLetsScroll` has actually run and set
      // the real (tall) track height — before that, the container only has its
      // CSS `min-height: 100vh` fallback (see index.css), which would make
      // `padStart` read as ~0 and briefly activate the guide at page load.
      if (hero && hero.classList.contains("sw-root")) {
        const rect = hero.getBoundingClientRect();
        const vh = window.innerHeight;
        const padStart = rect.height - vh;
        const distancePastPadStart = -rect.top - padStart;
        setAvatarActive(distancePastPadStart >= vh * 1.3);
      }
      const pricingHeading = document.getElementById("pricing-heading");
      if (pricingHeading) setRetreated(pricingHeading.getBoundingClientRect().bottom <= 0);
    };
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(update);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    update();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Below `lg` there's no reliable empty gutter to jump around in — collapse to a
  // single static corner badge instead of risking an overlap on narrow screens.
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const showGuide = avatarActive && !retreated;

  // Track which of the 4 tour-stop sections is currently near the middle of the
  // viewport, using a narrow rootMargin band so the "active" section only changes
  // once, cleanly, as it crosses the centre — not on every pixel of scroll.
  useEffect(() => {
    const els = STOPS.
    map((s) => document.getElementById(s.sectionId)).
    filter((el): el is HTMLElement => !!el);
    if (!els.length) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const idx = STOPS.findIndex((s) => s.sectionId === entry.target.id);
          if (idx !== -1) setActiveStop(idx);
        });
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
    );
    els.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const recompute = () => setTarget(cornerToPoint(STOPS[activeStop].corner));
    recompute();
    window.addEventListener("resize", recompute);
    return () => window.removeEventListener("resize", recompute);
  }, [activeStop]);

  // On phones there's no empty gutter to anchor the message bubble in without
  // it sitting on top of real page content (see the mobile guide render below),
  // so the full bubble only stays up briefly on each new stop, then collapses
  // to just the badge — tapping it re-expands the current stop's message.
  const [bubbleCollapsed, setBubbleCollapsed] = useState(false);
  useEffect(() => {
    setBubbleCollapsed(false);
    const timer = setTimeout(() => setBubbleCollapsed(true), 3500);
    return () => clearTimeout(timer);
  }, [activeStop]);

  // The badge sits at an exact viewport corner; the bubble hangs off whichever
  // side has room (away from the screen edge the badge is anchored to) so it
  // can never get clipped or push the badge off its intended spot.
  const bubbleSide: "left" | "right" = target.left > window.innerWidth / 2 ? "left" : "right";

  return (
    <AnimatePresence>
      {showGuide && !isDesktop &&
      <motion.div
        key="mobile-guide"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed z-50 flex max-w-[calc(100vw-2.5rem)] items-center justify-end gap-2.5"
        style={{ bottom: "calc(env(safe-area-inset-bottom, 0px) + 1.25rem)", right: "1.25rem" }}>

          <AnimatePresence>
            {!bubbleCollapsed &&
            <motion.button
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.94 }}
              transition={{ duration: 0.18 }}
              type="button"
              onClick={() => onAskAria?.(STOPS[activeStop].message)}
              aria-label={`Ask Aria about: ${STOPS[activeStop].message}`}
              className="cursor-pointer rounded-2xl border border-sand-200 bg-white px-4 py-2.5 text-left text-sm font-medium text-ink shadow-lift transition-colors hover:border-teal-500/60 hover:text-teal-700">

                {STOPS[activeStop].message}
              </motion.button>
            }
          </AnimatePresence>
          <button
            onClick={() => setBubbleCollapsed((v) => !v)}
            aria-label={bubbleCollapsed ? "Show guide message" : "Hide guide message"}
            className={`shrink-0 rounded-full ${FOCUS_RING}`}>

            <AvatarBadge small={bubbleCollapsed} />
          </button>
        </motion.div>
      }

      {showGuide && isDesktop &&
      <motion.div
        key="desktop-guide"
        className="fixed z-50 h-14 w-14"
        animate={{ top: target.top, left: target.left }}
        exit={{ opacity: 0 }}
        transition={{ type: "spring", stiffness: 170, damping: 22 }}
        onAnimationStart={() => setMoving(true)}
        onAnimationComplete={() => setMoving(false)}>

          <div className="relative h-14 w-14">
            <AnimatePresence>
              {!moving &&
            <motion.button
              key={activeStop}
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.92 }}
              transition={{ duration: 0.2 }}
              type="button"
              onClick={() => onAskAria?.(STOPS[activeStop].message)}
              aria-label={`Ask Aria about: ${STOPS[activeStop].message}`}
              className={`absolute top-1/2 w-[240px] -translate-y-1/2 cursor-pointer rounded-2xl border border-sand-200 bg-white px-4 py-2.5 text-left text-sm font-medium text-ink shadow-lift transition-colors hover:border-teal-500/60 hover:text-teal-700 ${
              bubbleSide === "left" ? "right-[calc(100%+12px)]" : "left-[calc(100%+12px)]"}`
              }>

                  {STOPS[activeStop].message}
                </motion.button>
            }
            </AnimatePresence>
            <AvatarBadge />
          </div>
        </motion.div>
      }
    </AnimatePresence>);

}

function AvatarBadge({ small }: { small?: boolean }) {
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-full border-2 border-white bg-teal-600 shadow-lift ${
      small ? "h-11 w-11" : "h-14 w-14"}`
      }>

      <StethoscopeIcon className={small ? "h-5 w-5 text-white" : "h-6 w-6 text-white"} />
    </div>);

}
