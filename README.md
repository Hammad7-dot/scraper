# The Polite Scraper — Books to Scrape

FlyRank Internship · Backend Track · Week 5 · Assignment A9

A small, polite scraping pipeline: downloads the first three catalogue pages of
[Books to Scrape](https://books.toscrape.com), visits all 60 book pages, turns messy HTML
into clean, validated JSON records, survives a broken page without crashing, and ends every
run with a short report of what happened.

## Target classification (Stage 0)

- **Site:** [books.toscrape.com](https://books.toscrape.com) — a sandbox site built specifically
  for people to practice scraping on. The site's own homepage says so directly ("We love being
  scraped!").
- **Scope:** the first 3 catalogue pages only (`/catalogue/page-1.html` through `page-3.html`),
  plus the ~60 individual book detail pages those 3 pages link to. Nothing outside that scope is
  requested.
- **`robots.txt` check:** requested `https://books.toscrape.com/robots.txt` once — the file does
  not exist (404). A missing file is not permission, it's just a missing file; permission here
  comes from the site's own "sandbox for practice" framing instead.
- **Data collected:** book title, product URL, price, availability, star rating, description,
  plus provenance (which catalogue page it came from, when it was fetched).
- **Why this is appropriate here:** the site exists for exactly this purpose, the scope is small
  and fixed (3 pages, not the full 1000-book catalogue), and every request is rate-limited and
  identifies itself.

**I will not reuse this code on another site without checking its rules and terms first.**

## Lane

Python 3.10+ — `requests` for HTTP, `BeautifulSoup` for HTML parsing, `Pydantic` for schema
validation.

## Politeness rules this scraper follows

- Identifies itself with a real user-agent naming the project and a contact link (see
  `src/main.py` — `USER_AGENT`, update the repo URL there once this is pushed).
- Every request has a timeout — it gives up rather than hanging forever.
- Checks the HTTP status code before doing anything with a response; only `200` is treated as
  success.
- Waits at least 500ms between real requests to the site.
- Reads from a local cache (`cache/`) instead of re-requesting a page it already has.

## Record schema

Defined in code with Pydantic (`BookRecord` in `src/main.py`); the shape validated before
anything reaches `books.json`:

| Field | Type | Required? | Notes |
|---|---|---|---|
| `title` | string | required, non-empty | |
| `product_url` | string | required | must start with `https://`; this book's canonical identity |
| `price_text` | string | required | raw text as scraped, e.g. `"£51.77"` |
| `price_gbp` | number | required, `> 0` | parsed from `price_text` |
| `availability_text` | string | required | e.g. `"In stock (22 available)"` |
| `rating_text` | string | required | one of `One`/`Two`/`Three`/`Four`/`Five` |
| `description` | string or `null` | optional | `null` when the book genuinely has none — never invented |
| `source_page` | string | required | must start with `https://`; which catalogue page this book was found on |
| `fetched_at` | string (ISO 8601) | required | see the noted limitation above re: cache hits |

## Run command

```bash
cd scraper
pip install -r requirements.txt
python src/main.py
```

Produces `output/books.json` (60 validated records), `output/errors.json` (any records that
failed validation, with why), and `output/run-report.json` (what actually happened during
the run). A sample of all three from a real run is committed in this repo under `output/`.

## Why this needed no browser

Every field this scraper collects — title, price, availability, rating, description — is
already present in the plain HTML the server sends back; nothing on these pages is rendered
client-side by JavaScript. A headless browser (Playwright, Selenium, etc.) would add real
startup and memory cost for zero additional data.

## Ethics note

This scraper only touches `books.toscrape.com`, a sandbox built specifically for scraping
practice — I checked that directly rather than assuming. More generally: prefer an official
API over scraping when one exists; never bypass a login, paywall, or an explicit block;
collect only the data actually needed for the task, not everything reachable.

## A real run-report.json

```json
{
  "start_time": "2026-08-08T21:18:23.238249+00:00",
  "duration_seconds": 1.55,
  "pages_fetched": 0,
  "cache_hits": 63,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": []
}
```

`pages_fetched: 0` / `cache_hits: 63` here because this particular run read all 63 pages
(3 catalogue + 60 books) from the local cache rather than hitting the site again — that's
the cache working as intended, not a bug.

## Resilience & the run report

- A timeout, connection error, or 5xx gets **one retry** after a short pause — those are
  plausibly transient. A **404 or 403 is never retried**: the page doesn't exist, or the
  site said no, and asking again doesn't change either.
- One broken book page is logged and skipped (`SKIP` in the output) — it doesn't stop the
  other 59 from being scraped.
- Every run writes `output/run-report.json`: start time, duration, pages actually
  fetched, cache hits, valid/invalid record counts, and a list of any failed pages with
  the reason.
- Proven with a deliberately broken URL: flip `INJECT_FAKE_BOOK_FOR_TESTING = True` in
  `src/main.py` for one run, then flip it back. See `run-report.json` from that run for
  the proof — `failed_pages` should show exactly one entry, and `valid_records` should
  still be 60.

## Bugs found & fixed

- **Mojibake in prices (`Â£51.77` instead of `£51.77`).** `books.toscrape.com` doesn't
  declare a charset in its `Content-Type` header, so `requests` defaulted to guessing
  Latin-1 instead of the page's actual UTF-8. Fixed by explicitly setting
  `response.encoding = "utf-8"` before reading `response.text`. Caught by comparing a
  real scraped record against the live page directly. **Note:** pages already fetched
  before this fix have the mangled text baked into `cache/` — clear the cache and
  re-run after pulling this fix.

## Known limitations / deviations

- `fetched_at` is set to the time the record is *built* (i.e. when the extraction step
  runs), not the time the page was physically fetched over the network. On a cache hit,
  those two times differ — the HTML was fetched earlier, but `fetched_at` reflects "now."
  A stricter version would persist the real fetch timestamp alongside each cached file.
  Noted here rather than silently fixed, per Stage 5's "don't gold-plate" guidance.

## Status

- [x] Stage 0 — classify target
- [x] Stage 1 — fetch and cache HTML
- [x] Stage 2 — discover all three catalogue pages
- [x] Stage 3 — extract raw records
- [x] Stage 4 — clean, validate, store
- [x] Stage 5 — survive failures, report the run
- [ ] Stage 6 — publish evidence