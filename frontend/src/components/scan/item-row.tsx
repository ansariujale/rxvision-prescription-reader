"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";

import { band, type Band } from "@/lib/format";
import { DOSAGE_FIELDS, type Item, type ItemPatch } from "@/lib/types";
import { Check, Pencil, Trash } from "@/components/ui/icons";
import { EASE } from "@/components/ui/motion";

import { ItemEditor } from "./item-editor";

const FIELD_LABEL: Record<(typeof DOSAGE_FIELDS)[number], string> = {
  strength: "Strength",
  dose: "Dose",
  frequency: "Frequency",
  duration: "Duration",
  timing: "Timing",
};

const BAND_TEXT: Record<Band, string> = {
  high: "Matched",
  review: "Check this",
  unmatched: "Not in catalogue",
  manual: "Added by you",
};

const BAND_STYLE: Record<Band, string> = {
  high: "text-muted",
  review: "text-warn",
  unmatched: "text-warn",
  manual: "text-muted",
};

function Confidence({ item }: { item: Item }) {
  const b = band(item);
  const pct = item.confidence !== null ? Math.round(item.confidence * 100) : null;
  return (
    <span className={`inline-flex items-center gap-2 text-[12px] ${BAND_STYLE[b]}`}>
      {pct !== null && (
        <span className="relative h-1 w-10 overflow-hidden rounded-full bg-line" aria-hidden>
          <motion.span
            className={`absolute inset-y-0 left-0 rounded-full ${b === "review" ? "bg-warn" : "bg-ink-2"}`}
            initial={{ width: 0 }}
            animate={{ width: `${pct}%` }}
            transition={{ duration: 0.8, ease: EASE, delay: 0.2 }}
          />
        </span>
      )}
      {BAND_TEXT[b]}
      {pct !== null && <span className="tabular">{pct}%</span>}
    </span>
  );
}

export function ItemRow({
  item,
  index,
  onUpdate,
  onDelete,
}: {
  item: Item;
  index: number;
  onUpdate: (patch: ItemPatch) => Promise<void>;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const b = band(item);
  const flagged = item.status === "suggested" && (b === "review" || b === "unmatched");
  const confirmed = item.status === "confirmed";
  const fields = DOSAGE_FIELDS.filter((f) => item[f]);

  return (
    <motion.li
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16, transition: { duration: 0.25 } }}
      transition={{ duration: 0.45, ease: EASE, delay: Math.min(index, 8) * 0.04 }}
      className={`group relative border-b border-line py-6 pl-5 last:border-b-0 ${
        flagged ? "before:absolute before:inset-y-6 before:left-0 before:w-[3px] before:rounded-full before:bg-warn" : ""
      }`}
    >
      <AnimatePresence mode="wait" initial={false}>
        {editing ? (
          <motion.div
            key="edit"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <ItemEditor
              item={item}
              onCancel={() => setEditing(false)}
              onSubmit={async (patch) => {
                await onUpdate(patch);
                setEditing(false);
              }}
            />
          </motion.div>
        ) : (
          <motion.div
            key="view"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="flex gap-4"
          >
            <span className="tabular w-6 shrink-0 pt-1 font-mono text-[13px] text-muted">
              {String(index + 1).padStart(2, "0")}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                {item.medicine ? (
                  <Link
                    href={`/medicines/${item.medicine.id}`}
                    className="text-left text-[19px] font-medium leading-snug underline decoration-transparent underline-offset-4 transition-colors hover:decoration-line-strong"
                  >
                    {item.name}
                  </Link>
                ) : (
                  <p className="text-[19px] font-medium leading-snug">{item.name}</p>
                )}
                {confirmed && (
                  <motion.span
                    initial={{ scale: 0.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[12px] text-accent"
                  >
                    <Check className="size-3" /> Confirmed
                  </motion.span>
                )}
                {item.status === "edited" && <span className="text-[12px] text-muted">Edited</span>}
              </div>
              {item.medicine?.composition && (
                <p className="mt-1 truncate text-[14px] text-muted">{item.medicine.composition}</p>
              )}

              {fields.length > 0 && (
                <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
                  {fields.map((f) => (
                    <div key={f}>
                      <dt className="text-[12px] text-muted">{FIELD_LABEL[f]}</dt>
                      <dd className="text-[15px]">{item[f]}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {item.notes && <p className="mt-3 text-[14px] text-ink-2">{item.notes}</p>}

              <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
                <Confidence item={item} />
                {item.source_line && (
                  <p className="min-w-0 truncate font-mono text-[12px] text-muted" title={item.source_line}>
                    &ldquo;{item.source_line}&rdquo;
                  </p>
                )}
              </div>
            </div>

            <div className="flex shrink-0 items-start gap-0.5 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
              {!confirmed && (
                <IconButton label="Confirm" onClick={() => onUpdate({ status: "confirmed" })}>
                  <Check />
                </IconButton>
              )}
              <IconButton label="Edit" onClick={() => setEditing(true)}>
                <Pencil />
              </IconButton>
              <IconButton label="Remove" onClick={onDelete} danger>
                <Trash />
              </IconButton>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

function IconButton({
  label,
  onClick,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      aria-label={label}
      title={label}
      className={`grid size-9 place-items-center rounded-full transition-colors ${
        danger ? "text-muted hover:bg-danger-soft hover:text-danger" : "text-muted hover:bg-surface-2 hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
