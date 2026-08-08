"""
The Polite Scraper — Books to Scrape
FlyRank Internship, Backend Track, Week 5, A9

Stage 1: fetch once, cache once.
Stage 2: find all three catalogue pages and every unique book link.
Stage 3: extract the raw record from each book page.
Stage 4: clean, validate, and store.
Stage 5: survive failures, report the run.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError, field_validator

# --- Config -----------------------------------------------------------------

# TODO: once this is pushed, replace the placeholder link below with the
# real repo URL, e.g. "https://github.com/Hammad7-dot/scraper" — a site
# owner who sees this in their access logs should be able to find out who's
# requesting their pages and why.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/Hammad7-dot/scraper)"

REQUEST_TIMEOUT_SECONDS = 10
REQUEST_DELAY_SECONDS = 0.5  # only applied between REAL requests, never on cache hits
MAX_ATTEMPTS = 2  # 1 try + 1 retry, only for timeouts / connection errors / 5xx
RETRY_DELAY_SECONDS = 1.0

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

BASE_URL = "https://books.toscrape.com"
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"
MAX_CATALOGUE_PAGES = 3

# Stage 5 checkpoint switch: flip to True for one run to prove a broken
# page can't take the whole run down, then flip back to False. Never
# leave this on for a normal run — it deliberately breaks one URL.
INJECT_FAKE_BOOK_FOR_TESTING = False


@dataclass
class RunStats:
    """Tracks what actually happened during one run, for the final report."""

    start_time: datetime
    pages_fetched: int = 0
    cache_hits: int = 0
    failed_pages: list = field(default_factory=list)  # [{"url":..., "reason":...}]


# --- Core ---------------------------------------------------------------


class FetchError(Exception):
    """Raised when a page can't be fetched after retries (or shouldn't be retried)."""


def fetch_and_cache(url: str, cache_filename: str, stats: RunStats) -> str:
    """
    Return the HTML for `url`, reading from cache/ if we already have it.

    Politeness rules applied on every REAL request (never on a cache hit,
    since a cache hit never leaves this machine):
      - honest, identifying user-agent
      - timeout, so a hung connection can't wait forever
      - status code checked before the body is trusted

    Retry policy: a timeout, connection error, or 5xx gets ONE retry after
    a short pause — those are the failures that are plausibly transient.
    A 404 or 403 is never retried — the page doesn't exist, or the site
    said no, and asking again won't change either of those.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / cache_filename

    if cache_path.exists():
        html = cache_path.read_text(encoding="utf-8")
        stats.cache_hits += 1
        print(f"CACHE HIT  {url}  ({len(html):,} bytes)")
        return html

    last_reason = "unknown error"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
            last_reason = f"{type(error).__name__}: {error}"
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            break

        if response.status_code == 200:
            # books.toscrape.com doesn't declare a charset in its
            # Content-Type header, so requests falls back to guessing
            # Latin-1. The page is actually UTF-8 (confirmed directly),
            # so without this line every "£" comes back mangled as "Â£".
            response.encoding = "utf-8"
            cache_path.write_text(response.text, encoding="utf-8")
            stats.pages_fetched += 1
            print(f"FETCH      {url}  ({len(response.text):,} bytes)")
            time.sleep(REQUEST_DELAY_SECONDS)
            return response.text

        if response.status_code in (404, 403):
            # Not retryable, per the assignment: 404 means the page
            # doesn't exist, 403 means the site said no. Asking again
            # is either pointless or rude.
            last_reason = f"HTTP {response.status_code}"
            break

        # Anything else (5xx, etc.) is treated as possibly transient.
        last_reason = f"HTTP {response.status_code}"
        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)
            continue
        break

    stats.failed_pages.append({"url": url, "reason": last_reason})
    raise FetchError(f"GET {url} failed: {last_reason}")


def discover_book_urls(
    stats: RunStats, max_pages: int = MAX_CATALOGUE_PAGES
) -> list[tuple[str, str]]:
    """
    Walk the catalogue starting from page 1, following the site's own
    "next" link — never hardcoding page-2.html / page-3.html — and collect
    every unique, absolute book URL along the way, paired with the
    catalogue page it was found on (for provenance in Stage 3).
    """
    book_entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    page_url = CATALOGUE_URL
    pages_fetched = 0

    for page_num in range(1, max_pages + 1):
        try:
            html = fetch_and_cache(page_url, f"catalogue-page-{page_num}.html", stats)
        except FetchError:
            # A broken catalogue page means we can't find its "next" link
            # either, so pagination stops here — but whatever books we've
            # already found from earlier pages are still kept.
            break
        pages_fetched += 1
        soup = BeautifulSoup(html, "html.parser")

        # Relative links like "the-requiem-red_995/index.html" — always
        # resolved against the page they came from, never string-glued.
        for link in soup.select("article.product_pod h3 a"):
            absolute_url = urljoin(page_url, link.get("href", ""))
            if absolute_url not in seen:
                seen.add(absolute_url)
                book_entries.append((absolute_url, page_url))

        next_link = soup.select_one("li.next a")
        if next_link and page_num < max_pages:
            page_url = urljoin(page_url, next_link.get("href", ""))
        else:
            break

    if INJECT_FAKE_BOOK_FOR_TESTING:
        fake_url = f"{BASE_URL}/catalogue/this-book-does-not-exist-fake_0000/index.html"
        book_entries.append((fake_url, CATALOGUE_URL))
        print(f"[TEST] injected a deliberately broken URL: {fake_url}")

    print(
        f"catalogue_pages={pages_fetched}  "
        f"discovered={len(book_entries)}  "
        f"unique_urls={len(seen)}"
    )
    return book_entries


def extract_book_record(book_url: str, source_page: str, stats: RunStats) -> Optional[dict]:
    """
    Fetch one book's detail page (politely, via the same cache) and pull
    the eight raw fields the assignment asks for. Selectors are aimed at
    the product_main container specifically, not the whole document, so a
    second price or rating elsewhere on the page can't get picked up by
    accident. Returns None (instead of raising) if the page couldn't be
    fetched at all — one bad book shouldn't stop the other 59.
    """
    slug = book_url.rstrip("/").split("/")[-2]
    try:
        html = fetch_and_cache(book_url, f"book-{slug}.html", stats)
    except FetchError as error:
        print(f"SKIP       {book_url}  ({error})")
        return None

    soup = BeautifulSoup(html, "html.parser")

    product_main = soup.select_one("div.product_main")

    title_el = product_main.select_one("h1") if product_main else None
    title = title_el.get_text(strip=True) if title_el else None

    price_el = product_main.select_one("p.price_color") if product_main else None
    price_text = price_el.get_text(strip=True) if price_el else None

    availability_el = product_main.select_one("p.availability") if product_main else None
    # Collapses the icon/newline whitespace inside this tag down to one
    # clean string, e.g. "In stock (22 available)".
    availability_text = (
        " ".join(availability_el.get_text().split()) if availability_el else None
    )

    rating_el = product_main.select_one("p.star-rating") if product_main else None
    rating_text = None
    if rating_el:
        classes = rating_el.get("class", [])
        rating_text = next((c for c in classes if c != "star-rating"), None)

    # Not every book has a description. We store None rather than invent
    # text that was never on the page.
    description_el = soup.select_one("#product_description ~ p")
    description = description_el.get_text(strip=True) if description_el else None

    return {
        "title": title,
        "product_url": book_url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_all_records(book_entries: list[tuple[str, str]], stats: RunStats) -> list[dict]:
    records = [
        record
        for url, source in book_entries
        if (record := extract_book_record(url, source, stats)) is not None
    ]

    if records:
        print(json.dumps(records[0], indent=2, ensure_ascii=False))
    print(f"detail_pages={len(records)}")
    return records


# --- Stage 4: clean, validate, store --------------------------------------


class BookRecord(BaseModel):
    """
    The shape of one finished, trustworthy record. Anything that doesn't
    fit this shape doesn't make it into books.json.
    """

    title: str = Field(min_length=1)
    product_url: str
    price_text: str
    price_gbp: float = Field(gt=0)
    availability_text: str
    rating_text: str
    description: Optional[str] = None  # genuinely optional — some books have none
    source_page: str
    fetched_at: str

    @field_validator("product_url", "source_page")
    @classmethod
    def must_be_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(f"expected an https:// URL, got: {value!r}")
        return value


def parse_price_gbp(price_text: str) -> float:
    """'£51.77' -> 51.77. Strips everything but digits and the decimal point."""
    cleaned = re.sub(r"[^0-9.]", "", price_text or "")
    return float(cleaned)  # raises ValueError on empty/garbage input, on purpose


def clean_and_validate(raw_records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Turn raw text into a real number, check every record against the
    schema, and de-duplicate on the canonical URL. A record that fails
    either check goes to the invalid list with the reason — it never
    reaches books.json.
    """
    valid_records: list[dict] = []
    invalid_records: list[dict] = []
    seen_urls: set[str] = set()

    for raw in raw_records:
        try:
            price_gbp = parse_price_gbp(raw.get("price_text", ""))
            record = BookRecord(**raw, price_gbp=price_gbp)
        except (ValidationError, ValueError, TypeError) as error:
            invalid_records.append({"record": raw, "reason": str(error)})
            continue

        if record.product_url in seen_urls:
            continue  # same book seen twice — identity is the URL, count it once
        seen_urls.add(record.product_url)
        valid_records.append(record.model_dump())

    return valid_records, invalid_records


def store_records(valid_records: list[dict], invalid_records: list[dict]) -> None:
    """
    Overwrite books.json / errors.json with this run's full result — never
    append. That's what makes re-running the scraper idempotent: the same
    60 good records every time, not 60 more piled on top.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "books.json").write_text(
        json.dumps(valid_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "errors.json").write_text(
        json.dumps(invalid_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"valid_records={len(valid_records)}  invalid_records={len(invalid_records)}")


# --- Stage 5: report the run ------------------------------------------------


def build_and_store_run_report(
    stats: RunStats, valid_count: int, invalid_count: int
) -> dict:
    """
    A scraper that reports nothing can fail silently for weeks. This is
    the honest summary of what actually happened, written every run.
    """
    finished_at = datetime.now(timezone.utc)
    report = {
        "start_time": stats.start_time.isoformat(),
        "duration_seconds": round((finished_at - stats.start_time).total_seconds(), 2),
        "pages_fetched": stats.pages_fetched,
        "cache_hits": stats.cache_hits,
        "valid_records": valid_count,
        "invalid_records": invalid_count,
        "failed_pages": stats.failed_pages,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "run-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return report


def main() -> None:
    stats = RunStats(start_time=datetime.now(timezone.utc))
    book_entries = discover_book_urls(stats)
    raw_records = extract_all_records(book_entries, stats)
    valid_records, invalid_records = clean_and_validate(raw_records)
    store_records(valid_records, invalid_records)
    build_and_store_run_report(stats, len(valid_records), len(invalid_records))


if __name__ == "__main__":
    main()