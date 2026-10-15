"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useSWRConfig } from "swr";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { ArrowRight } from "@/components/ui/icons";
import { Reveal } from "@/components/ui/motion";

type Mode = "login" | "register";

const COPY = {
  login: {
    title: "Welcome back",
    lead: "Sign in to see your scans.",
    action: "Sign in",
    switchText: "New here?",
    switchLink: "Create an account",
    switchHref: "/register",
  },
  register: {
    title: "Create an account",
    lead: "Your scans stay private to you.",
    action: "Create account",
    switchText: "Already have an account?",
    switchLink: "Sign in",
    switchHref: "/login",
  },
} as const;

function safeNext(next: string | null): string {
  // Only same-site paths, never a full URL from the query string.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/today";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const copy = COPY[mode];
  const router = useRouter();
  const params = useSearchParams();
  const { mutate } = useSWRConfig();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const body = Object.fromEntries(form.entries());
    setLoading(true);
    setError(null);
    try {
      const user = await api.post<User>(`/auth/${mode}`, body);
      await mutate("/auth/me", user, { revalidate: false });
      router.replace(safeNext(params.get("next")));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <Reveal className="w-full max-w-sm">
      <h1 className="font-display text-headline">{copy.title}</h1>
      <p className="mt-3 text-[17px] text-muted">{copy.lead}</p>

      <form onSubmit={onSubmit} className="mt-10 space-y-4">
        {mode === "register" && (
          <Field label="Name" name="name" autoComplete="name" required maxLength={120} />
        )}
        <Field label="Email" name="email" type="email" autoComplete="email" required />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          minLength={mode === "register" ? 8 : undefined}
          hint={mode === "register" ? "At least 8 characters." : undefined}
          required
        />
        {error && (
          <p role="alert" className="rounded-xl bg-danger-soft px-3.5 py-2.5 text-[14px] text-danger">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" loading={loading} className="w-full">
          {copy.action}
          {!loading && <ArrowRight />}
        </Button>
      </form>

      <p className="mt-8 text-[14px] text-muted">
        {copy.switchText}{" "}
        <Link href={copy.switchHref} className="text-ink underline decoration-line-strong underline-offset-4 hover:decoration-ink">
          {copy.switchLink}
        </Link>
      </p>
    </Reveal>
  );
}
