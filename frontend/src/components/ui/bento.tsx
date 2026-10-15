"use client";

import { motion, type HTMLMotionProps } from "motion/react";

import { staggerItem } from "./motion";

/**
 * Bento layout for sets of unlike pieces (dashboard, landing explainer).
 * Lists of like things should stay plain lists.
 */
export function Bento({ className = "", ...props }: HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: 0.05 } } }}
      className={`grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:auto-rows-[minmax(170px,auto)] ${className}`}
      {...props}
    />
  );
}

export function Tile({
  className = "",
  interactive = false,
  tone = "surface",
  ...props
}: HTMLMotionProps<"div"> & { interactive?: boolean; tone?: "surface" | "ink" | "accent" | "plain" }) {
  const tones = {
    surface: "bg-surface border border-line",
    ink: "bg-ink text-paper",
    accent: "bg-accent-soft border border-transparent",
    plain: "border border-dashed border-line-strong",
  };
  return (
    <motion.div
      variants={staggerItem}
      whileHover={interactive ? { y: -2 } : undefined}
      transition={{ type: "spring", stiffness: 400, damping: 32 }}
      className={`relative overflow-hidden rounded-tile p-6 ${tones[tone]} ${className}`}
      {...props}
    />
  );
}

export function TileLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={`text-[13px] font-medium tracking-wide text-muted uppercase ${className}`}>{children}</p>
  );
}
