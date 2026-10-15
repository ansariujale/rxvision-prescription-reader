"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useDeferredValue, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDay, plural } from "@/lib/format";
import { useMyMedicines } from "@/lib/hooks";
import type { MedicineHit, MyMedicine } from "@/lib/types";
import { ButtonLink } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";
import { ArrowRight, Plus, Search } from "@/components/ui/icons";
import { EASE, Reveal } from "@/components/ui/motion";

function hrefFor(m: MyMedicine) {
  return m.medicine ? `/medicines/${m.medicine.id}` : `/prescriptions/${m.uses[0].scan_id}`;
}

function Row({ m, index }: { m: MyMedicine; index: number }) {
  const latest = m.uses[0];
  const how = [latest.strength, latest.frequency, latest.duration].filter(Boolean).join(" · ");
  return (
    <motion.li
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: EASE, delay: Math.min(index, 12) * 0.03 }}
      className="border-b border-line"
    >
      <Link href={hrefFor(m)} className="group flex items-center gap-5 py-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <p className="truncate text-[18px] font-medium">{m.name}</p>
            {m.active && (
              <span className="shrink-0 rounded-full bg-accent-soft px-2 py-0.5 text-[12px] text-accent">Taking now</span>
            )}
            {!m.medicine && <span className="shrink-0 text-[12px] text-warn">Not in catalogue</span>}
          </div>
          <p className="mt-1 truncate text-[14px] text-muted">{m.medicine?.composition ?? how ?? ""}</p>
        </div>
        <div className="hidden shrink-0 text-right sm:block">
          <p className="text-[13px] text-ink-2">{plural(m.times, "time")}</p>
          <p className="text-[12px] text-muted">last {formatDay(m.last_prescribed)}</p>
        </div>
        <ArrowRight className="size-4 shrink-0 text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-ink" />
      </Link>
    </motion.li>
  );
}

export default function Medicines() {
  const [query, setQuery] = useState("");
  const q = useDeferredValue(query.trim());
  const { data: mine, isLoading } = useMyMedicines(q);
  const [catalogue, setCatalogue] = useState<MedicineHit[]>([]);

  useEffect(() => {
    if (q.length < 2) return;
    let live = true;
    api
      .get<MedicineHit[]>(`/medicines/search?q=${encodeURIComponent(q)}&limit=8`)
      .then((hits) => live && setCatalogue(hits))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [q]);

  const mineIds = new Set((mine ?? []).map((m) => m.medicine?.id));
  const extra = q.length >= 2 ? catalogue.filter((h) => !mineIds.has(h.id)) : [];
  const active = (mine ?? []).filter((m) => m.active);
  const past = (mine ?? []).filter((m) => !m.active);

  return (
    <div className="mx-auto max-w-4xl">
      <Reveal className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <h1 className="font-display text-headline">Medicines</h1>
          <p className="mt-3 text-[17px] text-muted">
            Everything you have been prescribed, and anything in the catalogue.
          </p>
        </div>
        <label className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search yours or the catalogue"
            className={`${inputClass} pl-10`}
            aria-label="Search medicines"
          />
        </label>
      </Reveal>

      {isLoading && !mine ? (
        <div className="mt-10 space-y-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="skeleton h-14" />
          ))}
        </div>
      ) : (
        <>
          {active.length > 0 && (
            <section className="mt-10">
              <h2 className="font-display text-[28px]">Taking now</h2>
              <ul className="mt-2 border-t border-line">
                {active.map((m, i) => <Row key={m.key} m={m} index={i} />)}
              </ul>
            </section>
          )}
          {past.length > 0 && (
            <section className="mt-12">
              <h2 className="font-display text-[28px] text-ink-2">{active.length ? "Before" : "Yours"}</h2>
              <ul className="mt-2 border-t border-line">
                {past.map((m, i) => <Row key={m.key} m={m} index={i} />)}
              </ul>
            </section>
          )}
          {mine && mine.length === 0 && !q && (
            <Reveal className="mt-10 border-t border-line py-16">
              <p className="font-display text-title text-muted">No medicines yet.</p>
              <p className="mt-2 text-[15px] text-muted">They appear here once you scan a prescription.</p>
              <ButtonLink href="/scan" className="mt-8" icon={<Plus />}>Scan a prescription</ButtonLink>
            </Reveal>
          )}
          {extra.length > 0 && (
            <section className="mt-12">
              <h2 className="font-display text-[28px] text-ink-2">From the catalogue</h2>
              <ul className="mt-2 border-t border-line">
                {extra.map((h, i) => (
                  <motion.li
                    key={h.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, ease: EASE, delay: i * 0.03 }}
                    className="border-b border-line"
                  >
                    <Link href={`/medicines/${h.id}`} className="group flex items-center justify-between gap-4 py-4">
                      <span className="truncate text-[16px]">{h.name}</span>
                      <ArrowRight className="size-4 shrink-0 text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-ink" />
                    </Link>
                  </motion.li>
                ))}
              </ul>
            </section>
          )}
          {q.length >= 2 && mine?.length === 0 && extra.length === 0 && (
            <p className="mt-10 border-t border-line py-12 font-display text-title text-muted">Nothing matches that.</p>
          )}
        </>
      )}
    </div>
  );
}
