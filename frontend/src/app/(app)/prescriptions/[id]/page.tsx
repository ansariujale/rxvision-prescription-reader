"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, exportUrl } from "@/lib/api";
import { formatDateTime, needsReview, plural, PROVIDER_LABEL } from "@/lib/format";
import type { Scan } from "@/lib/types";
import { Button, buttonClass } from "@/components/ui/button";
import { ArrowLeft, Check, Download, Refresh, Trash } from "@/components/ui/icons";
import { EASE, Reveal } from "@/components/ui/motion";
import { useToast } from "@/components/ui/toast";
import { ItemList } from "@/components/scan/item-list";
import { PrescriptionMeta } from "@/components/scan/prescription-meta";
import { Processing } from "@/components/scan/processing";
import { ScanImage } from "@/components/scan/scan-image";
import { StatusLabel } from "@/components/scan/status";
import { useScanEditor } from "@/components/scan/use-scan-editor";

function Title({ scan, onRename }: { scan: Scan; onRename: (t: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(scan.title);

  function commit() {
    setEditing(false);
    const t = value.trim();
    if (t && t !== scan.title) onRename(t);
    else setValue(scan.title);
  }

  return editing ? (
    <input
      autoFocus
      value={value}
      maxLength={160}
      onChange={(e) => setValue(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") commit();
        if (e.key === "Escape") {
          setValue(scan.title);
          setEditing(false);
        }
      }}
      className="w-full border-b border-line-strong bg-transparent font-display text-headline focus:outline-none"
    />
  ) : (
    <h1
      onClick={() => {
        setValue(scan.title);
        setEditing(true);
      }}
      title="Click to rename"
      className="cursor-text font-display text-headline decoration-line-strong underline-offset-8 hover:underline"
    >
      {scan.title}
    </h1>
  );
}

export default function PrescriptionPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const toast = useToast();
  const editor = useScanEditor(id);
  const { scan, error } = editor;
  const [showRaw, setShowRaw] = useState(false);

  async function remove() {
    if (!confirm("Delete this prescription and its image? This cannot be undone.")) return;
    if (await editor.remove()) {
      toast("Prescription deleted");
      router.replace("/prescriptions");
    }
  }

  if (error) {
    return (
      <Reveal className="py-20">
        <h1 className="font-display text-headline">
          {error instanceof ApiError && error.status === 404 ? "Prescription not found" : "Could not load this"}
        </h1>
        <p className="mt-3 text-muted">{error.message}</p>
        <Link href="/prescriptions" className={buttonClass("secondary", "md", "mt-8")}>
          All prescriptions
        </Link>
      </Reveal>
    );
  }

  if (!scan) {
    return (
      <div className="flex flex-col gap-10 lg:flex-row">
        <div className="skeleton aspect-[3/4] rounded-tile lg:w-[42%]" />
        <div className="flex-1 space-y-4">
          <div className="skeleton h-12 w-2/3" />
          <div className="skeleton h-4 w-1/3" />
        </div>
      </div>
    );
  }

  const pending = scan.status === "queued" || scan.status === "processing";
  const review = scan.items.filter(needsReview).length;
  const suggested = scan.items.filter((i) => i.status === "suggested").length;

  return (
    <div>
      <Link href="/prescriptions" className="mb-8 inline-flex items-center gap-2 text-[14px] text-muted transition-colors hover:text-ink">
        <ArrowLeft className="size-3.5" /> Prescriptions
      </Link>

      <div className="flex flex-col gap-10 lg:flex-row lg:items-start">
        <div className="flex flex-col gap-4 lg:sticky lg:top-24 lg:w-[42%] lg:shrink-0">
          <Reveal>
            <ScanImage src={scan.image_url} width={scan.image_width} height={scan.image_height} reading={pending} />
          </Reveal>
          {scan.status === "done" && (
            <Reveal delay={0.08}>
              <PrescriptionMeta key={scan.id} scan={scan} onChange={editor.updateScan} />
            </Reveal>
          )}
          {scan.status === "done" && scan.raw_text && (
            <div>
              <button
                onClick={() => setShowRaw((s) => !s)}
                className="text-[13px] text-muted underline decoration-line-strong underline-offset-4 hover:text-ink"
              >
                {showRaw ? "Hide" : "Show"} raw OCR text
              </button>
              <AnimatePresence initial={false}>
                {showRaw && (
                  <motion.pre
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.35, ease: EASE }}
                    className="mt-3 overflow-hidden rounded-xl bg-surface-2 font-mono text-[12px] leading-relaxed whitespace-pre-wrap text-ink-2"
                  >
                    <div className="p-4">{scan.raw_text}</div>
                  </motion.pre>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <Reveal delay={0.05}>
            <Title scan={scan} onRename={(title) => editor.updateScan({ title })} />
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-muted">
              <StatusLabel status={scan.status} />
              {scan.doctor && <span>{scan.doctor}</span>}
              <span>{formatDateTime(scan.created_at)}</span>
              <span>{PROVIDER_LABEL[scan.provider] ?? scan.provider}</span>
              {scan.in_routine && (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-[12px] text-accent">
                  <Check className="size-3" /> In routine
                </span>
              )}
            </div>
          </Reveal>

          {scan.provider === "mock" && scan.status === "done" && (
            <Reveal delay={0.1} className="mt-6 rounded-xl border border-dashed border-line-strong px-4 py-3 text-[14px] text-muted">
              Read with the sample provider, so these items are example data, not a reading of your image.
            </Reveal>
          )}

          <AnimatePresence mode="wait">
            {pending ? (
              <motion.div key="pending" exit={{ opacity: 0, transition: { duration: 0.2 } }} className="mt-8">
                <Processing />
              </motion.div>
            ) : scan.status === "failed" ? (
              <Reveal key="failed" className="mt-10">
                <p className="font-display text-title">We could not read this one.</p>
                <p className="mt-3 text-[15px] text-muted">{scan.error}</p>
                <div className="mt-8 flex gap-3">
                  <Button onClick={editor.retry} icon={<Refresh />}>Try again</Button>
                  <Button variant="ghost" onClick={remove} icon={<Trash />}>Delete</Button>
                </div>
              </Reveal>
            ) : (
              <motion.div key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
                <div className="mt-10 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-5">
                  <div>
                    <p className="tabular font-display text-[56px] leading-none">{scan.items.length}</p>
                    <p className="mt-1 text-[14px] text-muted">
                      {plural(scan.items.length, "medicine")}
                      {review > 0 && <span className="text-warn">, {review} to check</span>}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {suggested > 0 && (
                      <Button size="sm" variant="secondary" onClick={editor.confirmAll} icon={<Check className="size-3.5" />}>
                        Confirm all
                      </Button>
                    )}
                    <a href={exportUrl(scan.id, "csv")} className={buttonClass("secondary", "sm")} download>
                      <Download className="size-3.5" /> CSV
                    </a>
                    <a href={exportUrl(scan.id, "pdf")} className={buttonClass("secondary", "sm")} download>
                      <Download className="size-3.5" /> PDF
                    </a>
                  </div>
                </div>

                <ItemList items={scan.items} onUpdate={editor.updateItem} onDelete={editor.deleteItem} onAdd={editor.addItem} />

                <div className="mt-16 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-6">
                  <p className="max-w-md text-[13px] leading-relaxed text-muted">
                    Machine read. Check every item against the original before relying on it.
                  </p>
                  <Button variant="danger" size="sm" onClick={remove} icon={<Trash className="size-3.5" />}>
                    Delete prescription
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
