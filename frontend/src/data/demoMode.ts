/**
 * Mock/fallback data is only ever allowed when the app is explicitly started
 * in demo mode. It is never used to paper over a real API failure — a failed
 * request must surface as an error state, not silently render fake numbers
 * that a clinic could act on.
 *
 * Set VITE_DEMO_MODE=true in the environment to opt in.
 */
export function isDemoMode(): boolean {
  return import.meta.env?.VITE_DEMO_MODE === "true" || import.meta.env?.VITE_DEMO_MODE === "1";
}
