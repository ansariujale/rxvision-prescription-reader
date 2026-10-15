import { Logo } from "@/components/shell/logo";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Bento, Tile, TileLabel } from "@/components/ui/bento";
import { ButtonLink } from "@/components/ui/button";
import { ArrowRight, Check } from "@/components/ui/icons";
import { Reveal } from "@/components/ui/motion";

const SAMPLE_FIELDS = [
  ["Medicine", "Augmentin 625 Duo"],
  ["Frequency", "1-0-1"],
  ["Duration", "5 days"],
  ["Timing", "After food"],
] as const;

const ROUTINE = [
  ["Morning, after food", "Augmentin 625 Duo", true],
  ["Morning, before breakfast", "Pan 40", true],
  ["Afternoon", "Ascoril LS, 10 ml", false],
  ["Night, after food", "Augmentin 625 Duo", false],
] as const;

export default function Landing() {
  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-5">
        <Logo />
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <ButtonLink href="/login" variant="ghost" size="sm">
            Sign in
          </ButtonLink>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5">
        <section className="pt-20 pb-24 sm:pt-28">
          <Reveal>
            <p className="text-[13px] font-medium tracking-wide text-muted uppercase">Prescription reader</p>
          </Reveal>
          <Reveal delay={0.06}>
            <h1 className="mt-6 max-w-4xl font-display text-[clamp(3rem,9vw,7rem)] leading-[0.92] tracking-[-0.025em]">
              Handwritten prescriptions,
              <span className="italic text-muted"> read clearly.</span>
            </h1>
          </Reveal>
          <Reveal delay={0.12}>
            <p className="mt-8 max-w-xl text-[19px] leading-relaxed text-ink-2">
              Photograph a prescription. RxVision reads every medicine with its dose and duration,
              lets you check it, then turns it into a simple daily routine until the course is done.
            </p>
          </Reveal>
          <Reveal delay={0.18} className="mt-10 flex flex-wrap items-center gap-3">
            <ButtonLink href="/register" size="lg">
              Start reading <ArrowRight />
            </ButtonLink>
            <ButtonLink href="/login" variant="secondary" size="lg">
              I have an account
            </ButtonLink>
          </Reveal>
        </section>

        <section className="pb-24">
          <Reveal>
            <h2 className="mb-8 font-display text-title">How it works</h2>
          </Reveal>
          <Bento>
            <Tile className="lg:col-span-2 lg:row-span-2 flex flex-col justify-between">
              <TileLabel>From a line of scrawl</TileLabel>
              <div className="mt-8">
                <p className="font-mono text-[15px] text-muted">&ldquo;Tab Augmentin 625 1-0-1 x5d pc&rdquo;</p>
                <div className="my-6 h-px bg-line" />
                <dl className="space-y-3">
                  {SAMPLE_FIELDS.map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-6">
                      <dt className="text-[14px] text-muted">{k}</dt>
                      <dd className="font-display text-[26px] leading-none">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </Tile>
            <Tile>
              <TileLabel>01 Capture</TileLabel>
              <p className="mt-6 text-[17px] leading-snug">
                Upload a photo or use your phone camera. Crop to the medicines if the page is busy.
              </p>
            </Tile>
            <Tile>
              <TileLabel>02 Read</TileLabel>
              <p className="mt-6 text-[17px] leading-snug">
                A vision model reads the handwriting and splits out strength, dose and timing.
              </p>
            </Tile>
            <Tile tone="ink" className="lg:col-span-2">
              <p className="text-[13px] font-medium tracking-wide text-paper/60 uppercase">03 Match</p>
              <p className="mt-6 font-display text-[clamp(2rem,4vw,3rem)] leading-none">
                11 ms per line
              </p>
              <p className="mt-3 max-w-md text-[15px] text-paper/70">
                Every name is checked against a catalogue of 254,000 products with a trigram index,
                so misspellings land on the real medicine.
              </p>
            </Tile>
            <Tile tone="accent" className="lg:col-span-2">
              <TileLabel className="!text-accent">04 Review</TileLabel>
              <p className="mt-6 text-[17px] leading-snug">
                Each item shows the line it came from and how sure the match is. Fix anything in place,
                then confirm.
              </p>
            </Tile>
            <Tile className="lg:col-span-2 lg:row-span-2 flex flex-col justify-between">
              <TileLabel>05 Your day</TileLabel>
              <div className="mt-8 space-y-5">
                {ROUTINE.map(([slot, name, taken]) => (
                  <div key={slot + name} className="flex items-center gap-4">
                    <span
                      className={`grid size-7 shrink-0 place-items-center rounded-full border ${
                        taken ? "border-accent bg-accent text-paper" : "border-line-strong"
                      }`}
                    >
                      {taken && <Check className="size-3.5" />}
                    </span>
                    <div className={`min-w-0 flex-1 ${taken ? "opacity-50" : ""}`}>
                      <p className="truncate text-[16px] font-medium">{name}</p>
                      <p className="text-[13px] text-muted">{slot}</p>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-8 text-[15px] text-muted">Tick doses off. See what is ending soon.</p>
            </Tile>
            <Tile>
              <TileLabel>06 Same, for less</TileLabel>
              <p className="mt-6 text-[17px] leading-snug">
                Every medicine shows products with the identical composition, cheapest first.
              </p>
            </Tile>
            <Tile>
              <TileLabel>Private</TileLabel>
              <p className="mt-6 text-[17px] leading-snug">
                Images stay private. Export or delete everything whenever you like.
              </p>
            </Tile>
          </Bento>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-8 text-[13px] text-muted sm:flex-row sm:justify-between">
          <p>RxVision reads prescriptions. It does not give medical advice.</p>
          <p>Always check results against the original.</p>
        </div>
      </footer>
    </div>
  );
}
