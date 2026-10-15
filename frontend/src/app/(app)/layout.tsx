import { Suspense } from "react";

import { AppShell } from "@/components/shell/app-shell";

// Everything here is client rendered behind sign-in, so there is no static
// shell worth validating for instant navigation.
export const instant = false;

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
