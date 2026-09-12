import { useCallback } from "react";
import { useAuth } from "@clerk/clerk-react";
import { apiFetch, apiFetchBlob, ApiError } from "./client";

// Closes the gap app/auth/README.md documents — apiFetch() never attached a
// Clerk session token, so every backend route expecting Depends(get_current_user)
// was unreachable from the frontend. useAuthedFetch() binds Clerk's
// getToken() into apiFetch's Authorization header.
//
// useCallback matters here, not just style: usePlanTier.ts's tier-fetching
// effect depends on this function's identity ([authedFetch]). Without
// memoizing, every render produced a brand-new function, and PlanContext.tsx's
// setOverride() (the dashboard's "Switch to this plan" button) itself causes
// exactly such a render — so clicking it re-triggered the effect, which
// re-fetched the REAL plan from the backend and immediately overwrote the
// switch, making it look like the change "redirected" back to the old plan.
export function useAuthedFetch() {
  // isSignedIn is a tri-state while Clerk initializes: undefined (still
  // loading) / false (signed out) / true. Callers that only check
  // `!isSignedIn` treat "still loading" as "signed out" — see
  // RequirePractice.tsx's isLoaded fix for why that matters.
  const { getToken, isSignedIn, isLoaded } = useAuth();

  const authedFetch = useCallback(
    async function authedFetch<T>(path: string, init?: RequestInit): Promise<T> {
      if (!isSignedIn) throw new ApiError(401, "Not signed in");
      const token = await getToken();
      return apiFetch<T>(path, {
        ...init,
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers }
      });
    },
    [getToken, isSignedIn]
  );

  // Sibling to authedFetch above, for endpoints that return a real file
  // (invoice PDFs) instead of JSON — see apiFetchBlob's own comment.
  const authedFetchBlob = useCallback(
    async function authedFetchBlob(path: string, init?: RequestInit): Promise<Blob> {
      if (!isSignedIn) throw new ApiError(401, "Not signed in");
      const token = await getToken();
      return apiFetchBlob(path, {
        ...init,
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init?.headers }
      });
    },
    [getToken, isSignedIn]
  );

  return { authedFetch, authedFetchBlob, isSignedIn, isLoaded };
}
