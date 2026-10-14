"""Polite reader for Shopify's public /products.json feed.

Public JSON only: no login, no cookies, no attempt to get past bot protection.
robots.txt is checked first, and requests are spaced out.
"""
import hashlib
import json
import time
from pathlib import Path

import requests

from .robots import Robots

USER_AGENT = "fashion-scraper/0.1 (+https://github.com/noobcat0418/fashion-scraper)"
PAGE_SIZE = 250
MIN_DELAY = 5.0  # seconds between requests to the same site
CACHE_TTL = 6 * 3600  # re-use a downloaded page for 6 hours, so re-runs while developing cost no requests
MAX_BACKOFF = 60  # longest we'll wait when a site asks us to slow down


class Blocked(Exception):
    """The site's robots.txt (or a 401/403 on it) says not to fetch the feed."""


class CachedResponse:
    """A saved 200 response, read back from disk instead of asking the site again."""

    status_code, ok, headers = 200, True, {}

    def __init__(self, text: str):
        self.text = text

    def json(self):
        return json.loads(self.text)

    def raise_for_status(self):
        pass


class Fetcher:
    def __init__(self, session=None, min_delay=MIN_DELAY, sleep=time.sleep, clock=time.monotonic, log=print,
                 cache_dir=None, cache_ttl=CACHE_TTL):
        self.session = session or requests.Session()
        self.min_delay, self.sleep, self.clock, self.log = min_delay, sleep, clock, log
        self.cache_dir, self.cache_ttl = (Path(cache_dir) if cache_dir else None), cache_ttl
        self._last = None
        self.network_requests = 0

    def get(self, url: str):
        cache_file = self._cache_file(url)
        if cache_file and cache_file.exists() and time.time() - cache_file.stat().st_mtime < self.cache_ttl:
            return CachedResponse(cache_file.read_text(encoding="utf-8"))
        resp = self._polite_get(url)
        if cache_file and resp.status_code == 200:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(resp.text, encoding="utf-8")
        return resp

    def _cache_file(self, url: str):
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".txt")

    def _polite_get(self, url: str):
        if self._last is not None:
            wait = self.min_delay - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        resp = self._send(url)
        if resp.status_code in (429, 503):  # asked to slow down: wait once, then give up
            retry_after = resp.headers.get("Retry-After", "")
            pause = float(retry_after) if retry_after.isdigit() else 30.0
            if pause > MAX_BACKOFF:  # a long ban: stop rather than hang the run
                return resp
            self.log(f"  {resp.status_code} from {url}, waiting {pause:.0f}s")
            self.sleep(pause)
            resp = self._send(url)
        return resp

    def _send(self, url: str):
        resp = self.session.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=30)
        self._last = self.clock()
        self.network_requests += 1
        return resp


def load_robots(fetcher: Fetcher, domain: str) -> Robots:
    resp = fetcher.get(f"https://{domain}/robots.txt")
    if resp.status_code in (401, 403):
        return Robots.disallow_all(f"robots.txt returned {resp.status_code}")
    if resp.status_code >= 500:
        return Robots.disallow_all(f"robots.txt returned {resp.status_code}; trying later is kinder")
    if resp.status_code >= 400:  # no robots.txt: no rules
        return Robots("", USER_AGENT)
    return Robots(resp.text, USER_AGENT)


def fetch_products(fetcher: Fetcher, retailer: dict, max_pages: int):
    """Yield raw Shopify products, page by page, stopping at an empty or short page."""
    domain = retailer["domain"]
    robots = load_robots(fetcher, domain)
    if robots.blocked_everything:
        raise Blocked(robots.blocked_everything)
    if robots.crawl_delay:
        fetcher.min_delay = max(fetcher.min_delay, robots.crawl_delay)

    for page in range(1, max_pages + 1):
        path = f"/products.json?limit={PAGE_SIZE}&page={page}"
        if not robots.allowed(path):
            raise Blocked(f"robots.txt disallows {path}")
        resp = fetcher.get(f"https://{domain}{path}")
        resp.raise_for_status()
        products = resp.json().get("products") or []
        fetcher.log(f"  page {page}: {len(products)} products")
        yield from products
        if len(products) < PAGE_SIZE:
            return
