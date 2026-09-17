"""Core data model shared by every source and by scoring/filtering."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Listing:
    """A single marketplace listing, normalized across sources."""

    source: str  # "craigslist" | "facebook" | "nextdoor"
    external_id: str  # source-specific id, used for de-duping
    url: str
    title: str
    description: str  # verbatim listing text/body, as posted
    price: float  # 0.0 for free listings
    is_free: bool
    posted_at: Optional[datetime]  # UTC; None if unknown (fails freshness filter)
    location_text: str  # raw location string as given by the source
    lat: Optional[float] = None
    lon: Optional[float] = None
    photo_count: Optional[int] = None
    photo_urls: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)  # source-specific extra data

    @property
    def full_text(self) -> str:
        return f"{self.title}\n{self.description}"

    @property
    def dedupe_key(self) -> str:
        return f"{self.source}:{self.external_id}"


@dataclass
class FilterResult:
    passed: bool
    reasons_failed: list[str] = field(default_factory=list)
    distance_miles: Optional[float] = None
    category: Optional[str] = None
    matched_friction_phrases: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    total: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def top_factors(self, n: int = 3) -> list[tuple[str, float]]:
        positive = {k: v for k, v in self.breakdown.items() if v != 0}
        return sorted(positive.items(), key=lambda kv: kv[1], reverse=True)[:n]


@dataclass
class Candidate:
    """A listing that survived hard filtering, with its score attached."""

    listing: Listing
    filter_result: FilterResult
    score: ScoreResult
