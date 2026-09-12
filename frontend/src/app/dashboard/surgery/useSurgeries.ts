import { useCallback, useEffect, useState } from "react";
import {
  listSurgeries,
  getSurgery,
  createSurgery,
  updateSurgery,
  completeSurgery,
  cancelSurgery,
  type SurgeryResponse,
  type CreateSurgeryRequest,
  type UpdateSurgeryRequest,
  type CompleteSurgeryRequest
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

  const update = useCallback(
    async (data: UpdateSurgeryRequest) => {
      if (!authedFetch || !surgeryId) return;
      const updated = await updateSurgery(authedFetch, surgeryId, data);
      setSurgery(updated);
      return updated;
    },
    [authedFetch, surgeryId]
  );

  const complete = useCallback(
    async (data: CompleteSurgeryRequest) => {
      if (!authedFetch || !surgeryId) return;
      const updated = await completeSurgery(authedFetch, surgeryId, data);
      setSurgery(updated);
      return updated;
    },
    [authedFetch, surgeryId]
  );

  const cancel = useCallback(async () => {
    if (!authedFetch || !surgeryId) return;
    const updated = await cancelSurgery(authedFetch, surgeryId);
    setSurgery(updated);
    return updated;
  }, [authedFetch, surgeryId]);

  return { surgery, loading, error, refetch, update, complete, cancel };
}
