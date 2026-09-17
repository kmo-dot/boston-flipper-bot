"""Facebook Marketplace source adapter.

STATUS: best-effort / fragile by nature. Facebook has no public API for
Marketplace, requires a logged-in session, and runs aggressive automated-
browsing detection. This adapter works by driving a real Chromium profile
via Playwright with a *persisted* login session (see
scripts/capture_facebook_session.py and the README section on session
persistence) rather than storing or entering a password anywhere -- that
keeps credentials out of the repo/scheduler entirely and avoids scripted
login flows, which are exactly what trips FB's bot detection hardest.

Expect this to need occasional selector maintenance as Facebook changes
its DOM. Every extraction step is defensive (try/except, skip-and-log on a
single card failing) so a partial break degrades results rather than
killing the run, and a fully broken login/selectors surfaces as a clear
"0 listings from facebook" + logged warning rather than a crash.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from .. import config
from ..models import Listing
from .base import Source

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"\$\s?([\d,]+)")
_RELATIVE_TIME_RE = re.compile(
    r"(\d+)\s*(minute|min|hour|hr|day|week)s?\s*ago", re.IGNORECASE
)


def _search_url(query: str) -> str:
    slug = config.FACEBOOK_MARKETPLACE_LOCATION_SLUG
    return (
        f"https://www.facebook.com/marketplace/{slug}/search/"
        f"?query={quote(query)}&maxPrice={int(config.MAX_PRICE_USD)}&daysSinceListed=1"
    )


def parse_relative_time(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    now = now or datetime.now(timezone.utc)
    if not text:
        return None
    lowered = text.lower()
    if "just now" in lowered or "moments ago" in lowered:
        return now
    match = _RELATIVE_TIME_RE.search(lowered)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2)
    if unit.startswith("min"):
        delta = timedelta(minutes=amount)
    elif unit in ("hour", "hr"):
        delta = timedelta(hours=amount)
    elif unit == "day":
        delta = timedelta(days=amount)
    elif unit == "week":
        delta = timedelta(weeks=amount)
    else:
        return None
    return now - delta


def _parse_card_text(raw_text: str) -> dict:
    """Facebook marketplace cards render as a blob of stacked <span>s with
    no semantic markup, so we get back one newline-joined text string per
    card and heuristically split it into fields. Order has historically
    been: price, title, location[, distance/shipping note].
    """
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    price_line = next((l for l in lines if l.lower() == "free" or _PRICE_RE.search(l)), None)
    price = 0.0
    is_free = False
    if price_line:
        if price_line.lower() == "free":
            is_free = True
        else:
            m = _PRICE_RE.search(price_line)
            if m:
                price = float(m.group(1).replace(",", ""))

    remaining = [l for l in lines if l != price_line]
    title = remaining[0] if remaining else ""
    location = remaining[1] if len(remaining) > 1 else ""

    return {"price": price, "is_free": is_free, "title": title, "location": location}


class FacebookMarketplaceSource(Source):
    name = "facebook"

    def __init__(
        self,
        storage_state_path: str = config.FACEBOOK_STORAGE_STATE_PATH,
        queries: Optional[list[str]] = None,
        max_cards_per_query: int = 30,
        visit_detail_pages: bool = True,
        detail_visit_limit: int = 20,
        headless: bool = True,
    ):
        self.storage_state_path = storage_state_path
        self.queries = queries or config.FACEBOOK_SEARCH_QUERIES
        self.max_cards_per_query = max_cards_per_query
        self.visit_detail_pages = visit_detail_pages
        self.detail_visit_limit = detail_visit_limit
        self.headless = headless

    def fetch(self) -> list[Listing]:
        if not os.path.exists(self.storage_state_path):
            raise RuntimeError(
                f"No Facebook session found at {self.storage_state_path}. "
                "Run scripts/capture_facebook_session.py once to log in "
                "interactively and persist the session, then re-run."
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed. Run `pip install playwright && "
                "playwright install chromium`."
            ) from exc

        listings: list[Listing] = []
        seen_ids: set[str] = set()
        detail_visits = 0

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(storage_state=self.storage_state_path)
            page = context.new_page()

            for query in self.queries:
                try:
                    page.goto(_search_url(query), wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2500)
                    # Marketplace lazy-loads on scroll; a couple of nudges
                    # is enough for stage 1's needs without hammering FB.
                    for _ in range(3):
                        page.mouse.wheel(0, 2000)
                        page.wait_for_timeout(800)

                    cards = page.eval_on_selector_all(
                        'a[href*="/marketplace/item/"]',
                        """els => els.map(el => ({
                            href: el.getAttribute('href'),
                            text: el.innerText,
                        }))""",
                    )
                except Exception as exc:  # noqa: BLE001 - keep the run alive
                    logger.warning("facebook: query %r failed: %s", query, exc)
                    continue

                for card in cards[: self.max_cards_per_query]:
                    href = card.get("href") or ""
                    m = re.search(r"/marketplace/item/(\d+)", href)
                    if not m:
                        continue
                    item_id = m.group(1)
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)

                    parsed = _parse_card_text(card.get("text") or "")
                    if not parsed["title"]:
                        continue

                    url = f"https://www.facebook.com/marketplace/item/{item_id}/"
                    listings.append(
                        Listing(
                            source="facebook",
                            external_id=item_id,
                            url=url,
                            title=parsed["title"],
                            description="",
                            price=parsed["price"],
                            is_free=parsed["is_free"],
                            posted_at=None,
                            location_text=parsed["location"],
                            raw={"query": query},
                        )
                    )

            if self.visit_detail_pages:
                for listing in listings:
                    if detail_visits >= self.detail_visit_limit:
                        break
                    try:
                        page.goto(listing.url, wait_until="domcontentloaded", timeout=20000)
                        page.wait_for_timeout(1500)
                        detail_visits += 1
                        body_text = page.inner_text("body")
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("facebook: detail fetch failed for %s: %s", listing.url, exc)
                        continue

                    posted_at = None
                    for line in body_text.split("\n"):
                        posted_at = parse_relative_time(line)
                        if posted_at:
                            break
                    listing.posted_at = posted_at

                    # Best-effort: grab the longest paragraph as description.
                    candidates = [l.strip() for l in body_text.split("\n") if len(l.strip()) > 40]
                    if candidates:
                        listing.description = max(candidates, key=len)

            context.close()
            browser.close()

        return listings
