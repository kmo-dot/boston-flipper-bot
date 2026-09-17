import os

from boston_flipper.sources.nextdoor import parse_manual_inbox

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

SAMPLE = """
## Free sectional, must go this week
url: https://nextdoor.com/p/abc123
price: free
location: Jamaica Plain
posted: 2026-09-17T08:00:00
---
Moving out Sunday, must pick up. Great condition sectional, you haul.
---

## Old treadmill, OBO just want it gone
url: n/a
price: $30
location: Somerville
posted: 3 hours ago
---
Works fine, minor cosmetic wear. No delivery, pick up only.
---
"""


def test_parses_multiple_entries():
    listings = parse_manual_inbox(SAMPLE)
    assert len(listings) == 2

    first = listings[0]
    assert first.title == "Free sectional, must go this week"
    assert first.is_free is True
    assert first.location_text == "Jamaica Plain"
    assert first.source == "nextdoor"

    second = listings[1]
    assert second.price == 30.0
    assert second.is_free is False
    assert second.posted_at is not None


def test_empty_inbox_returns_no_listings():
    assert parse_manual_inbox("") == []
    assert parse_manual_inbox("<!-- just instructions, no entries -->") == []


def test_committed_template_has_no_live_entries():
    # Regression: the shipped template's own instructional example must
    # not itself be parsed as a real listing.
    with open(os.path.join(REPO_ROOT, "data", "nextdoor_manual_inbox.md")) as f:
        text = f.read()
    assert parse_manual_inbox(text) == []
