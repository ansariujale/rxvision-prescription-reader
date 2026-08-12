# Evaluation log

Notes on the tests I've run on this project — what I measured, what the numbers
were, and what I changed because of them. Oldest first.

I started keeping this because I'd been carrying an accuracy figure I couldn't
actually back up, and I wanted somewhere to write down what I'd really measured
so I'd stop guessing.

Setup when I ran these: Windows 11, Python 3.13, Tesseract 5.5.3, AWS Textract
`detect_document_text` in `ap-south-1`, and the 253,973-name medicine dataset.

To repeat any of it:

```bash
python -m eval.ocr_runner --images eval/images
```

```bash
python -m eval.evaluate --labels eval/labels.csv --sweep
```

Only the first one costs money. It runs both OCR engines over each image once
and caches the text, so I can score any routing strategy afterwards without
paying again.

---

## 1. The confidence score was wrong

A clean printed test page kept getting sent to Textract even though Tesseract
had read it perfectly. Turned out `get_tesseract_confidence` was reporting 43
when the real figure was 95.

Tesseract returns a row per page, block, paragraph and line as well as per word,
and the non-word rows have a confidence of `-1`. The line meant to drop them
compared each value against the string `'-1'`, but pytesseract gives you ints,
so the comparison never matched and all the `-1`s got averaged in.

Since escalation triggers below 70, this meant *every* image went to Textract no
matter how well Tesseract did. The fallback wasn't a fallback — it ran every
time and Tesseract's output was always thrown away.

Fixed, with tests in `eval/tests/test_confidence.py`.

## 2. Inverting the image was making OCR worse

When I restructured the preprocessing chain, `invert_image` went from being a
step whose output was ignored to one that fed everything after it. So I checked
whether it was actually helping.

Same test page through both:

| | text Tesseract read | confidence |
|---|---|---:|
| with inversion | `Augmentin625 DuojTablet` | 33.0 |
| without | `Augmentin 625 Duo Tablet` | 95.5 |

Tesseract wants dark text on light background and inverting gives it the
opposite. 33 is also under the escalation threshold, so it would have pushed
everything to Textract as well.

Took it out of the steps list. Kept the function in case I ever need it for a
scan that's genuinely inverted.

## 3. Speeding up the medicine matching

Matching one line of OCR text against 253,973 names was taking about 3.5
seconds. One evaluation run would have been ~28 minutes and a threshold sweep
over two hours, which meant I wasn't going to experiment much.

Worth noting the slow lines are the ones that *don't* match anything — the
scorer stops early on a perfect match, but a line matching nothing has to check
everything. On a prescription most lines are the doctor's name, the address,
dosage instructions. So I timed everything against a non-matching line.

Most of what I tried didn't work:

| what I tried | result |
|---|---|
| `score_cutoff=68` | slower, 6.3s vs 4.7s |
| pre-sorting tokens once | 1.1–2x |
| `cdist` across all 8 cores | slower, 0.8x |
| filtering candidates by string length | 1.1x, drug names are all similar lengths |
| deduplicating the dataset | only 2% duplicates |

What did work was a trigram inverted index — index each name by its
three-character pieces, then only score the few hundred names sharing the most
pieces with the query.

| | speedup | missed |
|---|---:|---|
| index, top 400 | 150x | 0 / 60 |
| + dropping trigrams in >10% of names | 497x | 0 / 60 |
| + top 200 | 817x | 1 / 60 |
| + top 100 | 1072x | 1 / 60 |

Below 400 it starts losing real matches, so that's the floor.

Then stripping the dosage words. Almost every name ends in "Tablet", so `tab`,
`let`, `abl` show up in about 60% of the dataset and don't narrow anything
down. My first attempt at this made things *worse*:

| | correct | ms |
|---|---:|---:|
| full names | 42 / 50 | 30.2 |
| full names, common trigrams dropped | 42 / 50 | 11.7 |
| dosage words stripped with a regex | **34 / 50** | 8.3 |
| stripped fuzzily | **46 / 50** | 9.2 |
| stripped fuzzily + common trigrams dropped | 46 / 50 | 7.4 |

The regex version strips `tablet` from the dataset but not `tablel` from the
OCR text, so the query ends up carrying a word the dataset entry doesn't have
and the score drops. Making the stripper fuzzy on both sides fixed it.

It also has to strip whole words, not substrings — cutting `tab` out of
`ventab dxt` or `let` out of `clopilet` destroys real drug names.

On the real dataset rather than the test subset: **3,500ms down to 11.5ms per
line**, and on 25 corrupted drug names it got 21 right — exactly the same 21 as
brute force. Building the index takes 46 seconds, cached to disk and reloads in
0.2.

One thing to be honest about: this is a filter, not an exhaustive search. Zero
misses in 60 tries means the miss rate is probably under 5%, not that it's
zero.

## 4. Textract on the original vs the preprocessed image

Production sends Textract the binarised, denoised image. Textract does its own
preprocessing internally so I thought the original photo might do better.

5 prescriptions, medicines found:

| | original | processed |
|---|---:|---:|
| rx_3 | 13 | 12 |
| rx_4 | 1 | 1 |
| rx_5 | 6 | 8 |

Inconclusive. Three usable images and they split roughly evenly. I didn't
change anything — five images can't answer this.

## 5. First real evaluation — 30 labelled prescriptions

Labelled 30 real prescriptions by hand before looking at any OCR output. 85
medicines total, about 2.8 per prescription, 4 with nothing legible.

First I checked whether the drugs I'd labelled are even in the dataset, since
the matcher can only ever return something that's in there:

- 63 (74%) are in it exactly
- 8 (9%) have a close match
- 14 (16%) aren't in it at all — `D-Task 60k`, `Nervmax Nt`, `Hexabenz Spray`,
  and `L.S Belt`, which is a support belt and not a drug at all

So 83% reachable. Not the main problem.

Results:

| | precision | recall | f1 | whole prescription right | textract calls |
|---|---:|---:|---:|---:|---:|
| tesseract only | 0.000 | 0.000 | 0.000 | 0.100 | 0% |
| textract only | 0.052 | **0.129** | 0.074 | 0.033 | 100% |
| escalate at 70 | 0.035 | 0.071 | 0.047 | 0.000 | 73% |

Three things came out of this.

**Tesseract found zero medicines across all 30.** So the whole
confidence-based escalation has no point — there's nothing to save by using
Tesseract first. Escalating at 70 is actually *worse* than just always calling
Textract, because on 27% of images it keeps Tesseract's empty result.

**A lot of the time the OCR just can't read the handwriting.** For `rx_3` not
one of the six drugs I labelled appears anywhere in Textract's raw text. That's
the ceiling — no amount of matcher tuning gets back words that were never read.

**The matcher returns a lot of rubbish.** Of 233 things it returned, 69 were
three characters or shorter — `'x'`, `'10'`, `'lad'`. Bits of the hospital
letterhead and stray numbers matching short drug names.

I tried refusing to match very short lines:

| minimum line length | precision | recall | f1 |
|---:|---:|---:|---:|
| 0 (what it does now) | 0.052 | 0.129 | 0.074 |
| 4 | 0.070 | 0.129 | 0.091 |
| 6 | 0.085 | 0.118 | 0.099 |
| 8 | 0.095 | 0.094 | 0.095 |
| 10 | 0.119 | 0.082 | 0.097 |

Precision more than doubles at 10 but recall drops and f1 barely moves. Worth
doing, doesn't fix anything.

Things wrong with this run that I should fix next time: 30 is a small sample so
these are rough numbers, I didn't split the labels into a tuning set and a
holdout set so I can't tune thresholds on this data without fooling myself, and
the harness gives Textract the original image while the app gives it the
processed one.

---

## Where it stands

12.9% recall and 5.2% precision on 30 real prescriptions. It finds roughly one
medicine in eight and most of what it reports is wrong.

The bottleneck is OCR on handwriting. Matching and speed are both much better
than they were and neither is what's holding it back.

That also means I can't put any accuracy number on this project except that
one. Whatever I'd assumed before was never measured.

What I want to do next:

1. Drop the confidence-based escalation, since it measurably does worse than
   just using Textract
2. Add the minimum line length filter, which doubles precision for free
3. Look at OCR that's actually built for handwriting — or accept this works on
   printed prescriptions and say so
4. Label more, with a proper tune/holdout split, before tuning anything
