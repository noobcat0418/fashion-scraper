"""SQLite storage: products, one row per colourway, and price history across runs."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    retailer TEXT, product_id TEXT, brand TEXT, title TEXT, handle TEXT, vendor TEXT, category TEXT,
    tags TEXT, materials TEXT, description TEXT, updated_at TEXT, first_seen TEXT, last_seen TEXT,
    score REAL, score_detail TEXT, scored_updated_at TEXT,
    PRIMARY KEY (retailer, product_id)
);
CREATE TABLE IF NOT EXISTS rows (
    retailer TEXT, product_id TEXT, colour TEXT, colour_family TEXT, price REAL, compare_at REAL,
    currency TEXT, on_sale INTEGER, in_stock INTEGER, sizes TEXT, url TEXT, image TEXT,
    first_seen TEXT, last_seen TEXT,
    PRIMARY KEY (retailer, product_id, colour)
);
CREATE TABLE IF NOT EXISTS price_history (
    retailer TEXT, product_id TEXT, colour TEXT, price REAL, seen_at TEXT
);
"""

_PRODUCT_FIELDS = ("brand", "title", "handle", "vendor", "category", "tags", "materials", "description", "updated_at")
_ROW_FIELDS = ("colour_family", "price", "compare_at", "currency", "on_sale", "in_stock", "sizes", "url", "image")


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def save(self, product: dict, rows: list[dict], seen_at: str) -> int:
        """Upsert a product and its colourways. Returns how many existing colourways changed price."""
        self.db.execute(
            f"""INSERT INTO products (retailer, product_id, {', '.join(_PRODUCT_FIELDS)}, first_seen, last_seen)
                VALUES (?, ?, {', '.join('?' * len(_PRODUCT_FIELDS))}, ?, ?)
                ON CONFLICT (retailer, product_id) DO UPDATE SET
                {', '.join(f'{f} = excluded.{f}' for f in _PRODUCT_FIELDS)}, last_seen = excluded.last_seen""",
            (product["retailer"], product["product_id"], *(product[f] for f in _PRODUCT_FIELDS), seen_at, seen_at),
        )
        changed = 0
        for row in rows:
            key = (row["retailer"], row["product_id"], row["colour"])
            prev = self.db.execute(
                "SELECT price FROM rows WHERE retailer = ? AND product_id = ? AND colour = ?", key
            ).fetchone()
            self.db.execute(
                f"""INSERT INTO rows (retailer, product_id, colour, {', '.join(_ROW_FIELDS)}, first_seen, last_seen)
                    VALUES (?, ?, ?, {', '.join('?' * len(_ROW_FIELDS))}, ?, ?)
                    ON CONFLICT (retailer, product_id, colour) DO UPDATE SET
                    {', '.join(f'{f} = excluded.{f}' for f in _ROW_FIELDS)}, last_seen = excluded.last_seen""",
                (*key, *(row[f] for f in _ROW_FIELDS), seen_at, seen_at),
            )
            # History gets a row the first time a colourway is seen and whenever its price moves.
            if prev is None or prev["price"] != row["price"]:
                self.db.execute("INSERT INTO price_history VALUES (?, ?, ?, ?, ?)", (*key, row["price"], seen_at))
                changed += prev is not None
        self.db.commit()
        return changed

    def board_rows(self) -> list[dict]:
        """Colourways listed in each retailer's latest scrape, with the previous price if it changed."""
        cur = self.db.execute(
            """
            SELECT r.*, p.brand, p.title, p.category, p.materials, p.score, p.score_detail,
                   (SELECT h.price FROM price_history h
                     WHERE h.retailer = r.retailer AND h.product_id = r.product_id AND h.colour = r.colour
                     ORDER BY h.rowid DESC LIMIT 1 OFFSET 1) AS prev_price
            FROM rows r JOIN products p USING (retailer, product_id)
            WHERE r.last_seen = (SELECT MAX(last_seen) FROM rows r2 WHERE r2.retailer = r.retailer)
            """
        )
        out = []
        for row in cur:
            d = dict(row)
            d["on_sale"], d["in_stock"] = bool(d["on_sale"]), bool(d["in_stock"])
            out.append(d)
        return out
