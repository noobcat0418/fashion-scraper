# fashion-scraper

Turns public Shopify product feeds from menswear brands into a clean, filterable shopping board.
Each product becomes **one row per colourway**, with price, sale status, sizes in stock, materials and a colour family.
Price history is kept across runs, so price drops show up on the board.

Stack: Python, SQLite, a single static HTML page. No server, no paid services.

```
retailers.json ─▶ robots.txt check ─▶ /products.json (paged, 5 s apart, 6 h cache)
               ─▶ normalise (colourways, prices, colour families, materials)
               ─▶ SQLite (products, colourways, price history)
               ─▶ out/board.html + out/products.csv
```

## Use

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

.\.venv\Scripts\python fashion.py check                                   # robots.txt + feed reachable
.\.venv\Scripts\python fashion.py run --retailer taylorstitch --max-pages 1
start out\board.html
```

| Command | What it does |
|---|---|
| `check` | For each retailer: does robots.txt allow the feed, and does it answer? |
| `scrape` | Download, normalise and store. `--max-pages N` (250 products per page), `--retailer KEY` |
| `board` | Write `out/board.html` and `out/products.csv` from the database |
| `run` | `scrape`, then `board` |

Add a store by appending to `retailers.json` (`key`, `name`, `domain`, `currency`, optional `include`/`exclude` keywords,
matched as whole words so `men` never matches `women`).

## Being a good citizen

- **Public data only:** the standard Shopify `/products.json` feed. No login, cookies or checkout pages.
- **robots.txt is checked before every fetch.** The parser supports `*` and `$` wildcards; Python's built-in one doesn't,
  and would read `Disallow: /*.json` as "allowed". A 401/403 on robots.txt means the store is skipped.
- **5 seconds between requests,** or longer if the site sets `Crawl-delay`. The user agent names this repo.
- **A 6-hour page cache,** so re-runs while developing cost the store nothing. `--fresh` bypasses it.
- **"Slow down" is respected:** on a 429 it waits once (up to 60 s), then stops rather than retrying.
  It never rotates IPs or disguises itself.
- **Scraped data stays local** (`out/` and `*.db` are gitignored).

Some large retailers block automated access outright (COS returns 403 even for robots.txt), so they are not supported.

## How colourways are built

Shopify variants are usually per size. They're grouped by the `Color`/`Colour` option when there is one.
Otherwise the colour is taken from the title (`"… - Black"`, `"… in Khaki Waxed Ripstop"`).
A vocabulary maps brand colour names to families (Spruce → green, Claret → red, Coal → black).
Unrecognised names fall back to `other`.

## Tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

The tests use synthetic, Shopify-shaped fixtures and fake HTTP, so they need no network and include no real brand data.
They cover pagination, request spacing, robots wildcards, 429 handling, the cache, colourway grouping, colour families,
materials, upserts, price history and HTML escaping on the board.
