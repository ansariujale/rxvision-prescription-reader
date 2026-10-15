"use client";

import { AnimatePresence, motion } from "motion/react";
import { useSyncExternalStore } from "react";

import { Moon, Sun } from "@/components/ui/icons";

type Theme = "light" | "dark";

function current(): Theme {
  const set = document.documentElement.dataset.theme;
  if (set === "light" || set === "dark") return set;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// The theme lives on <html data-theme> and in the OS setting; watch both.
function subscribe(onChange: () => void) {
  const media = matchMedia("(prefers-color-scheme: dark)");
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, current, () => null);

  function toggle() {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("rx-theme", next);
    } catch {}
  }

  return (
    <button
      onClick={toggle}
      aria-label="Switch colour theme"
      className="grid size-9 place-items-center rounded-full text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={theme ?? "none"}
          initial={{ opacity: 0, rotate: -30 }}
          animate={{ opacity: 1, rotate: 0 }}
          exit={{ opacity: 0, rotate: 30 }}
          transition={{ duration: 0.2 }}
        >
          {theme === "dark" ? <Sun /> : <Moon />}
        </motion.span>
      </AnimatePresence>
    </button>
  );
}

export type ThemeChoice = "light" | "dark" | "system";

function currentChoice(): ThemeChoice {
  const set = document.documentElement.dataset.theme;
  return set === "light" || set === "dark" ? set : "system";
}

export function useThemeChoice(): [ThemeChoice | null, (c: ThemeChoice) => void] {
  const choice = useSyncExternalStore<ThemeChoice | null>(subscribe, currentChoice, () => null);
  const set = (c: ThemeChoice) => {
    try {
      if (c === "system") {
        delete document.documentElement.dataset.theme;
        localStorage.removeItem("rx-theme");
      } else {
        document.documentElement.dataset.theme = c;
        localStorage.setItem("rx-theme", c);
      }
    } catch {}
  };
  return [choice, set];
}
