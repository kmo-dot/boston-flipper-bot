"""Nextdoor source adapter.

STATUS: manual-paste fallback, by design decision (documented in the
README under "Nextdoor"). Nextdoor gates its classifieds/"Finds" behind a
verified-address login, is a heavy JS SPA with no stable public markup to
scrape, and -- unlike Facebook Marketplace, which is at least a well-worn
scraping target with known patterns -- automating login against an
address-verification-gated neighborhood network carries a much higher risk
of the account getting flagged, with no fallback path (you can't just
re-verify a new address). Rather than ship an untested, likely-to-break
Playwright scraper for it, stage 1 ships a manual-paste ingestion adapter:
you copy/paste listing text from Nextdoor into a plain text/markdown inbox
file in the format below, and it flows through the exact same hard
filters, scoring, and digest as the other two sources. This is a
deliberate scope decision, not a bug -- see README for the full rationale
and what a "real" Nextdoor scraper would need in a later stage.

Inbox file format (see data/nextdoor_manual_inbox.md for a template):

    ## <title>
    url: <link to the post, or "n/a">
    price: <amount, or "free">
    location: <neighborhood/town>
    posted: <ISO datetime, e.g. 2026-09-16T14:30:00, or "3 hours ago">
    ---
    <verbatim listing text -- paste exactly as written>
    ---

Multiple entries can be stacked in one file; each is separated by the next
`## ` heading.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from .. import config
from ..models import Listing
from .base import Source
from .facebook import parse_relative_time  # shared relative-time parser

logger = logging.getLogger(__name__)

_ENTRY_RE = re.compile(
    r"^##\s*(?P<title>[^\n]+?)\s*\n"
    r"(?P<meta>(?:^(?!---)[^\n]*\n)*?)"
    r"^---[^\n]*\n"
    r"(?P<body>[\s\S]*?)\n"
    r"^---[^\n]*$",
    re.MULTILINE,
)


def _parse_meta(meta_block: str) -> dict:
    fields = {}
    for line in meta_block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields


def _parse_posted(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    return parse_relative_time(value)


def parse_manual_inbox(text: str) -> list[Listing]:
    listings: list[Listing] = []
    for i, match in enumerate(_ENTRY_RE.finditer(text)):
        title = match.group("title").strip()
        meta = _parse_meta(match.group("meta"))
        body = match.group("body").strip()

        price_raw = meta.get("price", "").lower()
        is_free = price_raw in ("free", "0", "$0", "")
        price = 0.0
        if not is_free:
            m = re.search(r"[\d.]+", price_raw)
            price = float(m.group(0)) if m else 0.0

        listings.append(
            Listing(
                source="nextdoor",
                external_id=meta.get("url") or f"manual-{i}-{hash(title) & 0xffffff}",
                url=meta.get("url", "n/a"),
                title=title,
                description=body,
                price=price,
                is_free=is_free,
                posted_at=_parse_posted(meta.get("posted", "")),
                location_text=meta.get("location", ""),
            )
        )
    return listings


class NextdoorManualSource(Source):
    """Reads listings a human pasted into a local inbox file. See module
    docstring for the format and the reasoning behind this approach.
    """

    name = "nextdoor"

    def __init__(self, inbox_path: str = config.NEXTDOOR_MANUAL_INBOX_PATH):
        self.inbox_path = inbox_path

    def fetch(self) -> list[Listing]:
        try:
            with open(self.inbox_path) as f:
                text = f.read()
        except FileNotFoundError:
            logger.info(
                "nextdoor: no manual inbox file at %s (nothing pasted in yet, skipping)",
                self.inbox_path,
            )
            return []
        return parse_manual_inbox(text)
