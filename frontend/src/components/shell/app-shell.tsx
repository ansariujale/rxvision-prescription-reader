"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";

import { ButtonLink } from "@/components/ui/button";
import { Logout, Plus, Search } from "@/components/ui/icons";
import { EASE } from "@/components/ui/motion";
import { Spinner } from "@/components/ui/spinner";

import { CommandPaletteProvider, useOpenPalette } from "./command-palette";
import { Logo } from "./logo";
import { ThemeToggle } from "./theme-toggle";
import { useAuthGuard, useSignOut } from "./use-auth-guard";

const NAV = [
  { href: "/today", label: "Today" },
  { href: "/prescriptions", label: "Prescriptions" },
  { href: "/medicines", label: "Medicines" },
];

function AccountMenu({ name, email }: { name: string; email: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const signOut = useSignOut();

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Account"
        aria-expanded={open}
        className="grid size-9 place-items-center rounded-full bg-surface-2 font-display text-[18px] text-ink transition-colors hover:bg-line"
      >
        {name.charAt(0).toUpperCase()}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98, transition: { duration: 0.12 } }}
            transition={{ duration: 0.2, ease: EASE }}
            style={{ transformOrigin: "top right" }}
            className="absolute right-0 mt-2 w-64 overflow-hidden rounded-2xl border border-line bg-surface p-1.5 shadow-xl shadow-black/5"
          >
            <div className="px-3 py-2.5">
              <p className="truncate text-[15px] font-medium">{name}</p>
              <p className="truncate text-[13px] text-muted">{email}</p>
            </div>
            <div className="my-1 h-px bg-line" />
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="block rounded-xl px-3 py-2 text-[14px] text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              Settings
            </Link>
            <div className="flex items-center justify-between rounded-xl py-0.5 pr-1 pl-3 text-[14px] text-ink-2">
              Theme <ThemeToggle />
            </div>
            <button
              onClick={signOut}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[14px] text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              <Logout className="size-3.5" /> Sign out
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SearchButton() {
  const open = useOpenPalette();
  return (
    <button
      onClick={open}
      aria-label="Search"
      className="flex h-9 items-center gap-2 rounded-full px-2.5 text-[13px] text-muted transition-colors hover:text-ink md:border md:border-line md:px-3 md:hover:border-line-strong"
    >
      <Search className="size-4 md:size-3.5" />
      <span className="hidden md:inline">Search</span>
      <kbd className="ml-3 hidden font-mono text-[11px] opacity-70 md:inline">Ctrl K</kbd>
    </button>
  );
}

function MobileTabs({ pathname }: { pathname: string }) {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-paper/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-md sm:hidden">
      <div className="flex items-center justify-around gap-1 px-3 py-2">
        {NAV.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`relative flex-1 rounded-full py-2 text-center text-[13px] transition-colors ${active ? "text-ink" : "text-muted"}`}
            >
              {active && (
                <motion.span layoutId="tab-pill" className="absolute inset-0 rounded-full bg-surface-2" />
              )}
              <span className="relative">{item.label}</span>
            </Link>
          );
        })}
        <Link
          href="/scan"
          aria-label="New scan"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-ink text-paper shadow-lg shadow-black/10"
        >
          <Plus />
        </Link>
      </div>
    </nav>
  );
}

function Shell({ children }: { children: ReactNode }) {
  const { user, ready, error } = useAuthGuard();
  const pathname = usePathname();

  if (!ready || !user) {
    return (
      <div className="grid min-h-dvh place-items-center text-muted">
        {error ? <p className="max-w-sm text-center text-[15px]">{error.message}</p> : <Spinner className="size-5" />}
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5">
          <Logo href="/today" />
          <nav className="hidden items-center gap-1 sm:flex">
            {NAV.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative rounded-full px-3 py-1.5 text-[14px] transition-colors ${
                    active ? "text-ink" : "text-muted hover:text-ink"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 rounded-full bg-surface-2"
                      transition={{ type: "spring", stiffness: 500, damping: 40 }}
                    />
                  )}
                  <span className="relative">{item.label}</span>
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <SearchButton />
            <ButtonLink href="/scan" size="sm" icon={<Plus className="size-3.5" />} className="hidden sm:inline-flex">
              New scan
            </ButtonLink>
            <AccountMenu name={user.name} email={user.email} />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 pt-10 pb-32 sm:pb-24">{children}</main>
      <MobileTabs pathname={pathname} />
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <CommandPaletteProvider>
      <Shell>{children}</Shell>
    </CommandPaletteProvider>
  );
}
