"""Hard filters. A listing must pass every one of these to become a
candidate. See README for the rationale behind each filter.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config
from .geo import resolve_distance_miles
from .models import FilterResult, Listing

_TV_RE = re.compile(config.TV_SIZE_PATTERN, re.IGNORECASE)


def classify_category(text: str) -> Optional[str]:
    """Return the best-matching bulky category key, or None if nothing
    in the listing text looks like a bulky/heavy item.
    """
    lowered = text.lower()

    for phrase in config.SMALL_ITEM_EXCLUSIONS:
        if phrase in lowered:
            return None

    # TVs only count as bulky if a size is given and it's >= threshold.
    tv_match = _TV_RE.search(lowered)
    has_qualifying_tv = False
    if tv_match:
        try:
            inches = int(tv_match.group(1))
            has_qualifying_tv = inches >= config.TV_MIN_INCHES
        except ValueError:
            has_qualifying_tv = False

    best_category = None
    best_hits = 0
    for category, keywords in config.BULKY_CATEGORY_KEYWORDS.items():
        if category == "large_electronics":
            hits = sum(1 for kw in keywords if kw != "tv" and kw in lowered)
            if has_qualifying_tv:
                hits += 1
        else:
            hits = sum(1 for kw in keywords if kw in lowered)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    return best_category


def has_pickup_friction(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in config.PICKUP_FRICTION_PHRASES if p in lowered]


def is_price_ok(listing: Listing) -> bool:
    if listing.is_free:
        return True
    return 0 <= listing.price <= config.MAX_PRICE_USD


def is_fresh(listing: Listing, now: Optional[datetime] = None) -> bool:
    if listing.posted_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    posted = listing.posted_at
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age = now - posted
    return timedelta(0) <= age <= timedelta(hours=config.MAX_LISTING_AGE_HOURS)


def apply_hard_filters(listing: Listing, now: Optional[datetime] = None) -> FilterResult:
    reasons: list[str] = []

    if not is_price_ok(listing):
        reasons.append(f"price ${listing.price:.0f} exceeds cap ${config.MAX_PRICE_USD:.0f}")

    category = classify_category(listing.full_text)
    if category is None:
        reasons.append("not a recognized bulky/heavy category")

    friction_matches = has_pickup_friction(listing.full_text)
    if not friction_matches:
        reasons.append("no pickup-friction language found")

    distance = resolve_distance_miles(listing.lat, listing.lon, listing.location_text)
    if distance is None:
        reasons.append("could not determine distance from Boston")
    elif distance > config.MAX_DISTANCE_MILES:
        reasons.append(
            f"{distance:.1f}mi exceeds {config.MAX_DISTANCE_MILES:.0f}mi radius"
        )

    if not is_fresh(listing, now=now):
        if listing.posted_at is None:
            reasons.append("unknown post time")
        else:
            reasons.append("older than 24h")

    return FilterResult(
        passed=not reasons,
        reasons_failed=reasons,
        distance_miles=distance,
        category=category,
        matched_friction_phrases=friction_matches,
    )
