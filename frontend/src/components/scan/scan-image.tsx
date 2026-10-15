"use client";

import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

export function ScanImage({
  src,
  width,
  height,
  reading,
}: {
  src: string;
  width: number;
  height: number;
  reading: boolean;
}) {
  const [loaded, setLoaded] = useState(false);

  return (
    <div
      className="relative overflow-hidden rounded-tile border border-line bg-surface-2"
      style={{ aspectRatio: `${width} / ${height}` }}
    >
      {!loaded && <div className="skeleton absolute inset-0 rounded-none" />}
      <motion.img
        src={src}
        alt="Prescription"
        onLoad={() => setLoaded(true)}
        initial={{ opacity: 0, scale: 1.02 }}
        animate={{ opacity: loaded ? 1 : 0, scale: loaded ? 1 : 1.02 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="absolute inset-0 size-full object-contain"
      />
      <AnimatePresence>
        {reading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0, transition: { duration: 0.5 } }}
            className="pointer-events-none absolute inset-0 bg-paper/20"
          >
            <div className="scan-line absolute inset-x-0 top-0 h-[10%] bg-gradient-to-b from-transparent via-accent/25 to-transparent">
              <div className="absolute inset-x-0 bottom-1/2 h-px bg-accent/70" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
