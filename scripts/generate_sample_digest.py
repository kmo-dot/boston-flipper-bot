#!/usr/bin/env python3
"""Runs the real filter/scoring/digest pipeline against realistic
synthetic listings.

This exists because the sandbox this project was originally built in has
no outbound network access to Craigslist/Facebook/Nextdoor, so the actual
scrapers couldn't be exercised against live data there. This script
proves the pipeline logic itself (parsing -> hard filters -> scoring ->
ranked markdown digest) end-to-end using listings shaped like what the
real sources would hand back -- including a few that *should* get
filtered out, to demonstrate the filters are actually doing something.

    python scripts/generate_sample_digest.py

Writes examples/sample_digest.md.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from boston_flipper.digest import render_digest  # noqa: E402
from boston_flipper.models import Listing  # noqa: E402
from boston_flipper.pipeline import build_candidates, dedupe  # noqa: E402

NOW = datetime.now(timezone.utc)


def ago(**kwargs) -> datetime:
    return NOW - timedelta(**kwargs)


LISTINGS = [
    # --- Should PASS: high-value, clear friction language, close, fresh ---
    Listing(
        source="craigslist",
        external_id="cl-1001",
        url="https://boston.craigslist.org/gbs/zip/d/cambridge-free-upright-piano-you/7799001.html",
        title="Free upright piano, you haul",
        description=(
            "Free upright piano, must go this week -- we're moving Sunday and "
            "it cannot come with us. Tuned last year, a few cosmetic scratches "
            "on the cabinet but plays beautifully. You haul, need at least two "
            "strong people and a dolly. No delivery, must pick up from our "
            "first-floor apartment, no stairs."
        ),
        price=0.0,
        is_free=True,
        posted_at=ago(hours=3),
        location_text="Cambridge, MA",
        photo_count=1,
    ),
    Listing(
        source="facebook",
        external_id="fb-2002",
        url="https://www.facebook.com/marketplace/item/2002/",
        title="West Elm sectional, moving must go",
        description=(
            "West Elm sectional sofa, moving must go by Friday. No delivery, "
            "pickup only in Somerville. Some wear on the cushions but very "
            "comfortable, no stains or damage. OBO just want it gone before "
            "the movers come."
        ),
        price=45.0,
        is_free=False,
        posted_at=ago(hours=8),
        location_text="Somerville, MA",
        photo_count=2,
    ),
    Listing(
        source="nextdoor",
        external_id="nd-3003",
        url="n/a",
        title="Free to good home: washer and dryer set",
        description=(
            "Free to good home, washer and dryer set, both work fine, just "
            "upgraded. Curb alert -- they're sitting on the porch, must pick "
            "up today or tomorrow, no delivery. Heavy, bring help."
        ),
        price=0.0,
        is_free=True,
        posted_at=ago(hours=1),
        location_text="Jamaica Plain",
        photo_count=0,
    ),
    Listing(
        source="craigslist",
        external_id="cl-1004",
        url="https://boston.craigslist.org/gbs/ppo/d/quincy-kitchenaid-fridge-must-go/7799004.html",
        title="KitchenAid fridge, must pick up",
        description=(
            "KitchenAid refrigerator, still cold and working, must pick up "
            "this weekend, we're closing on our move-out. No delivery "
            "possible, you'll need an appliance dolly and at least one other "
            "person -- it's heavy."
        ),
        price=50.0,
        is_free=False,
        posted_at=ago(hours=14),
        location_text="Quincy, MA",
        photo_count=6,
    ),
    # --- Should FAIL: over price cap ---
    Listing(
        source="craigslist",
        external_id="cl-1005",
        url="https://boston.craigslist.org/gbs/fuo/d/newton-leather-sectional/7799005.html",
        title="Leather sectional, must pick up",
        description="Great condition, must pick up, no delivery. Moving must go.",
        price=350.0,
        is_free=False,
        posted_at=ago(hours=5),
        location_text="Newton, MA",
        photo_count=4,
    ),
    # --- Should FAIL: not a bulky category (small item) ---
    Listing(
        source="facebook",
        external_id="fb-2006",
        url="https://www.facebook.com/marketplace/item/2006/",
        title="Free desk lamp, must pick up",
        description="Small desk lamp, works great, must pick up, no delivery.",
        price=0.0,
        is_free=True,
        posted_at=ago(hours=2),
        location_text="Brookline, MA",
        photo_count=1,
    ),
    # --- Should FAIL: no pickup-friction language (easy sale, not our target) ---
    Listing(
        source="craigslist",
        external_id="cl-1007",
        url="https://boston.craigslist.org/gbs/hso/d/malden-dining-set/7799007.html",
        title="Dining table and chairs, flexible",
        description=(
            "Solid wood dining table with 6 chairs, happy to hold or deliver "
            "locally for a small fee, very flexible on timing."
        ),
        price=40.0,
        is_free=False,
        posted_at=ago(hours=6),
        location_text="Malden, MA",
        photo_count=5,
    ),
    # --- Should FAIL: too far ---
    Listing(
        source="craigslist",
        external_id="cl-1008",
        url="https://boston.craigslist.org/gbs/zip/d/worcester-free-piano/7799008.html",
        title="Free piano, must go, you haul",
        description="Moving must go, must pick up, no delivery, you haul.",
        price=0.0,
        is_free=True,
        posted_at=ago(hours=4),
        location_text="Worcester, MA",
        photo_count=1,
    ),
    # --- Should FAIL: stale (>24h) ---
    Listing(
        source="nextdoor",
        external_id="nd-3009",
        url="n/a",
        title="Free treadmill, must go",
        description="Moving must go, must pick up, curb alert, no delivery.",
        price=0.0,
        is_free=True,
        posted_at=ago(hours=40),
        location_text="Dorchester",
        photo_count=2,
    ),
]


def main():
    deduped = dedupe(LISTINGS)
    candidates = build_candidates(deduped, now=NOW)
    source_counts = {}
    for listing in LISTINGS:
        source_counts[listing.source] = source_counts.get(listing.source, 0) + 1

    digest = render_digest(
        candidates,
        run_time=NOW,
        source_counts=source_counts,
        source_errors=None,
    )

    out_dir = os.path.join(os.path.dirname(__file__), "..", "examples")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "sample_digest.md")
    with open(out_path, "w") as f:
        f.write(digest)

    print(f"{len(LISTINGS)} synthetic listings in, {len(candidates)} candidates passed filters.")
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
