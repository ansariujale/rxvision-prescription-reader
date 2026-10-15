"use client";

import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import { EASE } from "@/components/ui/motion";

const STEPS = [
  "Reading the handwriting",
  "Finding the medicines",
  "Matching against the catalogue",
  "Working out doses and timings",
];

export function Processing() {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="py-6" role="status">
      <div className="relative h-[1.2em] overflow-hidden font-display text-title">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.p
            key={step}
            initial={{ y: "100%", opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: "-100%", opacity: 0 }}
            transition={{ duration: 0.5, ease: EASE }}
            className="absolute inset-0"
          >
            {STEPS[step]}
            <span className="text-muted">...</span>
          </motion.p>
        </AnimatePresence>
      </div>
      <p className="mt-3 text-[15px] text-muted">Usually a few seconds. You can leave this page.</p>
      <div className="mt-10 space-y-5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="space-y-2.5" style={{ opacity: 1 - i * 0.25 }}>
            <div className="skeleton h-5 w-2/3" />
            <div className="skeleton h-4 w-1/2" />
          </div>
        ))}
      </div>
    </div>
  );
}
