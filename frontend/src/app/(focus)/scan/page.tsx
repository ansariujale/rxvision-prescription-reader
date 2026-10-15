"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactCrop, { type PercentCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";

import { api, ApiError } from "@/lib/api";
import { needsReview, plural, PROVIDER_LABEL } from "@/lib/format";
import { clearPendingFile, peekPendingFile } from "@/lib/pending";
import type { Crop } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Camera, Check, Close, Crop as CropIcon, Refresh, Upload } from "@/components/ui/icons";
import { EASE } from "@/components/ui/motion";
import { useToast } from "@/components/ui/toast";
import { ItemList } from "@/components/scan/item-list";
import { PrescriptionMeta } from "@/components/scan/prescription-meta";
import { Processing } from "@/components/scan/processing";
import { ScanImage } from "@/components/scan/scan-image";
import { useScanEditor } from "@/components/scan/use-scan-editor";

const ACCEPT = ["image/jpeg", "image/png", "image/webp"];
const MAX_MB = 10;
const STEPS = ["Capture", "Crop", "Reading", "Review"] as const;
type Step = (typeof STEPS)[number];

function validate(file: File): string | null {
  if (!ACCEPT.includes(file.type)) return "Choose a JPEG, PNG or WebP image.";
  if (file.size > MAX_MB * 1024 * 1024) return `Images must be under ${MAX_MB} MB.`;
  return null;
}

function Stepper({ step }: { step: Step }) {
  const at = STEPS.indexOf(step);
  return (
    <ol className="flex items-center gap-1 sm:gap-2">
      {STEPS.map((s, i) => (
        <li key={s} className="flex items-center gap-1 sm:gap-2">
          <span
            className={`relative rounded-full px-2.5 py-1 text-[12px] transition-colors duration-300 sm:text-[13px] ${
              i === at ? "text-ink" : i < at ? "text-ink-2" : "text-muted/60"
            }`}
          >
            {i === at && (
              <motion.span
                layoutId="step-pill"
                className="absolute inset-0 rounded-full bg-surface-2"
                transition={{ type: "spring", stiffness: 500, damping: 40 }}
              />
            )}
            <span className="relative">{s}</span>
          </span>
          {i < STEPS.length - 1 && <span className={`h-px w-3 sm:w-6 ${i < at ? "bg-ink-2" : "bg-line"}`} />}
        </li>
      ))}
    </ol>
  );
}

const panel = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
  exit: { opacity: 0, y: -10, transition: { duration: 0.2 } },
};

function Capture({ onFile }: { onFile: (f: File) => void }) {
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display text-[clamp(2.5rem,6vw,4.5rem)] leading-[0.95]">
        Photograph the
        <span className="italic text-muted"> prescription.</span>
      </h1>
      <p className="mt-5 max-w-lg text-[17px] text-ink-2">
        Lay it flat in even light and fill the frame. You can crop to the medicines next.
      </p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files[0];
          if (f) onFile(f);
        }}
        className={`mt-10 flex min-h-[320px] flex-col items-center justify-center rounded-tile border border-dashed px-6 text-center transition-colors duration-300 ${
          over ? "border-accent bg-accent-soft" : "border-line-strong bg-surface"
        }`}
      >
        <motion.span
          animate={{ y: over ? -6 : 0 }}
          transition={{ type: "spring", stiffness: 300, damping: 20 }}
          className="grid size-14 place-items-center rounded-full bg-surface-2 text-ink-2"
        >
          <Upload className="size-5" />
        </motion.span>
        <p className="mt-5 text-[17px]">Drop an image here</p>
        <p className="mt-1 text-[14px] text-muted">JPEG, PNG or WebP, up to {MAX_MB} MB</p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button onClick={() => cameraInput.current?.click()} icon={<Camera />}>
            Take a photo
          </Button>
          <Button variant="secondary" onClick={() => fileInput.current?.click()} icon={<Upload />}>
            Choose a file
          </Button>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT.join(",")}
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <input
          ref={cameraInput}
          type="file"
          accept="image/*"
          capture="environment"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
      </div>
    </div>
  );
}

export default function ScanFlow() {
  const router = useRouter();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(() => {
    const handed = peekPendingFile();
    return handed && !validate(handed) ? handed : null;
  });
  const [crop, setCrop] = useState<PercentCrop>();
  const [uploading, setUploading] = useState(false);
  const [scanId, setScanId] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);
  const editor = useScanEditor(scanId);
  const scan = editor.scan;

  useEffect(clearPendingFile, []);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview);
    },
    [preview],
  );

  const pending = !scan || scan.status === "queued" || scan.status === "processing";
  const step: Step = scanId ? (pending ? "Reading" : "Review") : file ? "Crop" : "Capture";
  const hasCrop = !!crop && crop.width > 1 && crop.height > 1;

  function choose(f: File) {
    const problem = validate(f);
    if (problem) return toast(problem, "error");
    setFile(f);
    setCrop(undefined);
  }

  async function upload() {
    if (!file) return;
    const form = new FormData();
    form.append("image", file);
    if (hasCrop && crop) {
      const c: Crop = { x: crop.x / 100, y: crop.y / 100, width: crop.width / 100, height: crop.height / 100 };
      form.append("crop", JSON.stringify(c));
    }
    setUploading(true);
    try {
      const { id } = await api.post<{ id: string }>("/scans", form);
      setScanId(id);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Upload failed", "error");
    } finally {
      setUploading(false);
    }
  }

  async function finish(addToRoutine: boolean) {
    if (!scan) return;
    setFinishing(true);
    if (addToRoutine) {
      await editor.confirmAll();
      if (await editor.updateScan({ in_routine: true })) {
        toast("Added to your routine");
        router.push("/today");
        return;
      }
    } else {
      router.push(`/prescriptions/${scan.id}`);
      return;
    }
    setFinishing(false);
  }

  function restart() {
    setScanId(null);
    setFile(null);
    setCrop(undefined);
  }

  const review = scan?.items.filter(needsReview).length ?? 0;

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 border-b border-line/70 bg-paper/85 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5">
          <Link
            href="/today"
            aria-label="Close"
            className="grid size-9 place-items-center rounded-full text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <Close />
          </Link>
          <Stepper step={step} />
          <span className="size-9" aria-hidden />
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 pt-12 pb-32">
        <AnimatePresence mode="wait">
          {step === "Capture" && (
            <motion.div key="capture" {...panel}>
              <Capture onFile={choose} />
            </motion.div>
          )}

          {step === "Crop" && preview && (
            <motion.div key="crop" {...panel} className="mx-auto max-w-3xl">
              <h1 className="font-display text-headline">Crop to the medicines</h1>
              <p className="mt-3 text-[17px] text-muted">Drag over the part with the medicines, or read the whole page.</p>
              <div className="mt-8 flex justify-center overflow-hidden rounded-tile border border-line bg-surface-2 p-3">
                <ReactCrop crop={crop} onChange={(_, percent) => setCrop(percent)} keepSelection>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={preview} alt="Selected prescription" className="max-h-[60vh] w-auto rounded-lg" />
                </ReactCrop>
              </div>
            </motion.div>
          )}

          {step === "Reading" && (
            <motion.div key="reading" {...panel} className="flex flex-col gap-10 lg:flex-row lg:items-start">
              <div className="lg:w-[42%] lg:shrink-0">
                {scan ? (
                  <ScanImage src={scan.image_url} width={scan.image_width} height={scan.image_height} reading />
                ) : (
                  <div className="skeleton aspect-[3/4] rounded-tile" />
                )}
              </div>
              <div className="flex-1">
                <Processing />
              </div>
            </motion.div>
          )}

          {step === "Review" && scan && (
            <motion.div key="review" {...panel} className="flex flex-col gap-10 lg:flex-row lg:items-start">
              <div className="flex flex-col gap-4 lg:sticky lg:top-24 lg:w-[38%] lg:shrink-0">
                <ScanImage src={scan.image_url} width={scan.image_width} height={scan.image_height} reading={false} />
              </div>
              <div className="min-w-0 flex-1">
                {scan.status === "failed" ? (
                  <div>
                    <h1 className="font-display text-headline">We could not read this one.</h1>
                    <p className="mt-3 text-[15px] text-muted">{scan.error}</p>
                    <div className="mt-8 flex flex-wrap gap-3">
                      <Button onClick={editor.retry} icon={<Refresh />}>Try again</Button>
                      <Button variant="secondary" onClick={restart}>Use another photo</Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <h1 className="font-display text-headline">
                      {scan.items.length ? "Check what was read" : "Nothing recognised"}
                    </h1>
                    <p className="mt-3 text-[15px] text-muted">
                      {plural(scan.items.length, "medicine")}
                      {review > 0 && <span className="text-warn">, {review} worth a second look</span>}
                      {" · "}read with {PROVIDER_LABEL[scan.provider] ?? scan.provider}
                    </p>
                    {scan.provider === "mock" && (
                      <p className="mt-5 rounded-xl border border-dashed border-line-strong px-4 py-3 text-[14px] text-muted">
                        No OCR key is set, so this is sample data, not a reading of your image.
                      </p>
                    )}
                    <div className="mt-8 border-t border-line">
                      <ItemList
                        items={scan.items}
                        onUpdate={editor.updateItem}
                        onDelete={editor.deleteItem}
                        onAdd={editor.addItem}
                      />
                    </div>
                    <div className="mt-10">
                      <PrescriptionMeta scan={scan} onChange={editor.updateScan} showRoutine={false} />
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <AnimatePresence>
        {(step === "Crop" || (step === "Review" && scan?.status === "done")) && (
          <motion.footer
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ duration: 0.4, ease: EASE }}
            className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-paper/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md"
          >
            <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 py-4">
              {step === "Crop" ? (
                <>
                  <Button variant="ghost" onClick={() => setFile(null)} icon={<ArrowLeft />} disabled={uploading}>
                    Back
                  </Button>
                  <div className="ml-auto flex gap-2">
                    {hasCrop && (
                      <Button variant="secondary" onClick={() => setCrop(undefined)} disabled={uploading}>
                        Clear crop
                      </Button>
                    )}
                    <Button onClick={upload} loading={uploading} icon={hasCrop ? <CropIcon /> : undefined}>
                      {hasCrop ? "Read selection" : "Read whole page"}
                    </Button>
                  </div>
                </>
              ) : (
                <>
                  <Button variant="ghost" onClick={restart} disabled={finishing}>
                    Scan another
                  </Button>
                  <div className="ml-auto flex gap-2">
                    <Button variant="secondary" onClick={() => finish(false)} disabled={finishing}>
                      Just save
                    </Button>
                    <Button onClick={() => finish(true)} loading={finishing} icon={<Check />} disabled={!scan?.items.length}>
                      Add to routine
                    </Button>
                  </div>
                </>
              )}
            </div>
          </motion.footer>
        )}
      </AnimatePresence>
    </div>
  );
}
