"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import { addDays, formatDay, greeting, isoDay, parseDay, plural, SLOT_HINT, SLOT_LABEL } from "@/lib/format";
import { useMe, useRoutine } from "@/lib/hooks";
import type { Routine, RoutineEntry } from "@/lib/types";
import { ButtonLink } from "@/components/ui/button";
import { ArrowLeft, ArrowRight, Plus } from "@/components/ui/icons";
import { EASE, Reveal } from "@/components/ui/motion";
import { useToast } from "@/components/ui/toast";
import { DoseRow } from "@/components/routine/dose-row";
import { ProgressRing } from "@/components/routine/progress-ring";
import { WeekStrip } from "@/components/routine/week-strip";

const WEEKDAY = new Intl.DateTimeFormat("en-IN", { weekday: "long" });
const MONTH_DAY = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long" });

function toggled(routine: Routine, target: RoutineEntry): Routine {
  const flip = (e: RoutineEntry) =>
    e.item_id === target.item_id && e.slot === target.slot ? { ...e, taken: !e.taken } : e;
  const delta = target.slot === "as_needed" ? 0 : target.taken ? -1 : 1;
  return {
    ...routine,
    slots: routine.slots.map((s) => ({ ...s, entries: s.entries.map(flip) })),
    as_needed: routine.as_needed.map(flip),
    taken: routine.taken + delta,
    week: routine.week.map((d) => (d.day === routine.day ? { ...d, taken: d.taken + delta } : d)),
  };
}

function EmptyRoutine() {
  return (
    <Reveal className="max-w-2xl py-10">
      <p className="font-display text-[clamp(2.5rem,6vw,4.5rem)] leading-[0.95]">
        Your routine starts
        <span className="italic text-muted"> with a prescription.</span>
      </p>
      <p className="mt-6 max-w-lg text-[17px] leading-relaxed text-ink-2">
        Scan one, check what was read, and add it to your routine. You will see what to take each
        morning, afternoon and night, and how many days are left.
      </p>
      <div className="mt-10 flex flex-wrap gap-3">
        <ButtonLink href="/scan" size="lg" icon={<Plus />}>
          Scan a prescription
        </ButtonLink>
        <ButtonLink href="/prescriptions" size="lg" variant="secondary">
          Use one you already scanned
        </ButtonLink>
      </div>
    </Reveal>
  );
}

export default function Today() {
  const today = isoDay();
  const [day, setDay] = useState(today);
  const { data: user } = useMe();
  const { data: routine, mutate, isLoading } = useRoutine(day);
  const { mutate: mutateGlobal } = useSWRConfig();
  const toast = useToast();

  const isFuture = day > today;
  const date = parseDay(day);

  async function toggle(entry: RoutineEntry) {
    if (!routine) return;
    try {
      await mutate(
        async () => {
          await api.put("/routine/doses", { item_id: entry.item_id, day, slot: entry.slot, taken: !entry.taken });
          return toggled(routine, entry);
        },
        { optimisticData: toggled(routine, entry), rollbackOnError: true, revalidate: false },
      );
      mutateGlobal((k) => typeof k === "string" && k.startsWith("/routine?") && k !== `/routine?day=${day}`);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save that", "error");
    }
  }

  if (isLoading && !routine) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-16 w-72" />
        <div className="skeleton h-20" />
        <div className="skeleton h-64" />
      </div>
    );
  }

  if (routine && routine.prescriptions === 0) {
    return (
      <div>
        <p className="text-[15px] text-muted">{greeting()}, {user?.name.split(" ")[0]}</p>
        <EmptyRoutine />
      </div>
    );
  }

  const done = !!routine && routine.total > 0 && routine.taken >= routine.total;

  return (
    <div className="flex flex-col gap-12 lg:flex-row lg:items-start">
      <div className="min-w-0 flex-1">
        <Reveal className="flex items-end justify-between gap-6">
          <div>
            <p className="text-[15px] text-muted">
              {day === today ? `${greeting()}, ${user?.name.split(" ")[0]}` : day < today ? "Looking back" : "Looking ahead"}
            </p>
            <AnimatePresence mode="wait" initial={false}>
              <motion.h1
                key={day}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, ease: EASE }}
                className="font-display text-headline"
              >
                {day === today ? "Today" : WEEKDAY.format(date)}
                <span className="italic text-muted">, {MONTH_DAY.format(date)}</span>
              </motion.h1>
            </AnimatePresence>
          </div>
        </Reveal>

        <Reveal delay={0.05} className="mt-8 flex items-center gap-2">
          <button
            onClick={() => setDay(addDays(day, -7))}
            aria-label="Previous week"
            className="grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink"
          >
            <ArrowLeft />
          </button>
          <div className="min-w-0 flex-1">
            {routine && <WeekStrip week={routine.week} selected={day} today={today} onSelect={setDay} />}
          </div>
          <button
            onClick={() => setDay(addDays(day, 7))}
            aria-label="Next week"
            className="grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-ink"
          >
            <ArrowRight />
          </button>
        </Reveal>
        {day !== today && (
          <button onClick={() => setDay(today)} className="mt-3 text-[13px] text-muted underline underline-offset-4 hover:text-ink">
            Back to today
          </button>
        )}

        <AnimatePresence mode="wait">
          <motion.div
            key={day}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-10"
          >
            {routine && routine.total === 0 && routine.as_needed.length === 0 ? (
              <div className="border-t border-line py-12">
                <p className="font-display text-title text-muted">Nothing scheduled.</p>
                <p className="mt-2 text-[15px] text-muted">
                  No prescription in your routine runs on {formatDay(day)}.
                </p>
              </div>
            ) : (
              routine?.slots.map((slot) => (
                <section key={slot.slot} className="border-t border-line pt-6 pb-4">
                  <div className="flex items-baseline justify-between">
                    <h2 className="font-display text-[28px] leading-none">{SLOT_LABEL[slot.slot]}</h2>
                    <p className="text-[13px] text-muted">
                      {slot.entries.filter((e) => e.taken).length} of {slot.entries.length} · {SLOT_HINT[slot.slot]}
                    </p>
                  </div>
                  <ul className="mt-2 divide-y divide-line/70">
                    {slot.entries.map((e, i) => (
                      <DoseRow key={`${e.item_id}-${e.slot}`} entry={e} index={i} onToggle={() => toggle(e)} disabled={isFuture} />
                    ))}
                  </ul>
                </section>
              ))
            )}

            {routine && routine.as_needed.length > 0 && (
              <section className="border-t border-line pt-6 pb-4">
                <div className="flex items-baseline justify-between">
                  <h2 className="font-display text-[28px] leading-none">{SLOT_LABEL.as_needed}</h2>
                  <p className="text-[13px] text-muted">{SLOT_HINT.as_needed}</p>
                </div>
                <ul className="mt-2 divide-y divide-line/70">
                  {routine.as_needed.map((e, i) => (
                    <DoseRow key={e.item_id} entry={e} index={i} onToggle={() => toggle(e)} disabled={isFuture} />
                  ))}
                </ul>
              </section>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {routine && (
        <aside className="flex flex-col gap-4 lg:sticky lg:top-24 lg:w-80 lg:shrink-0">
          <Reveal delay={0.1} className="flex items-center gap-6 rounded-tile border border-line bg-surface p-6">
            <ProgressRing taken={routine.taken} total={routine.total} />
            <div>
              <p className="font-display text-[24px] leading-tight">
                {routine.total === 0 ? "A quiet day" : done ? "All taken" : `${routine.total - routine.taken} to go`}
              </p>
              <p className="mt-1 text-[13px] text-muted">
                {plural(routine.prescriptions, "prescription")} in your routine
              </p>
            </div>
          </Reveal>

          {routine.ending_soon.length > 0 && (
            <Reveal delay={0.15} className="rounded-tile bg-warn-soft p-6">
              <p className="text-[13px] font-medium tracking-wide text-warn uppercase">Finishing soon</p>
              <ul className="mt-4 space-y-3">
                {routine.ending_soon.map((e) => (
                  <li key={e.item_id} className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-[15px]">{e.name}</span>
                    <span className="shrink-0 text-[13px] text-muted">
                      {e.ends_on === day ? "last day" : `until ${formatDay(e.ends_on)}`}
                    </span>
                  </li>
                ))}
              </ul>
            </Reveal>
          )}

          <Reveal delay={0.2}>
            <Link
              href="/scan"
              className="group flex items-center justify-between rounded-tile border border-dashed border-line-strong p-6 transition-colors hover:border-ink/40"
            >
              <span>
                <span className="block font-display text-[22px]">New prescription?</span>
                <span className="text-[13px] text-muted">Scan it and add it here</span>
              </span>
              <ArrowRight className="text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-ink" />
            </Link>
          </Reveal>
          <p className="px-1 text-[12px] leading-relaxed text-muted">
            Built from what was read on your prescriptions. Follow your doctor if anything differs.
          </p>
        </aside>
      )}
    </div>
  );
}
