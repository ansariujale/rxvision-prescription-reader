"use client";

import { motion } from "motion/react";

import { EASE } from "@/components/ui/motion";

export function ProgressRing({ taken, total, size = 132 }: { taken: number; total: number; size?: number }) {
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = total ? taken / total : 0;
  const done = total > 0 && taken >= total;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={done ? "var(--accent)" : "var(--ink)"}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: c * (1 - pct) }}
          transition={{ duration: 0.9, ease: EASE }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="tabular font-display text-[40px] leading-none">
          {taken}
          <span className="text-muted">/{total}</span>
        </span>
        <span className="mt-1 text-[12px] text-muted">{done ? "All done" : "doses"}</span>
      </div>
    </div>
  );
}
