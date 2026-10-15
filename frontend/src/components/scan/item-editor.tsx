"use client";

import { useState, type FormEvent } from "react";

import type { Item, ItemPatch } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { inputClass } from "@/components/ui/field";

import { MedicineSearch } from "./medicine-search";

const FIELDS = [
  { key: "strength", label: "Strength", placeholder: "650 mg" },
  { key: "dose", label: "Dose", placeholder: "1 tablet" },
  { key: "frequency", label: "Frequency", placeholder: "1-0-1" },
  { key: "duration", label: "Duration", placeholder: "5 days" },
  { key: "timing", label: "Timing", placeholder: "After food" },
] as const;

const FREQUENCY_SUGGESTIONS = ["1-0-1", "1-0-0", "0-0-1", "1-1-1", "Once daily", "Twice daily", "As needed"];
const TIMING_SUGGESTIONS = ["Before food", "After food", "Empty stomach", "With food", "At bedtime"];

type Draft = Record<(typeof FIELDS)[number]["key"] | "name" | "notes", string>;

function toDraft(item?: Partial<Item>): Draft {
  return {
    name: item?.name ?? "",
    strength: item?.strength ?? "",
    dose: item?.dose ?? "",
    frequency: item?.frequency ?? "",
    duration: item?.duration ?? "",
    timing: item?.timing ?? "",
    notes: item?.notes ?? "",
  };
}

export function ItemEditor({
  item,
  submitLabel = "Save",
  onSubmit,
  onCancel,
}: {
  item?: Item;
  submitLabel?: string;
  onSubmit: (patch: ItemPatch) => Promise<void>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(() => toDraft(item));
  const [medicineId, setMedicineId] = useState<number | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  const set = (key: keyof Draft) => (value: string) => setDraft((d) => ({ ...d, [key]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!draft.name.trim()) return;
    const original = toDraft(item);
    const patch: ItemPatch = {};
    for (const key of Object.keys(draft) as (keyof Draft)[]) {
      if (!item || draft[key] !== original[key]) {
        (patch as Record<string, string | null>)[key] = draft[key].trim() || null;
      }
    }
    if (medicineId !== undefined) patch.medicine_id = medicineId;
    setSaving(true);
    try {
      await onSubmit(patch);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" onKeyDown={(e) => e.key === "Escape" && onCancel()}>
      <label className="block">
        <span className="mb-1.5 block text-[13px] font-medium text-ink-2">Medicine</span>
        <MedicineSearch
          autoFocus
          value={draft.name}
          onChange={(text) => {
            set("name")(text);
            // Typing a new name unlinks the catalogue entry until one is picked.
            if (item?.medicine && text !== item.medicine.name) setMedicineId(null);
          }}
          onPick={(hit) => {
            set("name")(hit.name);
            setMedicineId(hit.id);
          }}
        />
      </label>
      <div className="flex flex-wrap gap-3">
        {FIELDS.map((f) => (
          <label key={f.key} className="block min-w-[130px] flex-1">
            <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{f.label}</span>
            <input
              className={inputClass}
              value={draft[f.key]}
              placeholder={f.placeholder}
              maxLength={60}
              list={f.key === "frequency" ? "rx-frequency" : f.key === "timing" ? "rx-timing" : undefined}
              onChange={(e) => set(f.key)(e.target.value)}
            />
          </label>
        ))}
      </div>
      <label className="block">
        <span className="mb-1.5 block text-[13px] font-medium text-ink-2">Notes</span>
        <input
          className={inputClass}
          value={draft.notes}
          maxLength={1000}
          placeholder="Anything else written for this medicine"
          onChange={(e) => set("notes")(e.target.value)}
        />
      </label>
      <datalist id="rx-frequency">
        {FREQUENCY_SUGGESTIONS.map((v) => <option key={v} value={v} />)}
      </datalist>
      <datalist id="rx-timing">
        {TIMING_SUGGESTIONS.map((v) => <option key={v} value={v} />)}
      </datalist>
      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" loading={saving} disabled={!draft.name.trim()}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
