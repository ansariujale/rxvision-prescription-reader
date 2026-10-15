"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import type { MedicineHit, MyMedicine, Page, ScanSummary } from "@/lib/types";
import { ArrowRight, Search } from "@/components/ui/icons";
import { EASE } from "@/components/ui/motion";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  href: string;
}

const PAGES: Command[] = [
  { id: "p-today", group: "Go to", label: "Today", hint: "Your routine", href: "/today" },
  { id: "p-scan", group: "Go to", label: "New scan", hint: "Read a prescription", href: "/scan" },
  { id: "p-rx", group: "Go to", label: "Prescriptions", href: "/prescriptions" },
  { id: "p-med", group: "Go to", label: "Medicines", href: "/medicines" },
  { id: "p-set", group: "Go to", label: "Settings", href: "/settings" },
];

const PaletteContext = createContext<() => void>(() => {});
export const useOpenPalette = () => useContext(PaletteContext);

function useResults(query: string, open: boolean): Command[] {
  const [remote, setRemote] = useState<Command[]>([]);
  const q = query.trim();

  useEffect(() => {
    if (!open || q.length < 2) return;
    let live = true;
    const t = setTimeout(async () => {
      const enc = encodeURIComponent(q);
      const [scans, mine, catalogue] = await Promise.all([
        api.get<Page<ScanSummary>>(`/scans?q=${enc}&limit=4`).catch(() => null),
        api.get<MyMedicine[]>(`/me/medicines?q=${enc}`).catch(() => []),
        api.get<MedicineHit[]>(`/medicines/search?q=${enc}&limit=5`).catch(() => []),
      ]);
      if (!live) return;
      const mineIds = new Set(mine.map((m) => m.medicine?.id));
      setRemote([
        ...(scans?.items ?? []).map((s) => ({
          id: `s-${s.id}`, group: "Prescriptions", label: s.title,
          hint: s.preview.slice(0, 2).join(", "), href: `/prescriptions/${s.id}`,
        })),
        ...mine.slice(0, 4).map((m) => ({
          id: `m-${m.key}`, group: "Your medicines", label: m.name,
          hint: m.active ? "Taking now" : undefined,
          href: m.medicine ? `/medicines/${m.medicine.id}` : `/prescriptions/${m.uses[0].scan_id}`,
        })),
        ...catalogue
          .filter((h) => !mineIds.has(h.id))
          .map((h) => ({ id: `c-${h.id}`, group: "Catalogue", label: h.name, href: `/medicines/${h.id}` })),
      ]);
    }, 140);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q, open]);

  return useMemo(() => {
    const lower = q.toLowerCase();
    const pages = PAGES.filter((p) => !lower || p.label.toLowerCase().includes(lower));
    return q.length < 2 ? pages : [...pages, ...remote];
  }, [q, remote]);
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const results = useResults(query, open);

  const show = useCallback(() => {
    setQuery("");
    setActive(0);
    setOpen(true);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => {
          if (!o) {
            setQuery("");
            setActive(0);
          }
          return !o;
        });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function go(cmd: Command | undefined) {
    if (!cmd) return;
    setOpen(false);
    router.push(cmd.href);
  }

  return (
    <PaletteContext.Provider value={show}>
      {children}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-50 flex items-start justify-center bg-black/30 px-4 pt-[12vh] backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
          >
            <motion.div
              role="dialog"
              aria-label="Search and jump"
              initial={{ opacity: 0, y: -8, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -6, scale: 0.98 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="w-full max-w-xl overflow-hidden rounded-tile border border-line bg-surface shadow-2xl shadow-black/10"
            >
              <div className="flex items-center gap-3 border-b border-line px-5">
                <Search className="size-4 text-muted" />
                <input
                  ref={input}
                  autoFocus
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setActive(0);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowDown") {
                      e.preventDefault();
                      setActive((a) => Math.min(a + 1, results.length - 1));
                    } else if (e.key === "ArrowUp") {
                      e.preventDefault();
                      setActive((a) => Math.max(a - 1, 0));
                    } else if (e.key === "Enter") {
                      e.preventDefault();
                      go(results[active]);
                    } else if (e.key === "Escape") {
                      setOpen(false);
                    }
                  }}
                  placeholder="Search prescriptions, medicines, pages"
                  className="h-14 flex-1 bg-transparent text-[16px] text-ink placeholder:text-muted focus:outline-none focus-visible:outline-none"
                />
                <kbd className="rounded-md border border-line px-1.5 py-0.5 font-mono text-[11px] text-muted">esc</kbd>
              </div>
              <ul className="max-h-[50vh] overflow-y-auto py-2">
                {results.length === 0 && (
                  <li className="px-5 py-8 text-center text-[14px] text-muted">Nothing found for that.</li>
                )}
                {results.map((cmd, i) => {
                  const header = i === 0 || results[i - 1].group !== cmd.group ? cmd.group : null;
                  return (
                    <li key={cmd.id}>
                      {header && (
                        <p className="px-5 pt-3 pb-1.5 text-[11px] font-medium tracking-wide text-muted uppercase">
                          {header}
                        </p>
                      )}
                      <button
                        onMouseMove={() => setActive(i)}
                        onClick={() => go(cmd)}
                        className={`flex w-full items-center gap-3 px-5 py-2.5 text-left transition-colors ${
                          i === active ? "bg-surface-2" : ""
                        }`}
                      >
                        <span className="min-w-0 flex-1 truncate text-[15px]">{cmd.label}</span>
                        {cmd.hint && <span className="shrink-0 truncate text-[13px] text-muted">{cmd.hint}</span>}
                        <ArrowRight className={`size-3.5 shrink-0 transition-opacity ${i === active ? "opacity-60" : "opacity-0"}`} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PaletteContext.Provider>
  );
}
