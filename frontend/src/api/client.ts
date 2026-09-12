// Thin fetch wrapper for calling the backend (see ../../backend). Foundation
// only for now — most backend agent endpoints are still stubs with nothing
// real to fetch, so this isn't wired into any page yet. `getHealth()` in
// `./health.ts` is the one real, working call, used to prove the wiring end
// to end.

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  // A FormData body (file uploads) needs the browser to set its own
  // multipart Content-Type with boundary — forcing application/json here
  // would break every upload silently (FastAPI's UploadFile parsing fails
  // with no boundary to split on).
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...(isFormData ? {} : { "Content-Type": "application/json" }), ...init?.headers }
  });
  if (!res.ok) {
    // FastAPI's own exception handlers respond with {"detail": "..."} — that
    // real message (e.g. "This account is already registered as a doctor at
    // this practice.") is what a caller actually wants to show the user,
    // not a generic "failed with 400" that was silently swallowing it before.
    let detail: string | null = null;
    try {
      const body = await res.clone().json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON or empty error body — fall through to the generic message.
    }
    throw new ApiError(res.status, detail || `${init?.method || "GET"} ${path} failed with ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// For endpoints that return a real file (invoice PDFs, etc.) rather than
// JSON — apiFetch() above always calls res.json(), which would throw on a
// binary body.
export async function apiFetchBlob(path: string, init?: RequestInit): Promise<Blob> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    throw new ApiError(res.status, `${init?.method || "GET"} ${path} failed with ${res.status}`);
  }
  return res.blob();
}
