"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";
import { SWRConfig } from "swr";

import { ToastProvider } from "@/components/ui/toast";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user">
      <SWRConfig value={{ revalidateOnFocus: true, dedupingInterval: 1000 }}>
        <ToastProvider>{children}</ToastProvider>
      </SWRConfig>
    </MotionConfig>
  );
}
