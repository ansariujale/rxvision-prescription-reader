"use client";

import useSWR from "swr";
import useSWRInfinite from "swr/infinite";

import { fetcher } from "./api";
import type {
  Alternative,
  Medicine,
  MedicineUse,
  MyMedicine,
  Page,
  Providers,
  Routine,
  Scan,
  ScanSummary,
  User,
} from "./types";

export function useMe() {
  return useSWR<User>("/auth/me", fetcher, { shouldRetryOnError: false, revalidateOnFocus: false });
}

const PENDING = new Set(["queued", "processing"]);

export function useScan(id: string | null) {
  return useSWR<Scan>(id ? `/scans/${id}` : null, fetcher, {
    // Poll while the background job runs, then stop.
    refreshInterval: (scan) => (scan && PENDING.has(scan.status) ? 1200 : 0),
  });
}

export function useProviders() {
  return useSWR<Providers>("/providers", fetcher, { revalidateOnFocus: false });
}

export function useRoutine(day: string) {
  return useSWR<Routine>(`/routine?day=${day}`, fetcher, { keepPreviousData: true });
}

export function useMyMedicines(q = "") {
  return useSWR<MyMedicine[]>(`/me/medicines${q ? `?q=${encodeURIComponent(q)}` : ""}`, fetcher, {
    keepPreviousData: true,
  });
}

export function useMedicine(id: number | null) {
  return useSWR<Medicine>(id ? `/medicines/${id}` : null, fetcher);
}

export function useAlternatives(id: number | null) {
  return useSWR<Alternative[]>(id ? `/medicines/${id}/alternatives` : null, fetcher);
}

export function useMedicineHistory(id: number | null) {
  return useSWR<MedicineUse[]>(id ? `/medicines/${id}/history` : null, fetcher);
}

const PAGE = 20;

export function useScanHistory(q: string, inRoutine?: boolean) {
  const swr = useSWRInfinite<Page<ScanSummary>>(
    (index, previous) => {
      if (previous && previous.offset + previous.items.length >= previous.total) return null;
      const params = new URLSearchParams({ limit: String(PAGE), offset: String(index * PAGE) });
      if (q) params.set("q", q);
      if (inRoutine !== undefined) params.set("in_routine", String(inRoutine));
      return `/scans?${params}`;
    },
    fetcher,
  );
  const pages = swr.data ?? [];
  const items = pages.flatMap((p) => p.items);
  const total = pages[0]?.total ?? 0;
  return { ...swr, items, total, hasMore: items.length < total };
}
