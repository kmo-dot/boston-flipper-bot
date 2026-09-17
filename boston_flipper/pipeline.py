"""Orchestrates a single run: fetch every source, dedupe, hard-filter,
score, and render a digest. One source failing outright never kills the
run -- it's recorded and shown in the digest so you know to go check it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from . import config
from .digest import write_digest
from .filters import apply_hard_filters
from .models import Candidate, Listing
from .scoring import score_listing
from .sources.base import Source

logger = logging.getLogger(__name__)


def dedupe(listings: list[Listing]) -> list[Listing]:
    seen: set[str] = set()
    result = []
    for listing in listings:
        key = listing.dedupe_key
        if key in seen:
            continue
        seen.add(key)
        result.append(listing)
    return result


def build_candidates(listings: list[Listing], now: datetime | None = None) -> list[Candidate]:
    candidates = []
    for listing in listings:
        filter_result = apply_hard_filters(listing, now=now)
        if not filter_result.passed:
            continue
        score = score_listing(listing, filter_result)
        candidates.append(Candidate(listing=listing, filter_result=filter_result, score=score))
    return candidates


def run_pipeline(sources: list[Source], output_dir: str = config.OUTPUT_DIR) -> str:
    run_time = datetime.now(timezone.utc)
    all_listings: list[Listing] = []
    source_errors: dict[str, str] = {}
    source_counts: dict[str, int] = {}

    for source in sources:
        try:
            listings = source.fetch()
        except Exception as exc:  # noqa: BLE001 - isolate source failures
            logger.exception("source %s failed", source.name)
            source_errors[source.name] = str(exc)
            source_counts[source.name] = 0
            continue
        source_counts[source.name] = len(listings)
        all_listings.extend(listings)
        logger.info("%s: fetched %d listing(s)", source.name, len(listings))

    deduped = dedupe(all_listings)
    candidates = build_candidates(deduped, now=run_time)
    logger.info(
        "%d listing(s) fetched, %d after dedupe, %d passed hard filters",
        len(all_listings), len(deduped), len(candidates),
    )

    path = write_digest(
        candidates, output_dir, run_time=run_time,
        source_errors=source_errors, source_counts=source_counts,
    )
    return path
