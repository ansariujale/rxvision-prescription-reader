"use client";

import { motion } from "motion/react";

import { parseDay } from "@/lib/format";
import type { DayCount } from "@/lib/types";

const DOW = new Intl.DateTimeFormat("en-IN", { weekday: "narrow" });

export function WeekStrip({
  week,
  selected,
  today,
  onSelect,
}: {
  week: DayCount[];
  selected: string;
  today: string;
  onSelect: (day: string) => void;
}) {
  return (
    <div className="flex gap-1.5">
      {week.map((d) => {
        const date = parseDay(d.day);
        const active = d.day === selected;
        const isToday = d.day === today;
        const pct = d.total ? d.taken / d.total : 0;
        return (
          <button
            key={d.day}
            onClick={() => onSelect(d.day)}
            aria-pressed={active}
            aria-label={date.toDateString()}
            className="relative flex min-w-0 flex-1 flex-col items-center gap-1.5 rounded-2xl py-3 transition-colors hover:bg-surface-2/60"
          >
            {active && (
              <motion.span
                layoutId="week-day"
                className="absolute inset-0 rounded-2xl border border-line bg-surface"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
            <span className={`relative text-[12px] ${isToday ? "font-medium text-ink" : "text-muted"}`}>
              {DOW.format(date)}
            </span>
            <span className={`relative tabular font-display text-[24px] leading-none ${active ? "text-ink" : "text-ink-2"}`}>
              {date.getDate()}
            </span>
            <span className="relative h-1 w-6 overflow-hidden rounded-full bg-line">
              {d.total > 0 && (
                <motion.span
                  className={`absolute inset-y-0 left-0 rounded-full ${pct >= 1 ? "bg-accent" : "bg-ink-2"}`}
                  initial={false}
                  animate={{ width: `${Math.max(pct * 100, d.total ? 8 : 0)}%`, opacity: pct ? 1 : 0.35 }}
                  transition={{ duration: 0.5 }}
                />
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}
