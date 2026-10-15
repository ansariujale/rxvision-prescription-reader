"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { MedicineHit } from "@/lib/types";
import { inputClass } from "@/components/ui/field";

/**
 * Free text with catalogue suggestions. Typing sets the name; picking a
 * suggestion also links the catalogue entry.
 */
export function MedicineSearch({
  value,
  onChange,
  onPick,
  autoFocus,
  placeholder = "Medicine name",
}: {
  value: string;
  onChange: (text: string) => void;
  onPick: (hit: MedicineHit) => void;
  autoFocus?: boolean;
  placeholder?: string;
}) {
  const [hits, setHits] = useState<MedicineHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listId = useId();
  const typed = useRef(false);
  const visible = open && value.trim().length >= 2 && hits.length > 0;

  useEffect(() => {
    if (!typed.current) return;
    const q = value.trim();
    if (q.length < 2) return;
    const controller = new AbortController();
    const t = setTimeout(async () => {
      try {
        const res = await api.get<MedicineHit[]>(`/medicines/search?q=${encodeURIComponent(q)}&limit=6`);
        if (!controller.signal.aborted) {
          setHits(res);
          setActive(0);
          setOpen(true);
        }
      } catch {
        /* suggestions are best effort */
      }
    }, 160);
    return () => {
      controller.abort();
      clearTimeout(t);
    };
  }, [value]);

  function pick(hit: MedicineHit) {
    typed.current = false;
    setOpen(false);
    onPick(hit);
  }

  return (
    <div className="relative">
      <input
        className={inputClass}
        value={value}
        autoFocus={autoFocus}
        placeholder={placeholder}
        role="combobox"
        aria-expanded={visible}
        aria-controls={listId}
        aria-autocomplete="list"
        onChange={(e) => {
          typed.current = true;
          onChange(e.target.value);
        }}
        onFocus={() => hits.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(e) => {
          if (!visible) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => (a + 1) % hits.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => (a - 1 + hits.length) % hits.length);
          } else if (e.key === "Enter") {
            e.preventDefault();
            pick(hits[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      <AnimatePresence>
        {visible && (
          <motion.ul
            id={listId}
            role="listbox"
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4, transition: { duration: 0.12 } }}
            transition={{ duration: 0.18 }}
            className="absolute inset-x-0 top-full z-20 mt-1.5 overflow-hidden rounded-xl border border-line bg-surface py-1 shadow-xl shadow-black/5"
          >
            {hits.map((hit, i) => (
              <li
                key={hit.id}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(hit);
                }}
                onMouseEnter={() => setActive(i)}
                className={`cursor-pointer px-3.5 py-2 text-[14px] ${i === active ? "bg-surface-2 text-ink" : "text-ink-2"}`}
              >
                {hit.name}
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
