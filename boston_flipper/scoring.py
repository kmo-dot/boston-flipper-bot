"""Soft scoring (0-100). Only called on listings that already passed every
hard filter. See README for the rationale behind the photo-quality-gap
heuristic in particular (it's a proxy, not real image analysis).
"""
from __future__ import annotations

from . import config
from .models import FilterResult, Listing, ScoreResult


def score_category_value(listing: Listing, category: str | None) -> float:
    if category is None:
        return 0.0
    base = config.HIGH_VALUE_CATEGORY_SCORE.get(category, 10)
    lowered = listing.full_text.lower()
    if any(brand in lowered for brand in config.PREMIUM_BRAND_KEYWORDS):
        base += config.PREMIUM_BRAND_BONUS
    return min(base, 30.0)


def score_photo_quality_gap(listing: Listing) -> float:
    """Heuristic proxy for "worse original photos = more opportunity".

    Stage 1 has no image-analysis step, so this approximates using photo
    count only: fewer photos (especially 0-1) suggests a low-effort/bad
    listing that's more likely underpriced relative to the item's real
    condition. This is intentionally conservative -- treat it as a weak
    signal, not a verdict.
    """
    count = listing.photo_count
    if count is None:
        return 5.0  # unknown -- small neutral credit
    if count == 0:
        return 20.0
    if count == 1:
        return 15.0
    if count <= 2:
        return 10.0
    if count <= 4:
        return 5.0
    return 0.0


def score_free_vs_cheap(listing: Listing) -> float:
    if listing.is_free:
        return 15.0
    if listing.price <= 10:
        return 10.0
    if listing.price <= 25:
        return 6.0
    return 3.0


def score_urgency(listing: Listing) -> float:
    lowered = listing.full_text.lower()
    hits = sum(1 for phrase in config.URGENCY_PHRASES if phrase in lowered)
    return min(hits * 6.0, 15.0)


def score_description_detail(listing: Listing) -> float:
    word_count = len(listing.description.split())
    if word_count <= config.DETAIL_WORD_COUNT_MIN:
        return 0.0
    span = config.DETAIL_WORD_COUNT_FOR_MAX_SCORE - config.DETAIL_WORD_COUNT_MIN
    fraction = min((word_count - config.DETAIL_WORD_COUNT_MIN) / span, 1.0)
    return round(fraction * 10.0, 1)


def score_distance_penalty(distance_miles: float | None) -> float:
    if distance_miles is None:
        return 0.0
    over = max(0.0, distance_miles - config.FREE_DISTANCE_RADIUS_MILES)
    return -over * config.DISTANCE_PENALTY_PER_MILE


def score_listing(listing: Listing, filter_result: FilterResult) -> ScoreResult:
    breakdown = {
        "category_value": round(score_category_value(listing, filter_result.category), 1),
        "photo_quality_gap": round(score_photo_quality_gap(listing), 1),
        "free_vs_cheap": round(score_free_vs_cheap(listing), 1),
        "urgency_language": round(score_urgency(listing), 1),
        "description_detail": round(score_description_detail(listing), 1),
        "distance_penalty": round(score_distance_penalty(filter_result.distance_miles), 1),
    }
    total = sum(breakdown.values())
    total = max(0.0, min(100.0, total))
    return ScoreResult(total=round(total, 1), breakdown=breakdown)
