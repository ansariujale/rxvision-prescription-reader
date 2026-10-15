import Link from "next/link";

export function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="group inline-flex items-baseline gap-0.5 text-ink">
      <span className="font-display text-[26px] leading-none">Rx</span>
      <span className="font-display text-[26px] leading-none italic text-muted transition-colors group-hover:text-ink">
        vision
      </span>
    </Link>
  );
}
