"""Turn one raw Shopify product into one row per colourway, with prices, sizes and colour family."""
import html
import re

COLOUR_OPTION_NAMES = {"color", "colour", "colors", "colours"}

# Family -> words that brands use for it. First match, reading the colour name left to right, wins.
FAMILY_WORDS = {
    "black": "black jet onyx ink noir coal raven obsidian",
    "white": "white ivory ecru chalk snow cream milk pearl",
    "grey": "grey gray greyscale charcoal heather slate ash silver smoke graphite pewter fog steel mist",
    "blue": "blue navy indigo denim cobalt sky royal azure chambray marine ocean teal harbor midnight atlantic sea nocturne",
    "green": "green olive sage forest moss mint emerald pine army fern seaweed spruce leaf juniper cypress hunter lichen",
    "brown": "brown chocolate coffee espresso tobacco cognac walnut mocha chestnut umber bark saddle timber "
             "soil sable earth peat hickory mahogany",
    "beige": "beige tan khaki sand stone oatmeal camel natural bone taupe wheat fawn putty biscuit oat dune desert driftwood",
    "red": "red burgundy maroon wine crimson brick cherry oxblood cardinal claret garnet",
    "pink": "pink rose blush salmon fuchsia",
    "purple": "purple plum lilac lavender mauve violet eggplant aubergine",
    "yellow": "yellow mustard gold lemon butter ochre saffron goldfinch honey",
    "orange": "orange rust coral tangerine amber terracotta copper ember canyon clay",
    "multi": "multi multicolor multicolour print stripe striped plaid check camo floral houndstooth herringbone glen tartan",
}
WORD_TO_FAMILY = {w: fam for fam, words in FAMILY_WORDS.items() for w in words.split()}
FAMILY_HEX = {
    "black": "#111111", "white": "#f4f4f0", "grey": "#9a9a9a", "blue": "#2f5aa8", "green": "#5c7a3a",
    "brown": "#6b4423", "beige": "#d6c3a0", "red": "#b3261e", "pink": "#e8a0b4", "purple": "#7b4fa0",
    "yellow": "#e6c229", "orange": "#e07b2a", "multi": "linear-gradient(135deg,#e07b2a,#2f5aa8)", "other": "#cccccc",
}
MATERIALS = "organic cotton|recycled polyester|merino wool|cotton|linen|hemp|wool|merino|cashmere|silk|leather|suede|denim|nylon|polyester|elastane|spandex|lyocell|tencel|modal|alpaca|mohair|canvas"
_PERCENT_MATERIAL = re.compile(rf"(\d{{1,3}})\s*%\s*(?:recycled |organic |regenerative )?({MATERIALS})", re.I)
_ANY_MATERIAL = re.compile(rf"\b({MATERIALS})\b", re.I)


def colour_family(name: str | None) -> str:
    for word in re.findall(r"[a-z]+", (name or "").lower()):
        if word in WORD_TO_FAMILY:
            return WORD_TO_FAMILY[word]
    return "other"


def colour_from_title(title: str) -> str | None:
    """'Pocket Tee - Black' -> 'Black'; 'The Down Vest in Khaki Waxed Ripstop' -> 'Khaki Waxed Ripstop'."""
    if " - " in title:
        return title.rsplit(" - ", 1)[1].strip()
    match = re.search(r"\bin ([A-Z][\w'/ -]+)$", title)
    if match:
        return match.group(1).strip()
    for word in reversed(re.findall(r"[A-Za-z]+", title)):
        if word.lower() in WORD_TO_FAMILY:
            return word.title()
    return None


def materials(body_html: str | None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", body_html or ""))
    found = [f"{pct}% {mat.lower()}" for pct, mat in _PERCENT_MATERIAL.findall(text)]
    if not found:
        found = list(dict.fromkeys(m.lower() for m in _ANY_MATERIAL.findall(text)))
    return ", ".join(dict.fromkeys(found[:4]))


def tags(product: dict) -> list[str]:
    raw = product.get("tags") or []
    return [t.strip() for t in (raw.split(",") if isinstance(raw, str) else raw) if t.strip()]


def keep(product: dict, retailer: dict) -> bool:
    """Apply the retailer's include/exclude keywords as whole words (so 'men' never matches 'women')."""
    text = " ".join([product.get("title", ""), product.get("product_type", ""), *tags(product)]).lower()

    def hit(word):
        return re.search(rf"\b{re.escape(word.lower())}\b", text) is not None

    include, exclude = retailer.get("include") or [], retailer.get("exclude") or []
    if include and not any(hit(w) for w in include):
        return False
    return not any(hit(w) for w in exclude)


def product_record(product: dict, retailer: dict) -> dict:
    return {
        "retailer": retailer["key"],
        "brand": retailer["name"],
        "product_id": str(product["id"]),
        "title": product.get("title", "").strip(),
        "handle": product.get("handle", ""),
        "vendor": product.get("vendor", ""),
        "category": (product.get("product_type") or "").strip() or "Uncategorised",
        "tags": ", ".join(tags(product)),
        "materials": materials(product.get("body_html")),
        "description": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", product.get("body_html") or ""))).strip()[:600],
        "updated_at": product.get("updated_at", ""),
    }


def _money(value) -> float | None:
    try:
        return round(float(value), 2) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def rows(product: dict, retailer: dict) -> list[dict]:
    """One row per colourway. Variants are usually per size, so they're grouped by colour."""
    variants = product.get("variants") or []
    if not variants:
        return []
    options = product.get("options") or []
    colour_index = next(
        (i for i, o in enumerate(options) if str(o.get("name", "")).strip().lower() in COLOUR_OPTION_NAMES), None
    )

    groups: dict[str, list] = {}
    if colour_index is not None:
        for v in variants:
            groups.setdefault((v.get(f"option{colour_index + 1}") or "").strip(), []).append(v)
    else:
        groups[colour_from_title(product.get("title", "")) or ""] = variants

    images = product.get("images") or []
    out = []
    for colour, group in groups.items():
        available = [v for v in group if v.get("available", True)]
        priced = [(p, v) for v in (available or group) if (p := _money(v.get("price"))) is not None]
        if not priced:
            continue
        price, cheapest = min(priced, key=lambda pv: pv[0])
        compare = _money(cheapest.get("compare_at_price"))
        sizes = []
        for v in available:
            label = " / ".join(
                str(v.get(f"option{i + 1}"))
                for i in range(len(options))
                if i != colour_index and v.get(f"option{i + 1}") not in (None, "", "Default Title")
            )
            if label and label not in sizes:
                sizes.append(label)
        out.append({
            "retailer": retailer["key"],
            "product_id": str(product["id"]),
            "colour": colour or "",
            "colour_family": colour_family(colour) if colour else "other",
            "price": price,
            "compare_at": compare if compare and compare > price else None,
            "currency": retailer.get("currency", "USD"),
            "on_sale": bool(compare and compare > price),
            "in_stock": bool(available),
            "sizes": ", ".join(sizes),
            "url": f"https://{retailer['domain']}/products/{product.get('handle', '')}?variant={group[0]['id']}",
            "image": _image_for(group, images),
        })
    return out


def _image_for(group: list, images: list) -> str:
    for v in group:
        if isinstance(v.get("featured_image"), dict) and v["featured_image"].get("src"):
            return v["featured_image"]["src"]
    ids = {v.get("id") for v in group}
    for img in images:
        if ids & set(img.get("variant_ids") or []):
            return img.get("src", "")
    return images[0].get("src", "") if images else ""
