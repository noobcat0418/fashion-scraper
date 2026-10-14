"""Synthetic Shopify-shaped products. No real brand data is committed."""

RETAILER = {"key": "demo", "name": "Demo Co", "domain": "shop.example", "currency": "USD", "exclude": ["women", "gift card"]}


def variant(vid, price, *opts, available=True, compare=None, image=None):
    v = {"id": vid, "price": f"{price:.2f}", "compare_at_price": f"{compare:.2f}" if compare else None,
         "available": available, "featured_image": {"src": image} if image else None}
    for i, o in enumerate(opts, 1):
        v[f"option{i}"] = o
    return v


# Colour is a real option: two colours x two sizes.
WITH_COLOUR_OPTION = {
    "id": 1, "title": "Organic Pocket Tee", "handle": "organic-pocket-tee", "product_type": "Tees",
    "vendor": "Demo Co", "tags": ["Men", "Organic"], "updated_at": "2026-10-01T00:00:00Z",
    "body_html": "<p>Made from <b>100% organic cotton</b>.</p>",
    "options": [{"name": "Color"}, {"name": "Size"}],
    "variants": [
        variant(11, 40, "Navy", "M", image="https://img.example/navy.jpg"),
        variant(12, 40, "Navy", "L", available=False),
        variant(13, 30, "Heather Grey", "M", compare=40),
        variant(14, 30, "Heather Grey", "L"),
    ],
    "images": [{"src": "https://img.example/main.jpg", "variant_ids": []}],
}

# Colour lives in the title; variants are sizes only.
COLOUR_IN_TITLE = {
    "id": 2, "title": "The Down Vest in Khaki Waxed Ripstop", "handle": "down-vest-khaki", "product_type": "Outerwear",
    "vendor": "Demo Co", "tags": "Men, Outerwear", "updated_at": "2026-10-02T00:00:00Z",
    "body_html": "Shell: 55% hemp, 45% recycled polyester. Fill: down.",
    "options": [{"name": "Size"}],
    "variants": [variant(21, 598, "S"), variant(22, 598, "M"), variant(23, 598, "L", available=False)],
    "images": [{"src": "https://img.example/vest.jpg", "variant_ids": [21]}],
}

WOMENS = dict(COLOUR_IN_TITLE, id=3, title="Women's Down Vest - Black", tags=["Women"])
