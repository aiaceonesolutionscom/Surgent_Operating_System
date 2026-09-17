import { useEffect, useRef } from "react";
import { useLocation, useNavigationType } from "react-router-dom";

const KEY_PREFIX = "scrollpos:";

// Module-level (not component state) so it survives React StrictMode's dev
// double-mount but always starts false on a real page load/refresh — a
// fresh module evaluation. Restoring a saved scroll position is only ever
// correct for a browser-back landing on a page the user genuinely left via
// an in-app click during THIS session; react-router's history can report
// navigationType "POP" for the very first render of a fresh tab too (its
// initial action defaults to Pop), which would otherwise let a stale
// sessionStorage value from a previous visit jump the page straight past
// the hero on load — this flag is what tells those two "POP"s apart.
let hasNavigatedWithinApp = false;

function readSaved(pathname: string): number {
  try {
    return Number(sessionStorage.getItem(KEY_PREFIX + pathname) || 0);
  } catch {
    return 0;
  }
}

function writeSaved(pathname: string, y: number) {
  try {
    sessionStorage.setItem(KEY_PREFIX + pathname, String(y));
  } catch {
    // ignore (private mode / storage disabled)
  }
}

function forceScrollTo(top: number) {
  const html = document.documentElement;
  const prev = html.style.scrollBehavior;
  html.style.scrollBehavior = "auto";
  window.scrollTo({ top, left: 0, behavior: "instant" });
  html.style.scrollBehavior = prev;
}

export function ScrollToTop() {
  const { pathname, hash } = useLocation();
  const navigationType = useNavigationType();
  const isFirstRun = useRef(true);

  useEffect(() => {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  }, []);

  useEffect(() => {
    const onClickCapture = (e: MouseEvent) => {
      const anchor = (e.target as HTMLElement)?.closest?.("a[href]");
      if (!anchor) return;
      hasNavigatedWithinApp = true;
      writeSaved(window.location.pathname, window.scrollY);
    };
    document.addEventListener("click", onClickCapture, { capture: true });
    return () => document.removeEventListener("click", onClickCapture, { capture: true });
  }, []);

  useEffect(() => {
    const firstLoad = isFirstRun.current;
    isFirstRun.current = false;

    if (hash && !firstLoad) {
      const id = hash.slice(1);
      let cancelled = false;
      let attempts = 0;
      const tryScrollToHash = () => {
        if (cancelled) return;
        attempts++;
        const el = document.getElementById(id);
        if (el) {
          el.scrollIntoView();
        } else if (attempts <= 60) {
          requestAnimationFrame(tryScrollToHash);
        }
      };
      requestAnimationFrame(tryScrollToHash);
      return () => { cancelled = true; };
    }

    const saved = !firstLoad && hasNavigatedWithinApp && navigationType === "POP" ? readSaved(pathname) : 0;
    if (saved <= 0) {
      forceScrollTo(0);
      return;
    }

    let cancelled = false;
    let attempts = 0;
    const pageHeight = () =>
      Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight || 0);
    const tryRestore = () => {
      if (cancelled) return;
      attempts++;
      if (pageHeight() - window.innerHeight >= saved) {
        forceScrollTo(saved);
      } else if (attempts <= 600) {
        requestAnimationFrame(tryRestore);
      } else {
        forceScrollTo(0);
      }
    };
    requestAnimationFrame(tryRestore);
    return () => { cancelled = true; };
  }, [pathname, navigationType, hash]);

  return null;
}
