"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { Item, ItemPatch } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Plus } from "@/components/ui/icons";
import { EASE } from "@/components/ui/motion";

import { ItemEditor } from "./item-editor";
import { ItemRow } from "./item-row";

export function ItemList({
  items,
  onUpdate,
  onDelete,
  onAdd,
}: {
  items: Item[];
  onUpdate: (item: Item, patch: ItemPatch) => Promise<void>;
  onDelete: (item: Item) => void;
  onAdd: (patch: ItemPatch) => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);

  return (
    <div>
      {items.length === 0 && !adding && (
        <div className="py-12">
          <p className="font-display text-title text-muted">No medicines found.</p>
          <p className="mt-2 text-[15px] text-muted">
            Try a sharper photo, crop closer to the medicines, or add them yourself.
          </p>
        </div>
      )}

      <ul>
        <AnimatePresence initial={false}>
          {items.map((item, i) => (
            <ItemRow
              key={item.id}
              item={item}
              index={i}
              onUpdate={(patch) => onUpdate(item, patch)}
              onDelete={() => onDelete(item)}
            />
          ))}
        </AnimatePresence>
      </ul>

      <AnimatePresence mode="wait" initial={false}>
        {adding ? (
          <motion.div
            key="form"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.35, ease: EASE }}
            className="overflow-hidden"
          >
            <div className="mt-4 rounded-tile border border-line bg-surface p-5">
              <ItemEditor
                submitLabel="Add"
                onCancel={() => setAdding(false)}
                onSubmit={async (patch) => {
                  await onAdd(patch);
                  setAdding(false);
                }}
              />
            </div>
          </motion.div>
        ) : (
          <motion.div key="button" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4">
            <Button variant="ghost" onClick={() => setAdding(true)} icon={<Plus />}>
              Add a medicine
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
