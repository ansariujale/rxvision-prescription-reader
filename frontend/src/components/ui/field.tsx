import type { ComponentProps } from "react";

export const inputClass =
  "h-11 w-full rounded-xl border border-line bg-surface px-3.5 text-[15px] text-ink " +
  "placeholder:text-muted/70 transition-[border-color,box-shadow] duration-200 " +
  "hover:border-line-strong focus:border-ink/40 focus:outline-none focus:ring-4 focus:ring-[var(--focus)]/30";

export function Field({
  label,
  hint,
  error,
  className = "",
  ...props
}: ComponentProps<"input"> & { label: string; hint?: string; error?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{label}</span>
      <input className={inputClass} aria-invalid={!!error} {...props} />
      {error ? (
        <span className="mt-1.5 block text-[13px] text-danger">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-[13px] text-muted">{hint}</span>
      ) : null}
    </label>
  );
}
