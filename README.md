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

## Run it

```bash
pip install -r requirements.txt
python src/main.py
```

_(Stages beyond fetch/cache are still in progress — this README grows with each stage.)_

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
- [ ] Stage 4 — clean, validate, store
- [ ] Stage 4 — clean, validate, store
- [ ] Stage 5 — survive failures, report the run
- [ ] Stage 6 — publish evidence