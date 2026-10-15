// Mirrors backend/app/schemas. Keep in step with the API.

export type ScanStatus = "queued" | "processing" | "done" | "failed";
export type ItemStatus = "suggested" | "confirmed" | "edited" | "manual";

export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface MedicineBrief {
  id: number;
  name: string;
  manufacturer: string | null;
  composition: string | null;
}

export interface Medicine extends MedicineBrief {
  type: string | null;
  pack_size: string | null;
  price: string | null;
  uses: string | null;
}

export interface MedicineHit {
  id: number;
  name: string;
  score: number;
}

export interface Item {
  id: string;
  position: number;
  name: string;
  medicine: MedicineBrief | null;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  duration: string | null;
  timing: string | null;
  notes: string | null;
  confidence: number | null;
  source_line: string | null;
  status: ItemStatus;
}

export const DOSAGE_FIELDS = ["strength", "dose", "frequency", "duration", "timing"] as const;
export type DosageField = (typeof DOSAGE_FIELDS)[number];

export type ItemPatch = Partial<
  Pick<Item, DosageField | "name" | "notes"> & { medicine_id: number | null; status: ItemStatus }
>;

export interface Scan {
  id: string;
  title: string;
  status: ScanStatus;
  provider: string;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  error: string | null;
  raw_text: string | null;
  prescribed_on: string | null;
  doctor: string | null;
  in_routine: boolean;
  image_width: number;
  image_height: number;
  image_url: string;
  items: Item[];
}

export interface ScanSummary {
  id: string;
  title: string;
  status: ScanStatus;
  provider: string;
  prescribed_on: string | null;
  doctor: string | null;
  in_routine: boolean;
  created_at: string;
  item_count: number;
  preview: string[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Stats {
  scans: number;
  medicines_found: number;
  confirmed: number;
  needs_review: number;
  catalogue_size: number;
}

export interface Providers {
  active: string;
  configured: Record<string, boolean>;
}

export interface Crop {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type Slot = "morning" | "afternoon" | "evening" | "night" | "as_needed";

export interface RoutineEntry {
  item_id: string;
  scan_id: string;
  scan_title: string;
  name: string;
  medicine_id: number | null;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  timing: string | null;
  notes: string | null;
  slot: Slot;
  quantity: string | null;
  taken: boolean;
  day_of_course: number;
  total_days: number;
  ends_on: string;
  flags: string[];
}

export interface DayCount {
  day: string;
  total: number;
  taken: number;
}

export interface Routine {
  day: string;
  slots: { slot: Slot; entries: RoutineEntry[] }[];
  as_needed: RoutineEntry[];
  ending_soon: RoutineEntry[];
  taken: number;
  total: number;
  week: DayCount[];
  prescriptions: number;
}

export interface MedicineUse {
  scan_id: string;
  scan_title: string;
  prescribed_on: string;
  item_id: string;
  strength: string | null;
  dose: string | null;
  frequency: string | null;
  duration: string | null;
  timing: string | null;
  in_routine: boolean;
}

export interface MyMedicine {
  key: string;
  name: string;
  medicine: MedicineBrief | null;
  times: number;
  last_prescribed: string;
  active: boolean;
  uses: MedicineUse[];
}

export interface Alternative extends MedicineBrief {
  price: string | null;
  pack_size: string | null;
}
