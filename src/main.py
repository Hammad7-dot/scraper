"""
The Polite Scraper — Books to Scrape
FlyRank Internship, Backend Track, Week 5, A9

Stage 1: fetch once, cache once.
"""

import time
from pathlib import Path

import requests

# --- Config -----------------------------------------------------------------

# TODO: once this is pushed, replace the placeholder link below with the
# real repo URL, e.g. "https://github.com/Hammad7-dot/scraper" — a site
# owner who sees this in their access logs should be able to find out who's
# requesting their pages and why.
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/Hammad7-dot/scraper)"

REQUEST_TIMEOUT_SECONDS = 10
REQUEST_DELAY_SECONDS = 0.5  # only applied between REAL requests, never on cache hits

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"

BASE_URL = "Remove-Item -Recurse -Force .git "
CATALOGUE_URL = f"{BASE_URL}/catalogue/page-1.html"


# --- Core ---------------------------------------------------------------


class FetchError(Exception):
    """Raised when a page can't be fetched and isn't a 200."""


def fetch_and_cache(url: str, cache_filename: str) -> str:
    """
    Return the HTML for `url`, reading from cache/ if we already have it.

    Politeness rules applied on every REAL request (never on a cache hit,
    since a cache hit never leaves this machine):
      - honest, identifying user-agent
      - timeout, so a hung connection can't wait forever
      - status code checked before the body is trusted
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / cache_filename

    if cache_path.exists():
        html = cache_path.read_text(encoding="utf-8")
        print(f"CACHE HIT  {url}  ({len(html):,} bytes)")
        return html

    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    if response.status_code != 200:
        # Stage 1 keeps this simple and loud. Stage 5 replaces this with
        # per-page handling so one bad page doesn't take the whole run down.
        raise FetchError(f"GET {url} returned {response.status_code}, expected 200")

    cache_path.write_text(response.text, encoding="utf-8")
    print(f"FETCH      {url}  ({len(response.text):,} bytes)")

    time.sleep(REQUEST_DELAY_SECONDS)
    return response.text


def main() -> None:
    fetch_and_cache(CATALOGUE_URL, "catalogue-page-1.html")


if __name__ == "__main__":
    main()
