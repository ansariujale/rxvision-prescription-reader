"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import { useMe } from "@/lib/hooks";

/** Signed-in user, redirecting to /login when the session is missing. */
export function useAuthGuard() {
  const { data: user, error, isLoading } = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const unauthorised = error instanceof ApiError && error.status === 401;

  useEffect(() => {
    if (unauthorised) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [unauthorised, pathname, router]);

  return { user, ready: !!user && !unauthorised, error: unauthorised ? undefined : error, isLoading };
}

export function useSignOut() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  return async () => {
    await api.post("/auth/logout").catch(() => {});
    await mutate(() => true, undefined, { revalidate: false });
    router.replace("/login");
  };
}
