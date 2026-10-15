import type { Item } from "./types";

export type Band = "high" | "review" | "unmatched" | "manual";

export function band(item: Pick<Item, "confidence" | "medicine" | "status">): Band {
  if (item.status === "manual") return "manual";
  if (!item.medicine) return "unmatched";
  if (item.confidence === null || item.confidence >= 0.85) return "high";
  return "review";
}

export function needsReview(item: Item): boolean {
  if (item.status !== "suggested") return false;
  const b = band(item);
  return b === "review" || b === "unmatched";
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${dateFmt.format(d)}, ${timeFmt.format(d)}`;
}

export function relative(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} d ago`;
  return formatDate(iso);
}

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 5) return "Up late";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export const PROVIDER_LABEL: Record<string, string> = {
  gemini: "Gemini",
  claude: "Claude",
  textract: "AWS Textract",
  mock: "Sample data",
};

export function plural(n: number, word: string, many = `${word}s`): string {
  return `${n} ${n === 1 ? word : many}`;
}

/** Local calendar date as YYYY-MM-DD (not UTC, which can be a day off). */
export function isoDay(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseDay(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(iso: string, n: number): string {
  const d = parseDay(iso);
  d.setDate(d.getDate() + n);
  return isoDay(d);
}

export function formatDay(iso: string): string {
  return dateFmt.format(parseDay(iso));
}

export const SLOT_LABEL: Record<string, string> = {
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
  night: "Night",
  as_needed: "When needed",
};

export const SLOT_HINT: Record<string, string> = {
  morning: "With or after breakfast",
  afternoon: "Around lunch",
  evening: "Early evening",
  night: "Before bed",
  as_needed: "Only if you need it",
};
