import type { ScanStatus } from "@/lib/types";

const DOT: Record<ScanStatus, string> = {
  queued: "bg-muted animate-pulse",
  processing: "bg-warn animate-pulse",
  done: "bg-accent",
  failed: "bg-danger",
};

const LABEL: Record<ScanStatus, string> = {
  queued: "Queued",
  processing: "Reading",
  done: "Done",
  failed: "Failed",
};

export function StatusDot({ status }: { status: ScanStatus }) {
  return <span className={`size-2 shrink-0 rounded-full ${DOT[status]}`} aria-label={LABEL[status]} />;
}

export function StatusLabel({ status }: { status: ScanStatus }) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-muted">
      <StatusDot status={status} />
      {LABEL[status]}
    </span>
  );
}
