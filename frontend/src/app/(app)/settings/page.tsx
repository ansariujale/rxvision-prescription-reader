"use client";

import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import { PROVIDER_LABEL } from "@/lib/format";
import { useMe, useProviders } from "@/lib/hooks";
import type { User } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Download } from "@/components/ui/icons";
import { Reveal } from "@/components/ui/motion";
import { useToast } from "@/components/ui/toast";
import { useThemeChoice, type ThemeChoice } from "@/components/shell/theme-toggle";

function Section({ title, lead, children, delay = 0 }: { title: string; lead?: string; children: ReactNode; delay?: number }) {
  return (
    <Reveal delay={delay} className="flex flex-col gap-6 border-t border-line py-10 md:flex-row md:gap-16">
      <div className="md:w-64 md:shrink-0">
        <h2 className="font-display text-[28px] leading-none">{title}</h2>
        {lead && <p className="mt-3 text-[14px] leading-relaxed text-muted">{lead}</p>}
      </div>
      <div className="min-w-0 flex-1">{children}</div>
    </Reveal>
  );
}

function message(err: unknown) {
  return err instanceof ApiError ? err.message : "That did not work";
}

function Profile({ user }: { user: User }) {
  const { mutate } = useSWRConfig();
  const toast = useToast();
  const [name, setName] = useState(user.name);
  const [saving, setSaving] = useState(false);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await mutate("/auth/me", await api.patch<User>("/auth/me", { name }), { revalidate: false });
      toast("Saved");
    } catch (err) {
      toast(message(err), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-md space-y-4">
      <Field label="Name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
      <Field label="Email" value={user.email} disabled hint="Your sign-in email cannot be changed here." />
      <Button type="submit" loading={saving} disabled={!name.trim() || name.trim() === user.name}>
        Save
      </Button>
    </form>
  );
}

function Password() {
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    setSaving(true);
    setError(null);
    try {
      await api.post("/auth/password", data);
      form.reset();
      toast("Password changed");
    } catch (err) {
      setError(message(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={save} className="max-w-md space-y-4">
      <Field label="Current password" name="current_password" type="password" autoComplete="current-password" required />
      <Field
        label="New password"
        name="new_password"
        type="password"
        autoComplete="new-password"
        minLength={8}
        hint="At least 8 characters."
        required
      />
      {error && <p role="alert" className="rounded-xl bg-danger-soft px-3.5 py-2.5 text-[14px] text-danger">{error}</p>}
      <Button type="submit" loading={saving}>Change password</Button>
    </form>
  );
}

const THEMES: { key: ThemeChoice; label: string }[] = [
  { key: "system", label: "System" },
  { key: "light", label: "Light" },
  { key: "dark", label: "Dark" },
];

function Appearance() {
  const [choice, setChoice] = useThemeChoice();
  return (
    <div className="inline-flex rounded-full border border-line bg-surface p-1">
      {THEMES.map((t) => (
        <button
          key={t.key}
          onClick={() => setChoice(t.key)}
          aria-pressed={choice === t.key}
          className={`relative rounded-full px-4 py-1.5 text-[14px] transition-colors ${choice === t.key ? "text-paper" : "text-muted hover:text-ink"}`}
        >
          {choice === t.key && (
            <motion.span layoutId="theme-choice" className="absolute inset-0 rounded-full bg-ink" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
          )}
          <span className="relative">{t.label}</span>
        </button>
      ))}
    </div>
  );
}

function DeleteAccount() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.del("/auth/me", { password });
      await mutate(() => true, undefined, { revalidate: false });
      toast("Your account and data were deleted");
      router.replace("/");
    } catch (err) {
      setError(message(err));
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <Button variant="danger" onClick={() => setOpen(true)} className="border border-danger/30">
        Delete my account
      </Button>
    );
  }

  return (
    <motion.form
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      onSubmit={remove}
      className="max-w-md space-y-4 rounded-tile border border-danger/30 bg-danger-soft/40 p-5"
    >
      <p className="text-[15px]">
        This permanently deletes your account, every prescription, image and dose you logged. It cannot be undone.
      </p>
      <Field
        label="Type your password to confirm"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      {error && <p role="alert" className="text-[14px] text-danger">{error}</p>}
      <div className="flex gap-2">
        <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
        <Button type="submit" loading={busy} disabled={!password} className="bg-danger! text-white! hover:opacity-90">
          Delete everything
        </Button>
      </div>
    </motion.form>
  );
}

export default function Settings() {
  const { data: user } = useMe();
  const { data: providers } = useProviders();
  if (!user) return null;

  return (
    <div className="mx-auto max-w-4xl">
      <Reveal>
        <h1 className="font-display text-headline">Settings</h1>
        <p className="mt-3 text-[17px] text-muted">Your account, your data.</p>
      </Reveal>
      <div className="mt-10">
        <Section title="Profile" delay={0.03}>
          <Profile user={user} />
        </Section>
        <Section title="Password" delay={0.06}>
          <Password />
        </Section>
        <Section title="Appearance" lead="Follow your device, or pick one." delay={0.09}>
          <Appearance />
        </Section>
        <Section title="Reading" lead="The OCR service the server is configured to use." delay={0.12}>
          <p className="font-display text-[32px] leading-none">
            {providers ? PROVIDER_LABEL[providers.active] ?? providers.active : "..."}
          </p>
          <p className="mt-3 max-w-md text-[14px] leading-relaxed text-muted">
            {providers?.active === "mock"
              ? "No OCR key is set on the server, so scans return sample data. Add GEMINI_API_KEY to the server environment to read real prescriptions."
              : "Set by the server administrator through environment variables."}
          </p>
        </Section>
        <Section title="Your data" lead="Every prescription and item you have, as JSON." delay={0.15}>
          <a href="/api/v1/me/export" download className="inline-flex h-10 items-center gap-2 rounded-full border border-line-strong bg-surface px-4 text-[15px] font-medium transition-colors hover:border-ink/40">
            <Download className="size-4" /> Download my data
          </a>
        </Section>
        <Section title="Delete account" lead="Removes everything, including stored images." delay={0.18}>
          <DeleteAccount />
        </Section>
      </div>
    </div>
  );
}
