from scraper.normalize import colour_family, colour_from_title, keep, materials, product_record, rows
from tests.fixtures import COLOUR_IN_TITLE, RETAILER, WITH_COLOUR_OPTION, WOMENS


def test_one_row_per_colour_option():
    out = {r["colour"]: r for r in rows(WITH_COLOUR_OPTION, RETAILER)}
    assert set(out) == {"Navy", "Heather Grey"}
    navy, grey = out["Navy"], out["Heather Grey"]
    assert navy["colour_family"] == "blue" and grey["colour_family"] == "grey"
    assert navy["sizes"] == "M"  # L is sold out
    assert navy["image"] == "https://img.example/navy.jpg"
    assert navy["url"] == "https://shop.example/products/organic-pocket-tee?variant=11"


def test_sale_price_and_currency():
    grey = next(r for r in rows(WITH_COLOUR_OPTION, RETAILER) if r["colour"] == "Heather Grey")
    assert grey["price"] == 30.0 and grey["compare_at"] == 40.0 and grey["on_sale"] is True
    assert grey["currency"] == "USD"


def test_colour_from_title_when_no_colour_option():
    (row,) = rows(COLOUR_IN_TITLE, RETAILER)
    assert row["colour"] == "Khaki Waxed Ripstop" and row["colour_family"] == "beige"
    assert row["sizes"] == "S, M" and row["in_stock"] is True
    assert row["image"] == "https://img.example/vest.jpg"


def test_title_patterns():
    assert colour_from_title("Pocket Tee - Black") == "Black"
    assert colour_from_title("Field Jacket in Olive") == "Olive"
    assert colour_from_title("Navy Linen Shirt") == "Navy"
    assert colour_from_title("Plain Shirt") is None


def test_colour_families():
    assert colour_family("Dark Navy Heather") == "blue"
    assert colour_family("Oatmeal") == "beige"
    assert colour_family("Dusty") == "other"


def test_materials():
    assert materials(WITH_COLOUR_OPTION["body_html"]) == "100% cotton"
    assert materials(COLOUR_IN_TITLE["body_html"]) == "55% hemp, 45% polyester"
    assert materials("A soft linen and wool blend") == "linen, wool"


def test_filters_use_whole_words():
    assert keep(WITH_COLOUR_OPTION, RETAILER)
    assert not keep(WOMENS, RETAILER)
    assert keep(WITH_COLOUR_OPTION, dict(RETAILER, include=["men"]))
    assert not keep(WOMENS, dict(RETAILER, include=["men"], exclude=[]))


def test_product_record_strips_html_and_handles_comma_tags():
    rec = product_record(COLOUR_IN_TITLE, RETAILER)
    assert rec["tags"] == "Men, Outerwear" and rec["category"] == "Outerwear"
    assert "<" not in rec["description"] and rec["product_id"] == "2"
