"use client";

import { motion } from "motion/react";
import { useState } from "react";

import { isoDay } from "@/lib/format";
import type { Scan } from "@/lib/types";
import { inputClass } from "@/components/ui/field";

import type { ScanPatch } from "./use-scan-editor";

export function RoutineSwitch({
  on,
  onChange,
  disabled,
}: {
  on: boolean;
  onChange: (on: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-300 disabled:opacity-50 ${
        on ? "bg-accent" : "bg-line-strong"
      }`}
    >
      <motion.span
        className="absolute top-1 left-1 size-5 rounded-full bg-paper shadow-sm"
        animate={{ x: on ? 20 : 0 }}
        transition={{ type: "spring", stiffness: 600, damping: 35 }}
      />
    </button>
  );
}

/** Start date, doctor and the routine switch for one prescription. */
export function PrescriptionMeta({
  scan,
  onChange,
  showRoutine = true,
}: {
  scan: Scan;
  onChange: (p: ScanPatch) => Promise<boolean>;
  showRoutine?: boolean;
}) {
  const [doctor, setDoctor] = useState(scan.doctor ?? "");
  const start = scan.prescribed_on ?? scan.created_at.slice(0, 10);
  const ready = scan.status === "done";

  return (
    <div className="divide-y divide-line rounded-tile border border-line bg-surface">
      {showRoutine && (
      <div className="flex items-center justify-between gap-6 p-5">
        <div>
          <p className="text-[15px] font-medium">In my routine</p>
          <p className="mt-0.5 text-[13px] text-muted">
            {scan.in_routine ? "Shows up on Today until the course ends." : "Add it to see daily doses on Today."}
          </p>
        </div>
        <RoutineSwitch on={scan.in_routine} disabled={!ready} onChange={(on) => onChange({ in_routine: on })} />
      </div>
      )}
      <div className="flex flex-wrap gap-4 p-5">
        <label className="block min-w-[150px] flex-1">
          <span className="mb-1.5 block text-[13px] font-medium text-ink-2">Started on</span>
          <input
            type="date"
            className={inputClass}
            value={start}
            max={isoDay()}
            onChange={(e) => e.target.value && onChange({ prescribed_on: e.target.value })}
          />
        </label>
        <label className="block min-w-[180px] flex-[2]">
          <span className="mb-1.5 block text-[13px] font-medium text-ink-2">Doctor</span>
          <input
            className={inputClass}
            value={doctor}
            maxLength={160}
            placeholder="Optional"
            onChange={(e) => setDoctor(e.target.value)}
            onBlur={() => doctor.trim() !== (scan.doctor ?? "") && onChange({ doctor: doctor.trim() || null })}
          />
        </label>
      </div>
    </div>
  );
}
