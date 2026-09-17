from datetime import datetime, timedelta, timezone

from boston_flipper.filters import apply_hard_filters, classify_category, has_pickup_friction
from boston_flipper.models import Listing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def make_listing(**overrides) -> Listing:
    defaults = dict(
        source="craigslist",
        external_id="1",
        url="https://example.com/1",
        title="Free couch, must pick up",
        description="Moving must go this week, you haul. Great condition sectional sofa.",
        price=0.0,
        is_free=True,
        posted_at=NOW - timedelta(hours=2),
        location_text="Cambridge",
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_passes_all_filters():
    listing = make_listing()
    result = apply_hard_filters(listing, now=NOW)
    assert result.passed, result.reasons_failed
    assert result.category == "sectional_sofa"


def test_fails_price_cap():
    listing = make_listing(price=200, is_free=False)
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("price" in r for r in result.reasons_failed)


def test_fails_non_bulky_category():
    listing = make_listing(
        title="Free lamp", description="must pick up, small desk lamp only"
    )
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("category" in r for r in result.reasons_failed)


def test_fails_no_pickup_friction():
    listing = make_listing(
        title="Sectional sofa for sale",
        description="Great condition, will deliver if needed, flexible on price.",
    )
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("friction" in r for r in result.reasons_failed)


def test_fails_too_far():
    listing = make_listing(location_text="Worcester")  # ~40mi from Boston, not in town table
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed


def test_fails_stale_listing():
    listing = make_listing(posted_at=NOW - timedelta(hours=30))
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("24h" in r for r in result.reasons_failed)


def test_fails_unknown_post_time():
    listing = make_listing(posted_at=None)
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("unknown post time" in r for r in result.reasons_failed)


def test_tv_requires_size_qualifier():
    small = make_listing(title="Free tv", description="must pick up, small tv, works great")
    assert classify_category(small.full_text) is None

    big = make_listing(
        title="Free 65 inch tv", description="must pick up, 65 inch tv, works great"
    )
    assert classify_category(big.full_text) == "large_electronics"


def test_desk_lamp_is_not_bulky_despite_desk_keyword():
    # "desk" alone is a bulky (office furniture) keyword, but "desk lamp"
    # is a small item that shares the substring -- must not misclassify.
    listing = make_listing(
        title="Free desk lamp, must pick up",
        description="Small desk lamp, works great, must pick up, no delivery.",
    )
    result = apply_hard_filters(listing, now=NOW)
    assert not result.passed
    assert any("category" in r for r in result.reasons_failed)


def test_pickup_friction_matches_multiple_phrases():
    text = "Moving must go, must pick up, curb alert!"
    matches = has_pickup_friction(text)
    assert "moving must go" in matches or "must pick up" in matches
    assert len(matches) >= 2
