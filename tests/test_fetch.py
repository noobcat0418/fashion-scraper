import json as _json

import pytest

from scraper.robots import Robots
from scraper.shopify import Blocked, Fetcher, fetch_products
from tests.fixtures import RETAILER


class Resp:
    def __init__(self, status=200, json=None, text="", headers=None):
        self.status_code, self._json, self.headers = status, json, headers or {}
        self.text = text or (_json.dumps(json) if json is not None else "")
        self.ok = status < 400

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, headers, timeout):
        self.calls.append(url)
        return self.routes[url.split("shop.example", 1)[1]]


class Clock:
    def __init__(self):
        self.now, self.slept = 0.0, []

    def __call__(self):
        return self.now

    def sleep(self, s):
        self.slept.append(s)
        self.now += s


def fetcher_for(routes):
    clock = Clock()
    return Fetcher(session=FakeSession(routes), sleep=clock.sleep, clock=clock, log=lambda *_: None), clock


def page(n):
    return Resp(json={"products": [{"id": i} for i in range(n)]})


def test_paginates_until_short_page_and_spaces_requests():
    f, clock = fetcher_for({
        "/robots.txt": Resp(text="User-agent: *\nDisallow: /cart"),
        "/products.json?limit=250&page=1": page(250),
        "/products.json?limit=250&page=2": page(3),
    })
    assert len(list(fetch_products(f, RETAILER, max_pages=5))) == 253
    assert len(f.session.calls) == 3
    assert clock.slept and all(s >= 1.5 - 1e-9 for s in clock.slept)


def test_page_cap():
    f, _ = fetcher_for({"/robots.txt": Resp(status=404), "/products.json?limit=250&page=1": page(250)})
    assert len(list(fetch_products(f, RETAILER, max_pages=1))) == 250


def test_robots_wildcard_blocks_feed():
    f, _ = fetcher_for({"/robots.txt": Resp(text="User-agent: *\nDisallow: /*.json")})
    with pytest.raises(Blocked):
        list(fetch_products(f, RETAILER, max_pages=1))


def test_forbidden_robots_means_stay_away():
    f, _ = fetcher_for({"/robots.txt": Resp(status=403)})
    with pytest.raises(Blocked, match="403"):
        list(fetch_products(f, RETAILER, max_pages=1))


def test_crawl_delay_raises_spacing():
    f, clock = fetcher_for({
        "/robots.txt": Resp(text="User-agent: *\nCrawl-delay: 5"),
        "/products.json?limit=250&page=1": page(2),
    })
    list(fetch_products(f, RETAILER, max_pages=1))
    assert f.min_delay == 5.0 and clock.slept == [5.0]


def test_robots_longest_match_and_specific_agent():
    text = "User-agent: *\nDisallow: /\n\nUser-agent: fashion-scraper\nDisallow: /private\nAllow: /private/ok$\n"
    r = Robots(text, "fashion-scraper/0.1 (+https://github.com/x)")
    assert r.allowed("/products.json?limit=250")  # our own group, not the catch-all
    assert not r.allowed("/private/x")
    assert r.allowed("/private/ok") and not r.allowed("/private/ok/more")


def test_cache_serves_repeat_requests_without_network(tmp_path):
    f, _ = fetcher_for({"/products.json?limit=1": page(1), "/missing": Resp(status=404)})
    f.cache_dir = tmp_path
    assert f.get("https://shop.example/products.json?limit=1").json() == {"products": [{"id": 0}]}
    assert f.get("https://shop.example/products.json?limit=1").json() == {"products": [{"id": 0}]}
    f.get("https://shop.example/missing")
    f.get("https://shop.example/missing")  # errors are never cached
    assert f.network_requests == 3


def test_long_ban_is_not_waited_out():
    f, clock = fetcher_for({"/x": Resp(status=429, headers={"Retry-After": "3600"})})
    assert f.get("https://shop.example/x").status_code == 429
    assert clock.slept == [] and f.network_requests == 1


def test_429_waits_then_retries_once():
    responses = iter([Resp(status=429, headers={"Retry-After": "7"}), page(1)])
    f, clock = fetcher_for({})
    f.session.get = lambda url, headers, timeout: next(responses)
    assert f.get("https://shop.example/x").status_code == 200
    assert 7.0 in clock.slept
