import os

from boston_flipper.sources.craigslist import parse_detail_html, parse_search_results

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def test_parse_search_results_extracts_all_listings():
    html = load_fixture("craigslist_search_sample.html")
    listings = parse_search_results(html, category="free")
    assert len(listings) == 3

    first = listings[0]
    assert first.external_id == "7712345601"
    assert first.title == "Free sectional sofa, must pick up"
    assert first.is_free is True
    assert first.price == 0.0
    assert first.location_text == "Cambridge"
    assert first.posted_at is not None
    assert first.posted_at.year == 2026
    assert first.url.endswith("7712345601.html")


def test_parse_search_results_parses_price():
    html = load_fixture("craigslist_search_sample.html")
    listings = parse_search_results(html, category="furniture")
    dining = next(l for l in listings if "dining" in l.title.lower())
    assert dining.price == 40.0
    assert dining.is_free is False


def test_parse_search_results_handles_missing_data_gracefully():
    listings = parse_search_results("<html><body><ol></ol></body></html>", category="free")
    assert listings == []


def test_parse_detail_html_extracts_body_and_geo():
    html = load_fixture("craigslist_detail_sample.html")
    detail = parse_detail_html(html)
    assert "sectional sofa" in detail["description"].lower()
    assert "QR Code" not in detail["description"]
    assert detail["lat"] == 42.3736
    assert detail["lon"] == -71.1097
