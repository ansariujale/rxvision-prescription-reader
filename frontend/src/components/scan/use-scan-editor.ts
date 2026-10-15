"use client";

import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import { useScan } from "@/lib/hooks";
import type { Item, ItemPatch, Scan } from "@/lib/types";
import { useToast } from "@/components/ui/toast";

export interface ScanPatch {
  title?: string;
  prescribed_on?: string;
  doctor?: string | null;
  in_routine?: boolean;
}

/** A scan plus every mutation the review and prescription screens need. */
export function useScanEditor(id: string | null) {
  const swr = useScan(id);
  const scan = swr.data;
  const { mutate } = swr;
  const { mutate: mutateGlobal } = useSWRConfig();
  const toast = useToast();

  const fail = (err: unknown) => toast(err instanceof ApiError ? err.message : "That did not work", "error");
  // Lists, the routine and medicine pages all derive from scans.
  const refreshDerived = () =>
    mutateGlobal(
      (key) =>
        typeof key === "string" &&
        (key.startsWith("/scans?") || key.startsWith("/routine") || key.startsWith("/me/") || key.includes("/history")),
    );

  const withItem = (s: Scan, item: Item): Scan => ({ ...s, items: s.items.map((i) => (i.id === item.id ? item : i)) });

  async function updateItem(item: Item, patch: ItemPatch) {
    if (!scan) return;
    const optimistic = withItem(scan, { ...item, ...patch, status: patch.status ?? "edited" } as Item);
    try {
      await mutate(async () => withItem(scan, await api.patch<Item>(`/scans/${scan.id}/items/${item.id}`, patch)), {
        optimisticData: optimistic,
        rollbackOnError: true,
        revalidate: false,
      });
      refreshDerived();
    } catch (err) {
      fail(err);
    }
  }

  async function deleteItem(item: Item) {
    if (!scan) return;
    const next = { ...scan, items: scan.items.filter((i) => i.id !== item.id) };
    try {
      await mutate(
        async () => {
          await api.del(`/scans/${scan.id}/items/${item.id}`);
          return next;
        },
        { optimisticData: next, rollbackOnError: true, revalidate: false },
      );
      toast(`Removed ${item.name}`);
      refreshDerived();
    } catch (err) {
      fail(err);
    }
  }

  async function addItem(patch: ItemPatch) {
    if (!scan) return;
    try {
      const item = await api.post<Item>(`/scans/${scan.id}/items`, patch);
      await mutate({ ...scan, items: [...scan.items, item] }, { revalidate: false });
      refreshDerived();
    } catch (err) {
      fail(err);
      throw err;
    }
  }

  async function confirmAll() {
    if (!scan) return;
    try {
      await mutate(await api.post<Scan>(`/scans/${scan.id}/items/confirm-all`), { revalidate: false });
      refreshDerived();
    } catch (err) {
      fail(err);
    }
  }

  async function updateScan(patch: ScanPatch): Promise<boolean> {
    if (!scan) return false;
    try {
      await mutate(await api.patch<Scan>(`/scans/${scan.id}`, patch), { revalidate: false });
      refreshDerived();
      return true;
    } catch (err) {
      fail(err);
      return false;
    }
  }

  async function retry() {
    if (!scan) return;
    try {
      await api.post(`/scans/${scan.id}/retry`);
      await mutate();
    } catch (err) {
      fail(err);
    }
  }

  async function remove(): Promise<boolean> {
    if (!scan) return false;
    try {
      await api.del(`/scans/${scan.id}`);
      refreshDerived();
      return true;
    } catch (err) {
      fail(err);
      return false;
    }
  }

  return { ...swr, scan, updateItem, deleteItem, addItem, confirmAll, updateScan, retry, remove };
}
