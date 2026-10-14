import csv

from scraper.board import render, write_csv
from scraper.normalize import product_record, rows
from scraper.store import Store
from tests.fixtures import RETAILER, WITH_COLOUR_OPTION


def save(store, product, seen_at, price_override=None):
    product_rows = rows(product, RETAILER)
    if price_override is not None:
        for r in product_rows:
            r["price"] = price_override
    return store.save(product_record(product, RETAILER), product_rows, seen_at)


def test_rerun_does_not_duplicate_and_tracks_price_drops(tmp_path):
    store = Store(tmp_path / "t.db")
    assert save(store, WITH_COLOUR_OPTION, "2026-10-01T08:00:00") == 0
    assert save(store, WITH_COLOUR_OPTION, "2026-10-02T08:00:00") == 0  # same prices: no history rows
    assert store.db.execute("SELECT COUNT(*) FROM rows").fetchone()[0] == 2
    assert store.db.execute("SELECT COUNT(*) FROM price_history").fetchone()[0] == 2

    assert save(store, WITH_COLOUR_OPTION, "2026-10-03T08:00:00", price_override=25.0) == 2
    board = {r["colour"]: r for r in store.board_rows()}
    assert board["Navy"]["price"] == 25.0 and board["Navy"]["prev_price"] == 40.0


def test_board_only_shows_latest_scrape(tmp_path):
    store = Store(tmp_path / "t.db")
    save(store, WITH_COLOUR_OPTION, "2026-10-01T08:00:00")
    other = dict(WITH_COLOUR_OPTION, id=99)
    save(store, other, "2026-10-02T08:00:00")  # product 1 was not listed in this newer scrape
    assert {r["product_id"] for r in store.board_rows()} == {"99"}


def test_board_escapes_script_in_titles(tmp_path):
    store = Store(tmp_path / "t.db")
    save(store, dict(WITH_COLOUR_OPTION, title="Tee </script><script>alert(1)</script>"), "2026-10-01T08:00:00")
    html = render(store.board_rows(), "2026-10-01 08:00")
    assert html.count("</script>") == 2  # only the page's own two script tags
    assert "Fashion Board" in html


def test_csv_has_header_and_rows(tmp_path):
    store = Store(tmp_path / "t.db")
    save(store, WITH_COLOUR_OPTION, "2026-10-01T08:00:00")
    path = tmp_path / "p.csv"
    write_csv(store.board_rows(), path)
    with open(path, encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 2 and data[0]["brand"] == "Demo Co" and data[0]["url"].startswith("https://shop.example/")
