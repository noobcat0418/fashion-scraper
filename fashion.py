"""Fashion scraper: public Shopify product feeds -> one row per colourway -> SQLite, CSV and a static board.

  python fashion.py check                              robots.txt + feed reachable for each retailer
  python fashion.py scrape [--retailer KEY] [--max-pages N]
  python fashion.py score [--max N]                    rate new/changed products 1-10 with the local model
  python fashion.py board                              write out/board.html and out/products.csv
  python fashion.py run [--retailer KEY] [--max-pages N] [--max N] [--no-score]   scrape, score, board
"""
import argparse
import sys
import time
from datetime import datetime

import requests

from scraper import board, config, normalize, score
from scraper.shopify import PAGE_SIZE, Blocked, Fetcher, fetch_products, load_robots
from scraper.store import Store


def pick(retailers: list, key: str | None) -> list:
    if not key:
        return retailers
    chosen = [r for r in retailers if r["key"] == key]
    if not chosen:
        sys.exit(f"Unknown retailer {key!r}. Known: {', '.join(r['key'] for r in retailers)}")
    return chosen


def cmd_check(args, cfg, store) -> int:
    fetcher, ok = make_fetcher(args, cfg), True
    for r in pick(cfg.retailers, args.retailer):
        robots = load_robots(fetcher, r["domain"])
        path = "/products.json?limit=1"
        if robots.blocked_everything or not robots.allowed(path):
            print(f"{r['name']}: BLOCKED by robots.txt ({robots.blocked_everything or path})")
            ok = False
            continue
        resp = fetcher.get(f"https://{r['domain']}{path}")
        n = len(resp.json().get("products", [])) if resp.ok else 0
        print(f"{r['name']}: robots.txt allows the feed, feed HTTP {resp.status_code}, {n} product(s) on a 1-item page")
        ok = ok and resp.ok and n > 0
    return 0 if ok else 1


def make_fetcher(args, cfg) -> Fetcher:
    return Fetcher(cache_dir=None if args.fresh else cfg.out_dir / "cache")


def cmd_scrape(args, cfg, store) -> int:
    fetcher, failures = make_fetcher(args, cfg), 0
    for r in pick(cfg.retailers, args.retailer):
        seen_at = datetime.now().isoformat(timespec="seconds")
        print(f"{r['name']} ({r['domain']})")
        kept = filtered = colourways = changes = 0
        try:
            for product in fetch_products(fetcher, r, args.max_pages):
                if not normalize.keep(product, r):
                    filtered += 1
                    continue
                product_rows = normalize.rows(product, r)
                if not product_rows:
                    continue
                changes += store.save(normalize.product_record(product, r), product_rows, seen_at)
                kept += 1
                colourways += len(product_rows)
        except Blocked as e:
            print(f"  skipped: {e}")
            failures += 1
            continue
        except requests.RequestException as e:
            print(f"  stopped: {type(e).__name__}: {e}")
            failures += 1
        print(f"  {kept} products -> {colourways} colourways, {filtered} filtered out, {changes} price change(s)")
    print(f"Network requests this run: {fetcher.network_requests} (the rest came from the 6-hour cache)")
    return 1 if failures else 0


def cmd_board(args, cfg, store) -> int:
    rows = store.board_rows()
    cfg.out_dir.mkdir(exist_ok=True)
    html_path, csv_path = cfg.out_dir / "board.html", cfg.out_dir / "products.csv"
    html_path.write_text(board.render(rows, datetime.now().strftime("%Y-%m-%d %H:%M")), encoding="utf-8")
    board.write_csv(rows, csv_path)
    print(f"Board: {html_path} ({len(rows)} colourways)\nCSV:   {csv_path}")
    return 0


def cmd_score(args, cfg, store) -> int:
    from scraper.llm import LLM

    weights = cfg.scoring["weights"]
    if set(weights) != set(cfg.scoring["criteria"]):
        sys.exit("scoring.json: 'weights' and 'criteria' must list the same names")
    redone = store.rescore(lambda d: score.weighted(d, weights))
    if redone:
        print(f"Re-weighted {redone} already-scored product(s) with the current scoring.json")

    todo = store.to_score(args.max)
    if not todo:
        print("Nothing new to score.")
        return 0
    llm = LLM(cfg)
    try:
        warning = llm.check()
    except Exception as e:
        print(f"Model not reachable at {cfg.llm_base_url} ({type(e).__name__}). Is Ollama running?")
        return 2
    if warning:
        print(warning)
        return 2

    print(f"Scoring {len(todo)} product(s) with {llm.model} (--max {args.max})")
    failed = 0
    try:
        for i, p in enumerate(todo, 1):
            start = time.time()
            detail, error = score.score_product(llm, p, cfg.scoring)
            if detail is None:
                failed += 1
                print(f"  [{i:>3}/{len(todo)}] FAILED {p['title'][:50]} - {error}")
                continue  # left unscored, so the next run tries again
            total = score.weighted(detail, weights)
            store.save_score(p["retailer"], p["product_id"], detail, total, p["updated_at"])
            print(f"  [{i:>3}/{len(todo)}] {total:4.1f}  {time.time() - start:4.1f}s  {p['title'][:60]}")
    except KeyboardInterrupt:
        print("\nStopped. Scores so far are saved; run again to continue.")
    print(f"Scored {len(todo) - failed}, failed {failed}. Model: {llm.model} via {cfg.llm_base_url}")
    return 1 if failed else 0


def cmd_run(args, cfg, store) -> int:
    status = cmd_scrape(args, cfg, store)
    if not args.no_score:
        status = cmd_score(args, cfg, store) or status
    cmd_board(args, cfg, store)
    return status


def main(argv=None) -> int:
    sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("check", "scrape", "score", "board", "run"):
        p = sub.add_parser(name)
        p.add_argument("--max", type=int, default=20, help="most products to score this run (default 20)")
        p.add_argument("--no-score", action="store_true", help="run: skip AI scoring")
        p.add_argument("--retailer", help="only this retailer key from retailers.json")
        p.add_argument("--max-pages", type=int, default=4, help=f"pages of {PAGE_SIZE} products per retailer (default 4)")
        p.add_argument("--fresh", action="store_true", help="ignore the 6-hour page cache and ask the sites again")
    args = ap.parse_args(argv)

    cfg = config.load()
    store = Store(cfg.db_file)
    commands = {"check": cmd_check, "scrape": cmd_scrape, "score": cmd_score, "board": cmd_board, "run": cmd_run}
    return commands[args.command](args, cfg, store)


if __name__ == "__main__":
    sys.exit(main())
