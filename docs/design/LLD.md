# RxVision: Low Level Design

Companion to the [HLD](HLD.md). This is the build sheet: modules, tables, API
contracts, algorithms and UI structure.

## 1. Backend modules

```
backend/app/
  main.py                 app factory, lifespan (index load, crash recovery)
  core/
    config.py             Settings (pydantic-settings, env driven)
    security.py           bcrypt hashing, JWT encode/decode
    ratelimit.py          in-memory token bucket dependency
    errors.py             uniform error envelope + handlers
  db/
    base.py               DeclarativeBase, naming conventions
    session.py            async engine, session factory, get_session dep
  models/                 SQLAlchemy ORM: User, Scan, ScanItem, Medicine
  schemas/                Pydantic request/response models
  api/
    deps.py               current_user, owned_scan
    router.py             mounts v1 routers under /api/v1
    routes/               auth, scans, items, medicines, system
  services/
    images.py             validate, orient, crop, downscale, re-encode
    storage.py            Storage protocol + LocalStorage
    dosage.py             rule based dosage parser
    matching/index.py     trigram MedicineIndex (ported from v1)
    matching/catalog.py   process wide index holder, build/load from DB
    ocr/                  base, gemini, claude, textract, mock, factory
    pipeline.py           process_scan(scan_id): the background job
    export.py             CSV and PDF rendering
  scripts/seed.py         load medicines CSV into Postgres (idempotent)
  data/sample_medicines.csv   small bundled catalogue for zero setup runs
```

Dependency direction: `routes -> services -> models/db`. Services never import
routes; `pipeline.py` is the only module that knows about OCR, parsing and
matching together.

## 2. Database schema

All timestamps are `timestamptz`. UUID primary keys for user owned rows so ids
in URLs are not guessable or countable.

### users

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| email | varchar(320) unique | stored lowercased |
| name | varchar(120) | |
| password_hash | varchar(100) | bcrypt |
| created_at | timestamptz | default now |

### medicines

| column | type | notes |
|---|---|---|
| id | integer pk | |
| name | varchar(300) | e.g. `Augmentin 625 Duo Tablet`, indexed |
| manufacturer | varchar(200) null | |
| type | varchar(50) null | `allopathy` etc. |
| pack_size | varchar(120) null | `strip of 10 tablets` |
| composition | text null | `Amoxycillin (500mg) + Clavulanic Acid (125mg)` |
| price | numeric(10,2) null | INR |
| uses | text null | optional, not in every dataset |

### scans

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| user_id | uuid fk users on delete cascade | indexed with created_at |
| title | varchar(160) | user editable, default from date |
| status | varchar(16) | `queued`, `processing`, `done`, `failed` |
| provider | varchar(20) | provider used |
| image_key | varchar(80) | storage key, never exposed |
| image_width / image_height | int | |
| raw_text | text null | full OCR text |
| error | text null | user safe failure message |
| duration_ms | int null | processing time |
| prescribed_on | date null | start of the course; defaults to the upload date |
| doctor | varchar(160) null | read by LLM providers, editable |
| in_routine | bool | default false; true once the user adds it to the routine |
| created_at / completed_at | timestamptz | |

### scan_items

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| scan_id | uuid fk scans on delete cascade | indexed |
| position | int | display order |
| name | varchar(300) | what the user sees; canonical name when matched |
| medicine_id | int fk medicines null, on delete set null | catalogue link |
| strength | varchar(60) null | `650 mg` |
| dose | varchar(60) null | `1 tablet` |
| frequency | varchar(60) null | `1-0-1`, `Twice daily` |
| duration | varchar(60) null | `5 days` |
| timing | varchar(60) null | `After food` |
| notes | text null | |
| confidence | float null | 0..1 match score; null for manual items |
| source_line | text null | raw OCR line the item came from |
| status | varchar(16) | `suggested`, `confirmed`, `edited`, `manual` |

### dose_logs

| column | type | notes |
|---|---|---|
| id | uuid pk | |
| item_id | uuid fk scan_items on delete cascade | |
| day | date | the user's local date |
| slot | varchar(12) | `morning`, `afternoon`, `evening`, `night`, `as_needed` |
| taken_at | timestamptz | |

Unique on `(item_id, day, slot)`. A row means "taken"; un-ticking deletes it.

Migrations are managed by Alembic (`backend/alembic/`).

## 3. API

Base path `/api/v1`. JSON everywhere except the upload (multipart) and exports.
Authentication by the `rx_session` httpOnly cookie, or `Authorization: Bearer`.

### Error envelope

```json
{ "error": { "code": "not_found", "message": "Scan not found" } }
```

Codes: `validation_error` 422, `unauthorized` 401, `not_found` 404,
`conflict` 409, `payload_too_large` 413, `unsupported_media` 415,
`rate_limited` 429, `internal` 500.

### Routes

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | liveness + db check + index size |
| GET | `/providers` | no | active OCR provider and which are configured |
| POST | `/auth/register` | no | create account, sets cookie |
| POST | `/auth/login` | no | sets cookie |
| POST | `/auth/logout` | no | clears cookie |
| GET | `/auth/me` | yes | current user |
| GET | `/stats` | yes | totals for the dashboard |
| POST | `/scans` | yes | upload image (+crop), 202 |
| GET | `/scans` | yes | history: `?q=&limit=&offset=` |
| GET | `/scans/{id}` | yes | full scan with items |
| PATCH | `/scans/{id}` | yes | title, prescribed_on, doctor, in_routine |
| DELETE | `/scans/{id}` | yes | delete scan and image, 204 |
| POST | `/scans/{id}/retry` | yes | re-run a failed scan |
| GET | `/scans/{id}/image` | yes | the normalised image |
| GET | `/scans/{id}/export?format=csv\|pdf` | yes | download |
| POST | `/scans/{id}/items` | yes | add a manual item |
| PATCH | `/scans/{id}/items/{item_id}` | yes | edit or confirm |
| DELETE | `/scans/{id}/items/{item_id}` | yes | remove, 204 |
| POST | `/scans/{id}/items/confirm-all` | yes | confirm every suggested item |
| GET | `/medicines/search?q=&limit=` | yes | autocomplete via the index |
| GET | `/medicines/{id}` | yes | catalogue entry |
| GET | `/medicines/{id}/alternatives` | yes | same composition, cheapest first |
| GET | `/medicines/{id}/history` | yes | the user's items linked to this medicine |
| GET | `/me/medicines?q=` | yes | everything the user was prescribed, grouped |
| GET | `/routine?day=YYYY-MM-DD` | yes | the day's slots, items, progress |
| PUT | `/routine/doses` | yes | mark a dose taken or not |
| PATCH | `/auth/me` | yes | change name |
| POST | `/auth/password` | yes | change password (needs current) |
| DELETE | `/auth/me` | yes | delete account and all data (needs password) |
| GET | `/me/export` | yes | every scan and item as JSON |

### Key payloads

`POST /auth/register`

```json
{ "email": "a@b.com", "name": "Asha", "password": "at least 8 chars" }
```

`POST /scans` (multipart): `image` file, optional `crop` as JSON
`{"x":0.1,"y":0.05,"width":0.8,"height":0.6}` in fractions of the image, so the
client never has to know the original pixel size.

`ScanOut`

```json
{
  "id": "uuid", "title": "Prescription, 15 Oct", "status": "done",
  "provider": "gemini", "created_at": "...", "completed_at": "...",
  "duration_ms": 4120, "error": null, "raw_text": "...",
  "image_url": "/api/v1/scans/uuid/image",
  "items": [ItemOut]
}
```

`ItemOut`

```json
{
  "id": "uuid", "position": 0, "name": "Augmentin 625 Duo Tablet",
  "medicine": { "id": 81, "name": "Augmentin 625 Duo Tablet",
                "manufacturer": "...", "composition": "..." },
  "strength": "625 mg", "dose": "1 tablet", "frequency": "1-0-1",
  "duration": "5 days", "timing": "After food", "notes": null,
  "confidence": 0.91, "source_line": "Tab Augmentin 625 1-0-1 x5d",
  "status": "suggested"
}
```

`PATCH /scans/{id}/items/{item_id}`: any subset of `name, medicine_id,
strength, dose, frequency, duration, timing, notes, status`. Sending
`medicine_id` relinks the item and sets `name` to the catalogue name unless a
name is also sent. Any field change sets `status` to `edited` unless the request
sets `status` itself.

## 4. Upload handling (`services/images.py`)

1. Reject over `MAX_UPLOAD_MB` (10) while streaming, before decoding. 413.
2. Decode with Pillow; failure is 415. Accept JPEG, PNG, WebP only (by decoded
   format, not by extension).
3. Guard against decompression bombs: refuse above 40 megapixels.
4. `ImageOps.exif_transpose` so phone photos are upright.
5. Apply the crop if given (fractions clamped to [0,1], minimum 5% per side).
6. Downscale so the long edge is at most 2400 px (OCR gains nothing above that).
7. Convert to RGB and re-encode as JPEG quality 90, which strips EXIF and GPS.

## 5. OCR providers (`services/ocr/`)

```python
class OcrResult:
    text: str                       # full text, newline separated
    lines: list[str]
    medicines: list[ExtractedMedicine] | None   # None for text-only providers

class ExtractedMedicine:
    name: str
    strength, dose, frequency, duration, timing, notes: str | None
    source_line: str | None

class OcrProvider(Protocol):
    name: str
    async def read(self, image: bytes, mime: str) -> OcrResult: ...
```

| Provider | Transport | Notes |
|---|---|---|
| Gemini | REST `generateContent`, `responseMimeType: application/json` with a response schema | model from `GEMINI_MODEL` |
| Claude | REST Messages API, image block, JSON only instruction | model from `CLAUDE_MODEL` |
| Textract | boto3 `detect_document_text`, run in a worker thread | lines only |
| Mock | returns a fixed realistic prescription | lines only, offline |

Selection (`factory.py`): `OCR_PROVIDER=auto` picks the first configured of
gemini, claude, textract, then mock. Calls have a 45 s timeout and one retry on
a 429 or 5xx.

The LLM prompt asks for the medicine section only, a verbatim `source_line` per
item, `null` for anything unreadable, and explicitly forbids guessing names it
cannot read. Names are then verified by the matcher.

## 6. Dosage parser (`services/dosage.py`)

Input is one prescription line; output is a `ParsedLine` with the fields above
plus `name_part` (what is left once dosage tokens are removed). Each rule
removes its span from the working string so later rules and the matcher see
less noise.

| Field | Recognises | Normalised to |
|---|---|---|
| frequency | `1-0-1`, `1-1-1`, `0-0-1`, `1/2-0-1/2` | the pattern itself |
| | `OD`, `QD`, `once daily` | `Once daily` |
| | `BD`, `BID`, `twice daily` | `Twice daily` |
| | `TDS`, `TID`, `thrice daily` | `Three times daily` |
| | `QID`, `QDS` | `Four times daily` |
| | `HS`, `at bedtime`, `at night` | `At bedtime` |
| | `SOS`, `PRN`, `as needed` | `As needed` |
| | `STAT` | `Immediately` |
| duration | `x 5 days`, `for 1 week`, `5d`, `x2w`, `10 days` | `5 days`, `1 week`, `2 weeks` |
| timing | `AC`, `before food/meals`, `PC`, `after food/meals`, `empty stomach`, `with food` | `Before food`, `After food`, `Empty stomach`, `With food` |
| strength | `650 mg`, `500mg`, `5 ml`, `0.5 mg`, `60k`, `1 g`, `2%` | `650 mg`, `60000 IU` for `60k` |
| dose | `1 tab`, `2 caps`, `1/2 tab`, `10 ml`, `2 puffs`, `1 drop` | `1 tablet`, `½ tablet`, `2 puffs` |

The leading dosage-form prefix (`Tab.`, `Cap`, `Syp`, `Inj`) and list numbering
(`1.`, `2)`) are stripped from `name_part` as in v1's `clean_ocr_line`.

## 7. Matching (`services/matching/`)

`MedicineIndex` is the v1 trigram index with one change: it stores the catalogue
id next to each name, so a match returns `(medicine_id, name, score)`.

- Keys: lowercased, `mg` removed, dosage form words stripped fuzzily, whole
  tokens only.
- Candidates: names sharing the most trigrams, top 400, trigrams present in more
  than 10% of names dropped (but never below 50 occurrences).
- Scoring: RapidFuzz `token_sort_ratio`, threshold 68 (from v1 measurement).
- Lines shorter than 6 characters after cleaning are not matched (v1 measured
  this doubles precision).

`catalog.py` holds the process wide index. At startup it computes a fingerprint
of the table (`count`, `max(id)`), loads `INDEX_CACHE_DIR/index-<fp>.pkl` if it
exists, otherwise builds from the database in a worker thread and saves it.

Confidence bands used by the UI:

| score | band | UI |
|---|---|---|
| >= 0.85 | high | plain |
| 0.68 to 0.85 | review | amber marker |
| no match | unmatched | outlined, prompts to pick from catalogue |

## 8. Pipeline (`services/pipeline.py`)

```
process_scan(scan_id):
    scan = load; if status not in (queued, processing): return
    status = processing; commit
    t0 = now
    try:
        result = await provider.read(storage.read(scan.image_key))
        if result.medicines is not None:          # structured provider
            for m in result.medicines:
                hit = index.match(m.name, min_length=3)
                item from m, linked to hit if any, confidence = hit.score or None
        else:                                     # text provider
            for line in result.lines:
                p = parse_line(line)
                hit = index.match(p.name_part)
                if hit: item from p and hit   # unmatched lines are letterhead noise
        dedupe items by medicine_id (keep the higher confidence)
        save items, raw_text, status = done, duration_ms
    except ProviderError as e:  status = failed, error = e.user_message
    except Exception:           status = failed, error = generic; log stack
```

On application start, scans in `queued` or `processing` are re-scheduled.

## 9. Routine (`services/routine.py`)

The routine is computed per request from items on scans with `in_routine`.

**Slots from frequency.** A pattern `a-b-c` maps to morning, afternoon, night;
`a-b-c-d` to morning, afternoon, evening, night. Each non-zero position is a
slot, and its value (`1`, `1/2`, `2`) is the quantity shown. Words map as:

| frequency | slots |
|---|---|
| Once daily | morning |
| Twice daily | morning, night |
| Three times daily | morning, afternoon, night |
| Four times daily | morning, afternoon, evening, night |
| At bedtime | night |
| As needed | as_needed |
| Once weekly | morning, on days 1, 8, 15... of the course |
| missing or unknown | morning, flagged "check frequency" |

A timing of `At bedtime` moves a single morning slot to night.

**Course window.** `start = scan.prescribed_on or scan.created_at.date()`.
`duration_days` comes from the duration string (`5 days` = 5, `2 weeks` = 14,
`1 month` = 30). An item is active on `day` when
`0 <= (day - start).days < duration_days`. Without a duration it is treated as
30 days and flagged `no_duration`. Each entry reports `day_of_course`,
`total_days` and `ends_on`; items ending within two days are listed in
`ending_soon`.

**Response.**

```json
{
  "day": "2026-10-15",
  "slots": [{ "slot": "morning", "entries": [RoutineEntry] }],
  "as_needed": [RoutineEntry],
  "progress": { "taken": 3, "total": 7 },
  "ending_soon": [RoutineEntry],
  "upcoming_days": [{ "day": "...", "total": 7 }]
}
```

`RoutineEntry` has the item, the scan id and title, quantity, slot, `taken`,
`day_of_course`, `total_days`, and flags.

## 10. Alternatives (`routes/medicines.py`)

Composition strings are normalised (lowercase, whitespace collapsed, `mg`
spacing unified, parts sorted on ` + `) and compared for equality. Results
exclude the medicine itself, sort by price with unknown prices last, and cap at
12. Shown as information, never as a recommendation to switch.

## 11. Auth (`core/security.py`)

- bcrypt with cost 12. Passwords 8 to 128 characters.
- JWT HS256, claims `sub` (user id) and `exp` (7 days), secret `JWT_SECRET`.
- Cookie `rx_session`: httpOnly, SameSite=Lax, Secure when `COOKIE_SECURE=true`,
  path `/`.
- Login failure returns the same message for unknown email and wrong password.
- Rate limits: 10 requests per minute per IP on `/auth/*`, 20 per minute per
  user on `POST /scans`.

## 12. Export (`services/export.py`)

CSV columns: `#, medicine, strength, dose, frequency, duration, timing, notes,
status, confidence, matched catalogue name, composition`.

PDF (ReportLab): title, date, provider, a table of the same fields, and a footer
stating the list was machine read and reviewed by the user, not a prescription.

## 13. Frontend

### Routes (App Router)

| Path | Layout | Content |
|---|---|---|
| `/` | marketing | typographic hero, live demo of a line becoming fields, bento explainer |
| `/login`, `/register` | auth | single column form |
| `/today` | app shell | the day's routine: week strip, progress, slots, ending soon |
| `/scan` | focused (no nav) | capture, crop, reading, review, add to routine |
| `/prescriptions` | app shell | searchable list, filter by in routine |
| `/prescriptions/[id]` | app shell | image beside editable items, routine controls |
| `/medicines` | app shell | everything prescribed, grouped, plus catalogue search |
| `/medicines/[id]` | app shell | composition, your history, alternatives |
| `/settings` | app shell | profile, password, export, delete account |

Global: `Ctrl+K` / `Cmd+K` opens a command palette that searches prescriptions,
the user's medicines and the catalogue, and jumps to any page.

Bento grids are used where content is a set of unlike pieces (the landing
explainer, the medicine page header). Lists of like things (prescriptions,
medicines, routine entries) are plain vertical lists, and forms are a single
column.

### Structure

```
frontend/src/
  app/                    routes above, plus layout.tsx, globals.css
  components/
    ui/                   Button, Input, Field, Badge, Spinner, Reveal, Bento, Tile
    scan/                 Dropzone, Cropper, ScanImage, ItemRow, ItemEditor,
                          MedicineSearch, ProcessingState, ExportMenu
    shell/                AppShell, Nav, ThemeToggle
  lib/
    api.ts                fetch wrapper: base /api/v1, JSON, ApiError
    types.ts              mirrors of the API schemas
    hooks.ts              useMe, useScan (polls while queued/processing), useScans
    format.ts             dates, confidence bands
```

Data fetching uses SWR. `useScan` sets `refreshInterval` to 1200 ms while the
scan is `queued` or `processing` and to 0 afterwards. Item edits are optimistic:
the list updates first, then reconciles with the server response, and rolls back
with a toast on failure.

Auth gating happens in the app shell: it calls `/auth/me` and redirects to
`/login?next=...` on 401.

### Visual system

- Type does the work. Display: Instrument Serif. Text: Geist. Numbers and raw
  OCR lines: Geist Mono.
- Scale: 13, 15, 17, 22, 32, 48, 72 px. Tight leading on display sizes.
- Colour: warm paper and ink, one green for confirmed, one amber for review.
  Light and dark themes from the same tokens, system preference by default.
- Surfaces: 1 px hairlines and 20 px radius tiles, no heavy shadows.
- Copy: short, plain, no em dashes.

### Motion

- Entrance: 10 px rise plus fade, 450 ms, ease `[0.22, 1, 0.36, 1]`, staggered
  40 ms in lists.
- Layout: item add, remove and reorder animate with shared layout transitions.
- Processing: a soft scan line sweeps the prescription image.
- Hover: tiles lift 2 px; buttons darken. Nothing bounces.
- All motion respects `prefers-reduced-motion`.

## 14. Testing

| Layer | Tool | Covers |
|---|---|---|
| Unit | pytest | dosage parser, index, image normalisation, security helpers |
| API | pytest + httpx ASGI client + SQLite | auth flow, ownership isolation, scan lifecycle with the mock provider, item edits, export |
| Frontend | `next build` type check | compile time contract with `types.ts` |

## 15. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://rx:rx@db:5432/rxvision` | |
| `JWT_SECRET` | none, required outside dev | |
| `COOKIE_SECURE` | `false` | set true behind HTTPS |
| `OCR_PROVIDER` | `auto` | `gemini`, `claude`, `textract`, `mock` |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | none, `gemini-2.5-flash` | |
| `ANTHROPIC_API_KEY`, `CLAUDE_MODEL` | none, `claude-sonnet-5-5` | |
| `AWS_REGION` | `ap-south-1` | Textract uses the normal boto3 credential chain |
| `STORAGE_DIR` | `/data/images` | |
| `INDEX_CACHE_DIR` | `/data/cache` | |
| `MEDICINE_CSV` | bundled sample | full dataset path for seeding |
| `MAX_UPLOAD_MB` | `10` | |
