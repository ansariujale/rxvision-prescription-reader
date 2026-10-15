# RxVision

Read a photo of a handwritten prescription into a structured, reviewable medication list:
medicine, strength, dose, frequency, duration and timing, each matched to a real catalogue entry.

Version 2 is a web app (FastAPI + Next.js + Postgres). The original PyQt desktop app, its
evaluation harness and its write-ups are kept in [`legacy/`](legacy/).

- [High level design](docs/design/HLD.md): goals, architecture, pipeline, decisions, scaling path
- [Low level design](docs/design/LLD.md): modules, schema, API contracts, algorithms, UI system

## What it does

1. **Scan.** A focused, full-screen flow: photograph or upload, crop to the medicines, watch it
   read, then review. Gemini is the default OCR because it handles handwriting and returns
   structured fields; Claude, AWS Textract and an offline mock are built in.
2. **Check.** Every name is matched against the medicine catalogue with a trigram index (about
   11 ms per line across 254k names). Each item shows the line it came from and a confidence
   score; unsure or unmatched items are flagged. Edit, add, remove or confirm anything.
3. **Today.** Add a prescription to your routine and the home screen shows what to take this
   morning, afternoon, evening and night, which day of the course it is, and what finishes soon.
   Tick doses off; browse any day of the week.
4. **Medicines.** Everything you have been prescribed in one list. Each medicine has a page with
   its composition, your history with it, and catalogue products with the identical composition,
   cheapest first.
5. **Keep.** Prescriptions are saved per account with start date and doctor; search them, export
   CSV or PDF, download all your data as JSON, or delete your account and everything with it.

Press `Ctrl K` anywhere in the app to jump to a page, prescription or medicine.

## Run it

Needs Docker.

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Open http://localhost:3000 and create an account. API docs are at http://localhost:3000/api/docs.

With no keys set, the app uses the **mock provider**: every scan returns the same sample
prescription, clearly labelled as sample data. To read real prescriptions, put a Gemini key in
`.env` (free at https://aistudio.google.com/apikey) and restart:

```bash
docker compose up -d api
```

### Full medicine catalogue

An 80-row sample catalogue is bundled so the app works out of the box. For the full ~254k-row
dataset (the A-Z India medicine CSV the original project used), place it at
`data/medicine_names.csv`, set `MEDICINE_CSV=/datasets/medicine_names.csv` in `.env`, then:

```bash
docker compose run --rm api python -m app.scripts.seed --csv /datasets/medicine_names.csv --replace
```

```bash
docker compose restart api
```

The first start after a reload builds the index (about 45 s for the full set) and caches it.

## Develop without Docker

Postgres still runs in Docker:

```bash
docker compose up -d db
```

Backend (Python 3.13):

```bash
cd backend
```

```bash
python -m venv .venv
```

```bash
.venv/Scripts/pip install -r requirements-dev.txt
```

```bash
.venv/Scripts/alembic upgrade head
```

```bash
.venv/Scripts/python -m app.scripts.seed
```

```bash
.venv/Scripts/uvicorn app.main:app --reload --port 8000
```

(On macOS or Linux use `.venv/bin/` instead of `.venv/Scripts/`.)

Frontend (Node 20.9+), in another terminal:

```bash
cd frontend
```

```bash
npm install
```

```bash
npm run dev
```

If the API is not on port 8000, set `API_ORIGIN=http://127.0.0.1:<port>` before `npm run dev`.

## Tests

```bash
cd backend
```

```bash
.venv/Scripts/python -m pytest
```

80 tests: the dosage parser, matching index, routine engine, image normalisation, the scan
pipeline with both provider shapes, and the API end to end against SQLite (auth, ownership
isolation, scan lifecycle, item edits, routine and dose ticks, alternatives, exports, account
deletion, failure and retry). No network or API keys needed.

```bash
cd frontend
```

```bash
npm run build
```

## Layout

```
backend/
  app/api/          routes: auth, scans, items, routine, medicines, me, system
  app/services/     images, storage, dosage parser, matching index, OCR providers, pipeline,
                    routine engine, export
  app/models/       SQLAlchemy models
  alembic/          migrations
  tests/
frontend/
  src/app/          landing, auth, today, scan flow, prescriptions, medicines, settings
  src/components/   ui primitives, app shell, scan components
  src/lib/          API client, hooks, types
docs/design/        HLD and LLD
legacy/             v1 desktop app, evaluation harness and its README
```

## Accuracy, honestly

v1 measured Textract at 12.9% recall on 30 handwritten prescriptions
([legacy/docs/evaluation-log.md](legacy/docs/evaluation-log.md)). That is why v2 defaults to a
vision LLM, but v2 has **not** been re-measured yet. The evaluation harness in `legacy/eval/` is
the way to do it; porting it to call the v2 providers is the obvious next step before quoting any
number.

RxVision reads prescriptions. It does not give medical advice, and results must be checked
against the original by a qualified person.

## Origins

RxVision started as a two-person desktop project. Attribution and the v1 history are in
[legacy/README.md](legacy/README.md).
