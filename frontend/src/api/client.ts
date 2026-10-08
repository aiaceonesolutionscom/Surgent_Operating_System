// Thin fetch wrapper for calling the backend (see ../../backend). Foundation
// only for now — most backend agent endpoints are still stubs with nothing
// real to fetch, so this isn't wired into any page yet. `getHealth()` in
// `./health.ts` is the one real, working call, used to prove the wiring end
// to end.

// In development an unset VITE_API_BASE_URL falls back to the local API
// (port 8001, not FastAPI's default 8000). A PRODUCTION build must never do
// that - it would aim every visitor's browser at their own machine - so the
// fallback is empty there, and vite.config.ts refuses to build without a real
// API URL in the first place.
export const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://127.0.0.1:8001" : "")
).replace(/\/+$/, "");

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

// For the streaming agent endpoints (server/sse.py's `data: <json>\n\n`
// wire format) — a browser EventSource can't be used here since it's
// GET-only and can't carry a POST body or an Authorization header, so this
// reads the fetch Response body's ReadableStream directly and yields each
// parsed event as it arrives. Async generator so a caller does
// `for await (const event of streamSSE(...))`.
export async function* streamSSE<T = Record<string, unknown>>(path: string, init?: RequestInit): AsyncGenerator<T> {
  // A string body makes the browser send `Content-Type: text/plain`, and
  // FastAPI only parses a JSON body for a JSON content type - without this
  // header every streaming endpoint (Aria, Command Center, Finance Agent)
  // answers 422.
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { ...(typeof init?.body === "string" ? { "Content-Type": "application/json" } : {}), ...init?.headers }
  });
  if (!res.ok || !res.body) {
    let detail: string | null = null;
    try {
      const body = await res.clone().json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // Non-JSON or empty error body — fall through to the generic message.
    }
    throw new ApiError(res.status, detail || `${init?.method || "GET"} ${path} failed with ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      // SSE frames are separated by a blank line; each frame's payload line
      // starts with "data: ".
      const frames = buffer.split("\n\n");
      buffer = frames.pop() || "";
      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        try {
          yield JSON.parse(line.slice(6)) as T;
        } catch {
          // A malformed frame shouldn't kill the whole stream.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
