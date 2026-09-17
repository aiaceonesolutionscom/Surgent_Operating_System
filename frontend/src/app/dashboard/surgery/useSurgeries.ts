import { useCallback, useEffect, useState } from "react";
import {
  listSurgeries,
  getSurgery,
  createSurgery,
  updateSurgery,
  updateSurgeryClinical,
  confirmSurgery,
  startSurgery,
  completeSurgery,
  cancelSurgery,
  getSurgeryOverview,
  type SurgeryResponse,
  type CreateSurgeryRequest,
  type UpdateSurgeryRequest,
  type UpdateSurgeryClinicalRequest,
  type CompleteSurgeryRequest,
  type SurgeryOverviewResponse
} from "../../../api/entities";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

export function useSurgeries(authedFetch: AuthedFetch, patientId?: string, scope?: "all" | "mine") {
  const [surgeries, setSurgeries] = useState<SurgeryResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    if (!authedFetch) {
      setSurgeries([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await listSurgeries(authedFetch, patientId, scope);
      setSurgeries(data);
    } catch {
      setSurgeries([]);
    } finally {
      setLoading(false);
    }
  }, [authedFetch, patientId, scope]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const create = useCallback(
    async (data: CreateSurgeryRequest) => {
      if (!authedFetch) throw new Error("Not signed in");
      const created = await createSurgery(authedFetch, data);
      await refetch();
      return created;
    },
    [authedFetch, refetch]
  );

  return { surgeries, loading, refetch, create };
}

export function useSurgeryOverview(authedFetch: AuthedFetch) {
  const [overview, setOverview] = useState<SurgeryOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    if (!authedFetch) {
      setOverview(null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getSurgeryOverview(authedFetch);
      setOverview(data);
    } catch {
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { overview, loading, refetch };
}

export function useSurgery(authedFetch: AuthedFetch, surgeryId: string | undefined) {
  const [surgery, setSurgery] = useState<SurgeryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    if (!authedFetch || !surgeryId) {
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await getSurgery(authedFetch, surgeryId);
      setSurgery(data);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Couldn't load this surgery.");
    } finally {
      setLoading(false);
    }
  }, [authedFetch, surgeryId]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  // Scheduling-only update (Receptionist/Owner reschedule surface).
  const update = useCallback(
    async (data: UpdateSurgeryRequest) => {
      if (!authedFetch || !surgeryId) return;
      const updated = await updateSurgery(authedFetch, surgeryId, data);
      setSurgery(updated);
      return updated;
    },
    [authedFetch, surgeryId]
  );

  // Clinical update (Doctor/Owner pre-op checklist / note).
  const updateClinical = useCallback(
    async (data: UpdateSurgeryClinicalRequest) => {
      if (!authedFetch || !surgeryId) return;
      const updated = await updateSurgeryClinical(authedFetch, surgeryId, data);
      setSurgery(updated);
      return updated;
    },
    [authedFetch, surgeryId]
  );

  const confirm = useCallback(async () => {
    if (!authedFetch || !surgeryId) return;
    const updated = await confirmSurgery(authedFetch, surgeryId);
    setSurgery(updated);
    return updated;
  }, [authedFetch, surgeryId]);

  const start = useCallback(async () => {
    if (!authedFetch || !surgeryId) return;
    const updated = await startSurgery(authedFetch, surgeryId);
    setSurgery(updated);
    return updated;
  }, [authedFetch, surgeryId]);

  const complete = useCallback(
    async (data: CompleteSurgeryRequest) => {
      if (!authedFetch || !surgeryId) return;
      const updated = await completeSurgery(authedFetch, surgeryId, data);
      setSurgery(updated);
      return updated;
    },
    [authedFetch, surgeryId]
  );

  const cancel = useCallback(async (reason?: string) => {
    if (!authedFetch || !surgeryId) return;
    const updated = await cancelSurgery(authedFetch, surgeryId, { reason: reason || "" });
    setSurgery(updated);
    return updated;
  }, [authedFetch, surgeryId]);

  return { surgery, loading, error, refetch, update, updateClinical, confirm, start, complete, cancel };
}