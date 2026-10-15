"use client";

import type { ReactNode } from "react";

import { Spinner } from "@/components/ui/spinner";

import { useAuthGuard } from "./use-auth-guard";

/** Full-screen surface for single-purpose flows such as scanning. No navigation. */
export function FocusShell({ children }: { children: ReactNode }) {
  const { ready, error } = useAuthGuard();
  if (!ready) {
    return (
      <div className="grid min-h-dvh place-items-center text-muted">
        {error ? <p className="max-w-sm text-center text-[15px]">{error.message}</p> : <Spinner className="size-5" />}
      </div>
    );
  }
  return <div className="min-h-dvh">{children}</div>;
}
