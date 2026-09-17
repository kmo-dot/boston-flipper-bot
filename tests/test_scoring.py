from datetime import datetime, timedelta, timezone

from boston_flipper.filters import apply_hard_filters
from boston_flipper.models import Listing
from boston_flipper.scoring import score_listing

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def make_listing(**overrides) -> Listing:
    defaults = dict(
        source="craigslist",
        external_id="1",
        url="https://example.com/1",
        title="Free piano, must go this week",
        description=(
            "Beautiful upright piano, moving must go this week, you haul. "
            "Well maintained, tuned yearly, minor scuff on one leg but "
            "otherwise excellent condition. Bench included."
        ),
        price=0.0,
        is_free=True,
        posted_at=NOW - timedelta(hours=2),
        location_text="Cambridge",
        photo_count=1,
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_high_value_listing_scores_high():
    listing = make_listing()
    fr = apply_hard_filters(listing, now=NOW)
    assert fr.passed
    score = score_listing(listing, fr)
    assert score.total > 60
    assert score.breakdown["category_value"] == 30  # piano is capped at 30


def test_score_is_clamped_0_100():
    listing = make_listing(location_text="Boston")
    fr = apply_hard_filters(listing, now=NOW)
    score = score_listing(listing, fr)
    assert 0 <= score.total <= 100


def test_distance_penalty_reduces_score():
    near = make_listing(location_text="Boston")
    far = make_listing(location_text="Waltham")  # further from center

    near_fr = apply_hard_filters(near, now=NOW)
    far_fr = apply_hard_filters(far, now=NOW)
    assert near_fr.passed and far_fr.passed

    near_score = score_listing(near, near_fr)
    far_score = score_listing(far, far_fr)
    assert far_score.breakdown["distance_penalty"] <= near_score.breakdown["distance_penalty"]


def test_free_scores_higher_than_cheap():
    free_listing = make_listing(price=0.0, is_free=True)
    cheap_listing = make_listing(
        price=45.0, is_free=False,
        title="Piano for sale, must go this week",
        description=free_listing.description,
    )
    free_fr = apply_hard_filters(free_listing, now=NOW)
    cheap_fr = apply_hard_filters(cheap_listing, now=NOW)
    free_score = score_listing(free_listing, free_fr)
    cheap_score = score_listing(cheap_listing, cheap_fr)
    assert free_score.breakdown["free_vs_cheap"] > cheap_score.breakdown["free_vs_cheap"]


def test_top_factors_returns_highest_contributors():
    listing = make_listing()
    fr = apply_hard_filters(listing, now=NOW)
    score = score_listing(listing, fr)
    top = score.top_factors(3)
    assert len(top) <= 3
    values = [v for _, v in top]
    assert values == sorted(values, reverse=True)


def test_fewer_photos_scores_higher_photo_gap():
    many_photos = make_listing(photo_count=10)
    few_photos = make_listing(photo_count=0)
    fr = apply_hard_filters(many_photos, now=NOW)
    many_score = score_listing(many_photos, fr)
    few_score = score_listing(few_photos, fr)
    assert few_score.breakdown["photo_quality_gap"] > many_score.breakdown["photo_quality_gap"]
