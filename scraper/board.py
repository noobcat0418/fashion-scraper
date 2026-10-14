"""Output: a single static HTML board (no server, no build step) and a CSV."""
import csv
import json

from .normalize import FAMILY_HEX

CSV_COLUMNS = ["brand", "title", "category", "colour", "colour_family", "price", "compare_at", "currency",
               "on_sale", "in_stock", "prev_price", "score", "materials", "sizes", "url", "image"]
_BOARD_FIELDS = CSV_COLUMNS + ["first_seen", "score_reason"]


def _prepare(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        d = {k: r.get(k) for k in _BOARD_FIELDS}
        detail = r.get("score_detail")
        if detail:
            try:
                d["score_reason"] = json.loads(detail).get("reason", "")
            except ValueError:
                pass
        out.append(d)
    return out


def render(rows: list[dict], generated: str) -> str:
    data = {"rows": _prepare(rows), "generated": generated, "familyHex": FAMILY_HEX}
    # "</" can't appear inside a <script> block, or a product title could end it early.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", payload)


def write_csv(rows: list[dict], path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fashion Board</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e3e3e0;--accent:#2f4a7a;--sale:#b42318;--good:#1f7a4d}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1e1e21;--ink:#ececee;--muted:#a1a1a8;--line:#2e2e33;--accent:#8fb0ff;--sale:#ff7a6b;--good:#5fd39a}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink)}
header{padding:16px;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:1}
h1{font-size:18px;margin:0 0 2px}
.sub{color:var(--muted);font-size:12px;margin-bottom:10px}
.filters{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.filters input,.filters select{font:inherit;padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink)}
.filters label{display:inline-flex;gap:4px;align-items:center;color:var(--muted)}
main{padding:16px;display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:4/5;object-fit:cover;background:var(--line);display:block}
.body{padding:10px;display:flex;flex-direction:column;gap:4px;flex:1}
.brand{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.title{font-weight:600}
.colour{display:flex;gap:6px;align-items:center;color:var(--muted)}
.dot{width:10px;height:10px;border-radius:50%;border:1px solid var(--line);flex:none}
.price{font-weight:600}
.was{text-decoration:line-through;color:var(--muted);font-weight:400;margin-left:6px}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.badge{font-size:11px;padding:2px 7px;border-radius:999px;border:1px solid var(--line)}
.badge.sale{color:var(--sale);border-color:var(--sale)}
.badge.drop{color:var(--good);border-color:var(--good)}
.badge.score{color:var(--accent);border-color:var(--accent)}
.meta{font-size:12px;color:var(--muted)}
a.view{margin-top:auto;padding-top:6px;color:var(--accent);text-decoration:none;font-weight:600}
.empty{padding:40px;color:var(--muted)}
@media (max-width:480px){header{padding:12px 16px}main{grid-template-columns:repeat(2,1fr);gap:10px;padding:12px 16px}.filters input[type=search]{flex:1 1 100%}}
</style>
</head>
<body>
<header>
  <h1>Fashion Board</h1>
  <div class="sub" id="sub"></div>
  <div class="filters">
    <input id="q" type="search" placeholder="Search title or material">
    <select id="brand"><option value="">All brands</option></select>
    <select id="category"><option value="">All categories</option></select>
    <select id="family"><option value="">All colours</option></select>
    <input id="maxPrice" type="number" min="0" placeholder="Max price" style="width:110px">
    <select id="minScore"><option value="">Any score</option><option>5</option><option>6</option><option>7</option><option>8</option></select>
    <label><input id="sale" type="checkbox"> On sale</label>
    <label><input id="drop" type="checkbox"> Price drops</label>
    <label><input id="stock" type="checkbox" checked> In stock</label>
    <select id="sort">
      <option value="score">Best score</option><option value="price">Lowest price</option>
      <option value="priceDesc">Highest price</option><option value="new">Newest</option>
    </select>
  </div>
</header>
<main id="grid"></main>
<script type="application/json" id="data">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const rows = DATA.rows, $ = id => document.getElementById(id);
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function fill(id, values) {
  [...new Set(values.filter(Boolean))].sort().forEach(v => { const o = el('option', null, v); o.value = v; $(id).appendChild(o); });
}
fill('brand', rows.map(r => r.brand)); fill('category', rows.map(r => r.category)); fill('family', rows.map(r => r.colour_family));
function money(v, c) { try { return new Intl.NumberFormat(undefined, {style: 'currency', currency: c || 'USD'}).format(v); } catch (e) { return v + ' ' + c; } }
const dropped = r => r.prev_price != null && r.prev_price > r.price;
function card(r) {
  const c = el('article', 'card'), b = el('div', 'body');
  const img = el('img'); img.loading = 'lazy'; img.alt = r.title || ''; if (r.image) img.src = r.image; c.appendChild(img);
  b.appendChild(el('div', 'brand', r.brand)); b.appendChild(el('div', 'title', r.title));
  const col = el('div', 'colour'), dot = el('span', 'dot');
  dot.style.background = DATA.familyHex[r.colour_family] || '#ccc';
  col.appendChild(dot); col.appendChild(document.createTextNode(r.colour || r.colour_family)); b.appendChild(col);
  const p = el('div', 'price', money(r.price, r.currency));
  if (r.on_sale && r.compare_at) p.appendChild(el('span', 'was', money(r.compare_at, r.currency)));
  b.appendChild(p);
  const badges = el('div', 'badges');
  if (r.score != null) badges.appendChild(el('span', 'badge score', 'Score ' + Number(r.score).toFixed(1)));
  if (r.on_sale) badges.appendChild(el('span', 'badge sale', 'Sale'));
  if (dropped(r)) badges.appendChild(el('span', 'badge drop', 'Was ' + money(r.prev_price, r.currency)));
  if (!r.in_stock) badges.appendChild(el('span', 'badge', 'Sold out'));
  b.appendChild(badges);
  if (r.materials) b.appendChild(el('div', 'meta', r.materials));
  if (r.sizes) b.appendChild(el('div', 'meta', 'Sizes: ' + r.sizes));
  if (r.score_reason) b.appendChild(el('div', 'meta', r.score_reason));
  const a = el('a', 'view', 'View \\u2192'); a.href = r.url; a.target = '_blank'; a.rel = 'noopener'; b.appendChild(a);
  c.appendChild(b); return c;
}
function render() {
  const q = $('q').value.trim().toLowerCase(), brand = $('brand').value, cat = $('category').value, fam = $('family').value;
  const maxP = parseFloat($('maxPrice').value), minS = parseFloat($('minScore').value);
  const list = rows.filter(r =>
    (!q || ((r.title || '') + ' ' + (r.materials || '')).toLowerCase().includes(q)) &&
    (!brand || r.brand === brand) && (!cat || r.category === cat) && (!fam || r.colour_family === fam) &&
    (isNaN(maxP) || r.price <= maxP) && (isNaN(minS) || (r.score != null && r.score >= minS)) &&
    (!$('sale').checked || r.on_sale) && (!$('drop').checked || dropped(r)) && (!$('stock').checked || r.in_stock));
  const sorts = {
    score: (a, b) => ((b.score ?? -1) - (a.score ?? -1)) || a.price - b.price,
    price: (a, b) => a.price - b.price,
    priceDesc: (a, b) => b.price - a.price,
    new: (a, b) => (b.first_seen || '').localeCompare(a.first_seen || ''),
  };
  list.sort(sorts[$('sort').value]);
  $('grid').replaceChildren(...list.map(card));
  if (!list.length) $('grid').appendChild(el('div', 'empty', 'No products match these filters.'));
  $('sub').textContent = list.length + ' of ' + rows.length + ' colourways \\u00b7 updated ' + DATA.generated;
}
document.querySelectorAll('.filters input, .filters select').forEach(e => e.addEventListener('input', render));
render();
</script>
</body>
</html>
"""
