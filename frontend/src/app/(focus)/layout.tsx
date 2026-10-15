import { Suspense } from "react";

import { FocusShell } from "@/components/shell/focus-shell";

// Client rendered behind sign-in; nothing static to validate.
export const instant = false;

export default function FocusLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense>
      <FocusShell>{children}</FocusShell>
    </Suspense>
  );
}
