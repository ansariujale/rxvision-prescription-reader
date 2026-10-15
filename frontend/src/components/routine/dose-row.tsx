"use client";

import { motion } from "motion/react";
import Link from "next/link";

import type { RoutineEntry } from "@/lib/types";
import { EASE } from "@/components/ui/motion";

const CAPSULE = /capsule|\bcap\b/i;
const LIQUID = /syrup|suspension|solution/i;
const DROPS = /\bdrops?\b/i;
const MILLILITRES = /\bml\b/i;

function unit(name: string): string {
  if (CAPSULE.test(name)) return "capsule";
  if (LIQUID.test(name)) return "dose";
  if (DROPS.test(name)) return "drop";
  return "tablet";
}

function amount(e: RoutineEntry): string | null {
  if (e.dose) return e.dose;
  // Liquids are usually written as a volume ("10 ml"), which reads better than "1 dose".
  if (e.strength && MILLILITRES.test(e.strength)) return e.strength;
  if (!e.quantity) return null;
  const q = e.quantity === "1/2" ? "½" : e.quantity;
  const u = unit(e.name);
  return q === "1" || q === "½" ? `${q} ${u}` : `${q} ${u}s`;
}

export function DoseRow({
  entry,
  onToggle,
  disabled,
  index,
}: {
  entry: RoutineEntry;
  onToggle: () => void;
  disabled?: boolean;
  index: number;
}) {
  const meta = [amount(entry), entry.timing].filter(Boolean).join(" · ");
  const checkFlag = entry.flags.includes("check_frequency");

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: Math.min(index, 8) * 0.035 }}
      className="group flex items-center gap-4 py-4"
    >
      <button
        onClick={onToggle}
        disabled={disabled}
        aria-pressed={entry.taken}
        aria-label={entry.taken ? `Mark ${entry.name} as not taken` : `Mark ${entry.name} as taken`}
        className={`relative grid size-9 shrink-0 place-items-center rounded-full border transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-40 ${
          entry.taken ? "border-accent bg-accent" : "border-line-strong hover:border-ink/50"
        }`}
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="var(--paper)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <motion.path
            d="M5 12.5l4.5 4.5L19 7.5"
            initial={false}
            animate={{ pathLength: entry.taken ? 1 : 0, opacity: entry.taken ? 1 : 0 }}
            transition={{ duration: 0.35, ease: EASE }}
          />
        </svg>
      </button>

      <div className={`min-w-0 flex-1 transition-opacity duration-300 ${entry.taken ? "opacity-50" : ""}`}>
        <div className="flex items-baseline gap-2">
          {entry.medicine_id ? (
            <Link
              href={`/medicines/${entry.medicine_id}`}
              className="truncate text-[17px] font-medium decoration-line-strong underline-offset-4 hover:underline"
            >
              {entry.name}
            </Link>
          ) : (
            <p className="truncate text-[17px] font-medium">{entry.name}</p>
          )}
        </div>
        <p className="mt-0.5 truncate text-[14px] text-muted">
          {meta || entry.frequency || "As prescribed"}
          {checkFlag && <span className="text-warn"> · check how often</span>}
        </p>
      </div>

      <div className="shrink-0 text-right">
        {entry.flags.includes("no_duration") ? (
          <p className="text-[13px] text-muted">No end date</p>
        ) : (
          <p className="tabular text-[13px] text-ink-2">
            Day {entry.day_of_course}
            <span className="text-muted"> of {entry.total_days}</span>
          </p>
        )}
        <Link href={`/prescriptions/${entry.scan_id}`} className="block max-w-[140px] truncate text-[12px] text-muted hover:text-ink">
          {entry.scan_title}
        </Link>
      </div>
    </motion.li>
  );
}
