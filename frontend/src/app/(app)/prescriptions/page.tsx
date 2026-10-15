"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useDeferredValue, useState } from "react";

import { formatDay, plural } from "@/lib/format";
import { useScanHistory } from "@/lib/hooks";
import { Button, ButtonLink } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";
import { ArrowRight, Plus, Search } from "@/components/ui/icons";
import { EASE, Reveal } from "@/components/ui/motion";
import { StatusLabel } from "@/components/scan/status";

const FILTERS = [
  { key: "all", label: "All", value: undefined },
  { key: "routine", label: "In routine", value: true },
  { key: "archive", label: "Not in routine", value: false },
] as const;

export default function Prescriptions() {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["key"]>("all");
  const q = useDeferredValue(query.trim());
  const current = FILTERS.find((f) => f.key === filter)!;
  const { items, total, hasMore, size, setSize, isLoading, isValidating } = useScanHistory(q, current.value);

  return (
    <div className="mx-auto max-w-4xl">
      <Reveal className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-headline">Prescriptions</h1>
          <p className="mt-3 text-[17px] text-muted">
            {isLoading ? " " : q ? `${plural(total, "match", "matches")} for “${q}”` : plural(total, "prescription")}
          </p>
        </div>
        <label className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Title, doctor or medicine"
            className={`${inputClass} pl-10`}
            aria-label="Search prescriptions"
          />
        </label>
      </Reveal>

      <Reveal delay={0.05} className="mt-8 mb-2 flex gap-1">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`relative rounded-full px-3.5 py-1.5 text-[14px] transition-colors ${
              filter === f.key ? "text-ink" : "text-muted hover:text-ink"
            }`}
          >
            {filter === f.key && (
              <motion.span layoutId="rx-filter" className="absolute inset-0 rounded-full bg-surface-2" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
            )}
            <span className="relative">{f.label}</span>
          </button>
        ))}
      </Reveal>

      {isLoading ? (
        <div className="mt-6 space-y-6">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <Reveal className="mt-4 border-t border-line py-20">
          <p className="font-display text-title text-muted">
            {q || filter !== "all" ? "Nothing matches that." : "No prescriptions yet."}
          </p>
          {!q && filter === "all" && (
            <ButtonLink href="/scan" className="mt-8" icon={<Plus />}>
              Scan your first prescription
            </ButtonLink>
          )}
        </Reveal>
      ) : (
        <ul className="mt-4 border-t border-line">
          <AnimatePresence initial={false}>
            {items.map((scan, i) => (
              <motion.li
                key={scan.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.4, ease: EASE, delay: Math.min(i % 20, 10) * 0.03 }}
                className="border-b border-line"
              >
                <Link href={`/prescriptions/${scan.id}`} className="group flex items-center gap-6 py-6">
                  <div className="hidden w-28 shrink-0 sm:block">
                    <p className="tabular text-[14px] text-ink-2">{formatDay(scan.prescribed_on ?? scan.created_at.slice(0, 10))}</p>
                    <p className="mt-1 truncate text-[12px] text-muted">{scan.doctor ?? " "}</p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <p className="truncate font-display text-[28px] leading-tight transition-transform duration-300 ease-out-soft group-hover:translate-x-1">
                        {scan.title}
                      </p>
                      {scan.in_routine && <span className="size-1.5 shrink-0 rounded-full bg-accent" title="In routine" />}
                    </div>
                    <p className="mt-1 truncate text-[14px] text-muted">
                      {scan.preview.length
                        ? scan.preview.join(", ") +
                          (scan.item_count > scan.preview.length ? `, +${scan.item_count - scan.preview.length}` : "")
                        : scan.status === "done"
                          ? "No medicines found"
                          : " "}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-5">
                    {scan.status !== "done" && <StatusLabel status={scan.status} />}
                    <ArrowRight className="size-4 text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-ink" />
                  </div>
                </Link>
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}

      {hasMore && (
        <div className="mt-10 flex justify-center">
          <Button variant="secondary" onClick={() => setSize(size + 1)} loading={isValidating}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}
