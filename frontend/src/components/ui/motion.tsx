"use client";

import { motion, type HTMLMotionProps } from "motion/react";

export const EASE = [0.22, 1, 0.36, 1] as const;

/** Fade in with a short rise. The one entrance used everywhere. */
export function Reveal({
  delay = 0,
  y = 10,
  ...props
}: HTMLMotionProps<"div"> & { delay?: number; y?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay }}
      {...props}
    />
  );
}

/** Children marked with <StaggerItem> enter one after another. */
export function Stagger({ gap = 0.04, ...props }: HTMLMotionProps<"div"> & { gap?: number }) {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}
      {...props}
    />
  );
}

export const staggerItem = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

export function StaggerItem(props: HTMLMotionProps<"div">) {
  return <motion.div variants={staggerItem} {...props} />;
}
