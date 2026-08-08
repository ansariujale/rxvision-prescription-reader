# How the medicine index works

Matching one line of OCR text against 254,000 drug names used to take about
3.5 seconds. It now takes about 11 milliseconds, with the same results. This is
how, in the smallest number of ideas possible.

## Start with a textbook

Open the back of any textbook and you find this:

```mermaid
flowchart LR
    subgraph BOOK["The book itself"]
        direction TB
        P1["page 12<br/>chlorophyll, photosynthesis"]
        P2["page 45<br/>chlorophyll, mitochondria"]
        P3["page 89<br/>photosynthesis"]
    end

    subgraph IDX["The index at the back"]
        direction TB
        I1["chlorophyll ....... 12, 45"]
        I2["photosynthesis .... 12, 89"]
        I3["mitochondria ...... 45"]
    end

    BOOK -->|"flip it around"| IDX
```

The book goes **page to words on it**. The index goes **word to pages containing
it**. That flip is the entire idea, and "inverted index" is just its name.

To find photosynthesis you don't read 300 pages. You look up one word and it
hands you two page numbers.

## Ours is the same, with two swaps

| Textbook | Here |
|---|---|
| pages | drugs |
| whole words | three-letter pieces |

```
textbook:   "photosynthesis"  ->  12, 89      page numbers
ours:       "aug"             ->  0, 1        drug numbers
```

The numbers are positions in the drug list. Drug 0, drug 1. That's all they are.

## Why three-letter pieces and not whole words

Because OCR misreads. `Augmentin` comes back as `Augrnentin` — the `m` read as
`rn`.

A word index fails completely: `Augrnentin` simply isn't in it.

A piece index survives, because most of the pieces are still correct:

```mermaid
flowchart LR
    Q["Augrnentin"] --> T["aug · ugr · grn · rne · nen · ent · nti · tin"]
    T --> G["aug ✓ ent ✓ nti ✓ tin ✓<br/>still correct"]
    T --> B["ugr ✗ grn ✗ rne ✗ nen ✗<br/>destroyed"]
    G --> R["enough survives to find the drug"]
```

**Whole words break under OCR damage. Pieces don't.** If you remember one
sentence, remember that one.

### A note on padding, because the counts look wrong otherwise

Before cutting a word up, two spaces go on the front and one on the end:

```
"augrnentin"   ->   "  augrnentin "
```

So a 10-character word becomes 13 characters, and yields **11** pieces rather
than the 8 you get by cutting the bare word. The three extra are `'  a'`,
`' au'` and `'in '`.

They are there so the beginning and end of a word are distinguishable — without
them `dolo` and `xdolo` would share every piece and look identical to the index.
It also means very short names still produce something to index.

Worth knowing when a count doesn't seem to add up: the padding pieces are real
pieces and they score like any other.

## Building the index

Done once, at startup.

```mermaid
flowchart TB
    A["Augmentin 625 Duo Tablet"]
    B["augmentin 625 duo<br/><i>dosage form stripped</i>"]
    C["  a · aug · ugm · gme · men · ent · nti · tin · ...<br/><i>cut into pieces</i>"]
    D[("INVERTED INDEX<br/>aug → 0<br/>ent → 0, 4871<br/>tin → 0, 55, 903")]

    A --> B --> C --> D
```

Walk every drug name, cut it up, and record its position under each piece. With
254,000 names that produces about 3.1 million entries.

## Looking something up

Done for every line of OCR text.

Every piece is shown here so the final number can actually be counted. The
dataset is two drugs: `augmentin` is drug 0, `azithral 500` is drug 1.

```mermaid
flowchart TB
    Q["OCR line: Augrnentin Tablel"]
    S["strip dosage form → augrnentin"]
    T["pad and cut → 11 pieces"]

    M["MATCHED — 7 pieces<br/><br/>'  a' → drug 0, drug 1<br/>' au' → drug 0<br/>'aug' → drug 0<br/>'ent' → drug 0<br/>'in ' → drug 0<br/>'nti' → drug 0<br/>'tin' → drug 0"]
    X["NO MATCH — 4 pieces<br/><br/>'ugr' → nothing<br/>'grn' → nothing<br/>'rne' → nothing<br/>'nen' → nothing<br/><br/><i>these are the ones OCR destroyed</i>"]

    C["COUNT the drug numbers<br/><br/>drug 0 appears 7 times<br/>drug 1 appears 1 time"]
    K["keep the top 400<br/><i>here, both survive</i>"]
    F["run the real fuzzy scorer<br/>on the survivors only"]
    R["augmentin<br/>score 89"]

    Q --> S --> T
    T --> M
    T --> X
    M --> C --> K --> F --> R
```

Count them: seven pieces matched, and every one of them listed drug 0. So drug 0
scores **7**. Drug 1 scores 1, because `'  a'` happens to appear in `azithral`
too — both start with an `a`.

The step people trip over is the counting one, so to be explicit:

> **"drug 0 appeared 7 times" and "drug 0 shares 7 pieces with the query" are
> the same statement.**

The count *is* the similarity estimate. Nothing clever happens — you look up
pieces and tally which drug numbers keep coming back.

Four of eleven pieces were destroyed by a single misread character, and it still
won 7 to 1. That is the property the whole design rests on.

## Where the speed comes from

```mermaid
flowchart LR
    subgraph BEFORE["Before"]
        B1["one line"] --> B2["score against<br/>253,973 names"] --> B3["3,500 ms"]
    end

    subgraph AFTER["After"]
        A1["one line"] --> A2["index narrows<br/>to 400"] --> A3["score against<br/>400 names"] --> A4["11 ms"]
    end
```

The scoring function is unchanged. The threshold is unchanged. The only
difference is how many candidates ever reach it.

That is why the answers don't change — verified against brute force on corrupted
drug names, identical results both ways.

## If you forget how it works

Three questions rebuild it from nothing:

1. **What am I looking up?** — a three-letter piece
2. **What does it give me?** — a list of drug numbers
3. **What do I do with them?** — count which number appears most

## What it costs

**Products merge.** Stripping the dosage form means `Azithral 500 Tablet` and
`Azithral 500 Injection` become the same key, `azithral 500`. About 8,500 groups
collapse this way. The original names are kept alongside so nothing is lost, but
the *match* can't tell them apart. Fine for reading a prescription where the form
often isn't legible; not fine for a dispensing system.

**It can miss.** The index is a filter, not an exhaustive search. If a name
shares very few pieces with the query it never reaches scoring, even if it would
have scored well. Measured at zero misses across 60 corrupted names — which means
the real rate is probably under 5%, not that it is zero. A provable bound exists
via minimum-overlap thresholds; this uses the measured route instead.

**Memory and build time.** About 3.1 million entries held in RAM, and 46 seconds
to build, cached to disk and reloaded in 0.2 s.
