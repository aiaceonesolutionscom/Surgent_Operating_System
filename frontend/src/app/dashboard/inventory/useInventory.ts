import { useCallback, useEffect, useState } from "react";
import {
  listInventoryItems,
  createInventoryItem,
  updateInventoryItem,
  type InventoryItemResponse,
  type CreateInventoryItemRequest,
  type UpdateInventoryItemRequest
} from "../../../api/entities";

type AuthedFetch = (<T>(path: string, init?: RequestInit) => Promise<T>) | null;

export function useInventory(authedFetch: AuthedFetch) {
  const [items, setItems] = useState<InventoryItemResponse[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    if (!authedFetch) {
      setItems([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const data = await listInventoryItems(authedFetch);
      setItems(data || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [authedFetch]);

  useEffect(() => {
    refetch();
  }, [refetch]);

  const create = useCallback(
    async (data: CreateInventoryItemRequest) => {
      if (!authedFetch) return null;
      const item = await createInventoryItem(authedFetch, data);
      setItems((prev) => [...prev, item].sort((a, b) => a.name.localeCompare(b.name)));
      return item;
    },
    [authedFetch]
  );

  const update = useCallback(
    async (id: string, data: UpdateInventoryItemRequest) => {
      if (!authedFetch) return null;
      const item = await updateInventoryItem(authedFetch, id, data);
      setItems((prev) => prev.map((i) => (i.id === id ? item : i)));
      return item;
    },
    [authedFetch]
  );

  return { items, loading, refetch, create, update };
}