import { useCallback, useEffect, useRef, useState } from "react";
import { MOCK_DOCTORS } from "../data/mockDoctors";
import { isDemoMode } from "../../../data/demoMode";
import type { Doctor } from "./types";
import { loadDoctorsDB, saveDoctorsDB } from "./doctorsDB";
import { createDoctor, listDoctors, updateDoctor as updateDoctorApi, inviteDoctor, type DoctorResponse } from "../../../api/entities";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

// Doctors used to live in localStorage, which caps out around 5-10MB per
// origin — too small once real photos/documents are attached (they're
// base64 data URIs, ~33% bigger than the file itself; a couple of real PDFs
// filled it and made saves silently fail). IndexedDB's quota is a large
// fraction of free disk space, so records now live there instead.
const LEGACY_STORAGE_KEY = "aesthetixai_dashboard_doctors";

function readLegacyLocalStorage(): Doctor[] | null {
  try {
    const raw = localStorage.getItem(LEGACY_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

// A doctor saved before `capabilities`/`availability`/`documents`/`userId`
// existed on the type (localStorage era or otherwise) is missing those
// fields entirely — every page calls .length/.map/.filter on them directly,
// so a stale record crashes the whole app on load. Backfill defaults instead
// of trusting whatever shape is already sitting in storage.
function normalize(doctor: Doctor): Doctor {
  return {
    ...doctor,
    capabilities: doctor.capabilities ?? [],
    availability: doctor.availability ?? [],
    documents: doctor.documents ?? [],
    userId: doctor.userId ?? null,
    isActive: doctor.isActive ?? true
  };
}

// Backend Doctor rows don't carry yearsExperience/availability/documents/
// activePatients/upcomingSurgeries yet (see backend/src/models/doctor.py) —
// a doctor synced FROM the API defaults those to honest zeros/empty arrays
// rather than fabricating fake-looking data, same precedent as
// patients/usePatients.ts's own fromApi.
function fromApi(d: DoctorResponse): Doctor {
  return {
    id: d.id,
    name: d.name,
    initial: d.name.trim()[0]?.toUpperCase() || "?",
    photoUrl: d.photo_url ?? undefined,
    userId: d.user_id,
    email: d.email,
    phone: d.phone ?? "",
    specialty: d.specialty ?? "",
    capabilities: d.capabilities,
    licenseNumber: d.license_number ?? "",
    yearsExperience: 0,
    bio: d.bio ?? "",
    availability: [],
    documents: [],
    activePatients: 0,
    upcomingSurgeries: 0,
    isActive: d.is_active
  };
}

// A stuck IndexedDB request (blocked by another tab, a wedged connection)
// otherwise hangs its Promise forever — which left `loading` true forever
// and the whole page blank with no way out. Cap every DB call so the UI can
// always fall back instead.
function withTimeout<T>(promise: Promise<T>, ms = 5000): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Storage operation timed out")), ms);
    promise.then(
      (v) => {
        clearTimeout(timer);
        resolve(v);
      },
      (e) => {
        clearTimeout(timer);
        reject(e);
      }
    );
  });
}

// Real backend (GET/POST/PATCH /api/v1/doctors, see backend/src/router/doctors/)
// is source #1 when signed in — falls back to the IndexedDB cache on failure
// or when signed out, same source-chain as patients/usePatients.ts.
// `authedFetch` comes from usePlan() (app/dashboard/plan/PlanContext.tsx) —
// pass null to stay IndexedDB-only, e.g. when Clerk is disabled.
export function useDoctors(authedFetch: AuthedFetch = null) {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const doctorsRef = useRef<Doctor[]>([]);
  doctorsRef.current = doctors;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let data: Doctor[] | undefined;
      let error: string | null = null;

      if (authedFetch) {
        try {
          const remote = await listDoctors(authedFetch);
          data = remote.map(fromApi);
          await withTimeout(saveDoctorsDB(data)).catch(() => undefined);
        } catch {
          data = undefined;
        }
      }

      if (!data) {
        // Everything below here is a *cache* path, reached both when signed out
        // and when a real API call just failed. The mock roster is demo-mode
        // exclusive: a signed-in clinic whose doctors request failed must end
        // up with an empty list and a visible error, never an invented team the
        // practice could try to invoice or message. The same rule the overview
        // and sessions hooks follow.
        let cacheFailed = false;
        try {
          data = await withTimeout(loadDoctorsDB());
          if (!data) {
            const legacy = readLegacyLocalStorage();
            if (legacy) {
              data = legacy.map(normalize);
            } else {
              data = isDemoMode() ? MOCK_DOCTORS : [];
            }
            // Only persist a non-empty roster. Writing the empty result of a
            // failed fetch would poison the cache and stop the next attempt
            // from ever being able to recover a real list.
            if (data.length) await withTimeout(saveDoctorsDB(data));
          } else {
            data = data.map(normalize);
          }
        } catch {
          // IndexedDB unavailable (private browsing, storage disabled) — fall
          // back to in-memory only, same degradation as the old localStorage path.
          cacheFailed = true;
          data = isDemoMode() ? MOCK_DOCTORS : [];
        }
        if (authedFetch && data.length === 0) {
          error = cacheFailed
            ? "Couldn't load your doctors — local storage is unavailable in this browser."
            : "Couldn't load your doctors — check your connection and try again.";
        }
      }
      if (!cancelled) {
        doctorsRef.current = data;
        setDoctors(data);
        setLoadError(error);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  const getDoctor = useCallback((id: string) => doctors.find((d) => d.id === id), [doctors]);

  const addDoctor = useCallback(
    async (doctor: Doctor): Promise<Doctor | null> => {
      let toSave = doctor;

      if (authedFetch) {
        try {
          const created = await createDoctor(authedFetch, {
            name: doctor.name,
            email: doctor.email,
            phone: doctor.phone || null,
            specialty: doctor.specialty || null,
            license_number: doctor.licenseNumber || null,
            bio: doctor.bio || null,
            capabilities: doctor.capabilities
          });
          // Keep the locally-known extras the backend doesn't store yet
          // (yearsExperience/availability/documents/photoUrl) but use the
          // real id so future GET /doctors calls match this same record.
          toSave = { ...doctor, id: created.id, userId: created.user_id, isActive: created.is_active };
        } catch {
          // API unavailable — fall through to the local-only save below,
          // same graceful-degradation behavior this hook always had.
        }
      }

      const next = [...doctorsRef.current, toSave];
      try {
        await withTimeout(saveDoctorsDB(next));
        doctorsRef.current = next;
        setDoctors(next);
        return toSave;
      } catch {
        return null;
      }
    },
    [authedFetch]
  );

  const updateDoctor = useCallback(
    async (id: string, patch: Partial<Doctor>): Promise<boolean> => {
      if (authedFetch) {
        try {
          await updateDoctorApi(authedFetch, id, {
            name: patch.name,
            email: patch.email,
            phone: patch.phone,
            specialty: patch.specialty,
            license_number: patch.licenseNumber,
            bio: patch.bio,
            capabilities: patch.capabilities,
            is_active: patch.isActive
          });
        } catch {
          // API unavailable — fall through to the local-only update below.
        }
      }

      const next = doctorsRef.current.map((d) => (d.id === id ? { ...d, ...patch } : d));
      try {
        await withTimeout(saveDoctorsDB(next));
        doctorsRef.current = next;
        setDoctors(next);
        return true;
      } catch {
        return false;
      }
    },
    [authedFetch]
  );

  // Owner's "help them log back in" lever — resends the invite this doctor
  // originally got (POST /doctors/{id}/invite, backend endpoint already
  // existed but was never wired to any UI). Not a permissions/roster change,
  // just re-sends Clerk email access to the same doctor.id/email.
  const resendAccess = useCallback(
    async (id: string): Promise<string | null> => {
      if (!authedFetch) return "Not signed in.";
      try {
        await inviteDoctor(authedFetch, id);
        return null;
      } catch (err) {
        return err instanceof Error && err.message ? err.message : "Couldn't resend — try again.";
      }
    },
    [authedFetch]
  );

  return { doctors, loading, loadError, getDoctor, addDoctor, updateDoctor, resendAccess };
}
