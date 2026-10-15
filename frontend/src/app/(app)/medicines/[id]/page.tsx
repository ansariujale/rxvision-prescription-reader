"use client";

import { motion } from "motion/react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { ApiError } from "@/lib/api";
import { formatDay, plural } from "@/lib/format";
import { useAlternatives, useMedicine, useMedicineHistory } from "@/lib/hooks";
import { Bento, Tile, TileLabel } from "@/components/ui/bento";
import { buttonClass } from "@/components/ui/button";
import { ArrowLeft, ArrowRight } from "@/components/ui/icons";
import { EASE, Reveal } from "@/components/ui/motion";

function rupees(price: string | null) {
  if (!price) return null;
  const n = Number(price);
  return Number.isFinite(n) ? `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : null;
}

function splitComposition(text: string | null): string[] {
  return (text ?? "").split("+").map((p) => p.trim()).filter(Boolean);
}

export default function MedicinePage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id) || null;
  const { data: medicine, error } = useMedicine(id);
  const { data: history } = useMedicineHistory(id);
  const { data: alternatives } = useAlternatives(id);

  if (error) {
    return (
      <Reveal className="py-20">
        <h1 className="font-display text-headline">
          {error instanceof ApiError && error.status === 404 ? "Medicine not found" : "Could not load this"}
        </h1>
        <Link href="/medicines" className={buttonClass("secondary", "md", "mt-8")}>All medicines</Link>
      </Reveal>
    );
  }

  if (!medicine) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-16 w-2/3" />
        <div className="skeleton h-48" />
      </div>
    );
  }

  const parts = splitComposition(medicine.composition);
  const price = rupees(medicine.price);
  const cheaper = (alternatives ?? []).filter((a) => a.price && medicine.price && Number(a.price) < Number(medicine.price));

  return (
    <div>
      <Link href="/medicines" className="mb-8 inline-flex items-center gap-2 text-[14px] text-muted transition-colors hover:text-ink">
        <ArrowLeft className="size-3.5" /> Medicines
      </Link>

      <Bento className="lg:auto-rows-[minmax(150px,auto)]">
        <Tile className="flex flex-col justify-between sm:col-span-2 lg:col-span-3">
          <TileLabel>{medicine.type ?? "Medicine"}</TileLabel>
          <div className="mt-8">
            <h1 className="font-display text-[clamp(2.5rem,5vw,4rem)] leading-[0.95]">{medicine.name}</h1>
            {medicine.manufacturer && <p className="mt-3 text-[15px] text-muted">{medicine.manufacturer}</p>}
          </div>
        </Tile>
        <Tile tone={history?.length ? "accent" : "surface"} className="flex flex-col justify-between">
          <TileLabel className={history?.length ? "!text-accent" : ""}>Your history</TileLabel>
          <div>
            <p className="tabular font-display text-[56px] leading-none">{history?.length ?? 0}</p>
            <p className="text-[13px] text-muted">{history?.length === 1 ? "prescription" : "prescriptions"}</p>
          </div>
        </Tile>

        <Tile className="sm:col-span-2">
          <TileLabel>Composition</TileLabel>
          {parts.length ? (
            <ul className="mt-5 space-y-2">
              {parts.map((p) => (
                <li key={p} className="font-display text-[24px] leading-tight">{p}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-5 text-[15px] text-muted">Not listed in the catalogue.</p>
          )}
        </Tile>
        <Tile className="flex flex-col justify-between">
          <TileLabel>Pack</TileLabel>
          <p className="text-[17px] leading-snug">{medicine.pack_size ?? "Not listed"}</p>
        </Tile>
        <Tile className="flex flex-col justify-between">
          <TileLabel>Price</TileLabel>
          <p className="font-display text-[40px] leading-none">{price ?? <span className="text-[17px] font-sans text-muted">Not listed</span>}</p>
        </Tile>
      </Bento>

      <div className="mt-16 flex flex-col gap-16 lg:flex-row lg:items-start">
        <section className="min-w-0 flex-1">
          <Reveal>
            <h2 className="font-display text-title">Same composition</h2>
            <p className="mt-2 max-w-lg text-[15px] text-muted">
              Products with exactly the same ingredients and strengths.
              {cheaper.length > 0 && ` ${plural(cheaper.length, "costs", "cost")} less.`} Ask your pharmacist before switching.
            </p>
          </Reveal>
          {!alternatives ? (
            <div className="mt-6 space-y-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-12" />)}</div>
          ) : alternatives.length === 0 ? (
            <p className="mt-6 border-t border-line py-8 text-[15px] text-muted">No exact matches in the catalogue.</p>
          ) : (
            <ul className="mt-6 border-t border-line">
              {alternatives.map((a, i) => {
                const p = rupees(a.price);
                const less = a.price && medicine.price && Number(a.price) < Number(medicine.price);
                return (
                  <motion.li
                    key={a.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, ease: EASE, delay: i * 0.04 }}
                    className="border-b border-line"
                  >
                    <Link href={`/medicines/${a.id}`} className="group flex items-center gap-4 py-4">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[16px] font-medium">{a.name}</p>
                        <p className="truncate text-[13px] text-muted">{[a.manufacturer, a.pack_size].filter(Boolean).join(" · ")}</p>
                      </div>
                      {p && <span className={`tabular shrink-0 text-[15px] ${less ? "text-accent" : "text-ink-2"}`}>{p}</span>}
                      <ArrowRight className="size-4 shrink-0 text-muted transition-transform duration-300 group-hover:translate-x-1 group-hover:text-ink" />
                    </Link>
                  </motion.li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="lg:w-96 lg:shrink-0">
          <Reveal>
            <h2 className="font-display text-title">In your prescriptions</h2>
          </Reveal>
          {!history ? (
            <div className="mt-6 skeleton h-24" />
          ) : history.length === 0 ? (
            <p className="mt-6 border-t border-line py-8 text-[15px] text-muted">You have not been prescribed this.</p>
          ) : (
            <ul className="mt-6 border-t border-line">
              {history.map((u) => (
                <li key={u.item_id} className="border-b border-line">
                  <Link href={`/prescriptions/${u.scan_id}`} className="group block py-4">
                    <div className="flex items-baseline justify-between gap-3">
                      <span className="truncate text-[15px] font-medium group-hover:underline group-hover:underline-offset-4">{u.scan_title}</span>
                      <span className="shrink-0 text-[13px] text-muted">{formatDay(u.prescribed_on)}</span>
                    </div>
                    <p className="mt-1 text-[13px] text-muted">
                      {[u.dose, u.frequency, u.duration, u.timing].filter(Boolean).join(" · ") || "No dosage written"}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {medicine.uses && <p className="mt-6 text-[14px] leading-relaxed text-ink-2">{medicine.uses}</p>}
          <p className="mt-6 text-[12px] leading-relaxed text-muted">
            Catalogue information is for identification only. Follow the prescriber&apos;s instructions.
          </p>
        </section>
      </div>
    </div>
  );
}
