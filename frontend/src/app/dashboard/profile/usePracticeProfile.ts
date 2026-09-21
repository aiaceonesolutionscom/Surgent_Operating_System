import { useCallback, useEffect, useState } from "react";
import { getMyPractice, updateMyPractice } from "../../../api/practice";

export interface PracticeProfile {
  name: string;
  timezone: string;
  address: string;
  onCallPhone: string;
}

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

const STORAGE_KEY = "aesthetixai_dashboard_practice_profile";

const DEFAULT_PROFILE: PracticeProfile = {
  name: "Your Practice",
  timezone: "America/New_York",
  address: "",
  onCallPhone: ""
};

function loadLocal(): PracticeProfile {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULT_PROFILE, ...JSON.parse(raw) } : DEFAULT_PROFILE;
  } catch {
    return DEFAULT_PROFILE;
  }
}

function saveLocal(profile: PracticeProfile) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
  } catch {
    // ignore — private mode / storage disabled
  }
}

// Real backend (GET/PATCH /api/v1/practice/me, owner-only) is source #1
// when signed in — same source-chain pattern as usePatients.ts/useDoctors.ts.
// A successful save is also mirrored into localStorage so SetupChecklist and
// any other reader stay in sync even if the API is briefly unreachable.
export function usePracticeProfile(authedFetch: AuthedFetch = null) {
  const [profile, setProfile] = useState<PracticeProfile>(() => loadLocal());
  const [loading, setLoading] = useState(Boolean(authedFetch));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!authedFetch) {
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const remote = await getMyPractice(authedFetch);
        if (cancelled) return;
        const next: PracticeProfile = {
          name: remote.name,
          timezone: remote.timezone,
          address: remote.address || "",
          onCallPhone: remote.phone || ""
        };
        setProfile(next);
        saveLocal(next);
      } catch {
        // Backend unreachable — keep whatever was already loaded locally.
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  // Draft-only — does not persist. Call save() to actually write it.
  const update = (patch: Partial<PracticeProfile>) => setProfile((p) => ({ ...p, ...patch }));

  const save = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    setError(null);
    try {
      if (authedFetch) {
        const remote = await updateMyPractice(authedFetch, {
          name: profile.name,
          timezone: profile.timezone,
          address: profile.address || null,
          phone: profile.onCallPhone || null
        });
        const next: PracticeProfile = {
          name: remote.name,
          timezone: remote.timezone,
          address: remote.address || "",
          onCallPhone: remote.phone || ""
        };
        setProfile(next);
        saveLocal(next);
      } else {
        saveLocal(profile);
      }
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't save — try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [authedFetch, profile]);

  return { profile, update, save, loading, saving, error };
}
