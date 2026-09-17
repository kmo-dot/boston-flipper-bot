"""Craigslist source adapter.

Craigslist search results are public, server-rendered HTML -- no login or
browser automation needed, which makes this the most reliable of the three
sources. The one risk is markup drift: Craigslist tweaks class names every
so often, so `parse_search_results` is kept isolated from the network call
and covered by a fixture-based test (tests/test_craigslist_parser.py) so a
drift shows up as a clean test failure rather than a silent zero-results
run.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .. import config
from ..models import Listing
from .base import Source

logger = logging.getLogger(__name__)

_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _search_url(category_code: str) -> str:
    return (
        f"https://{config.CRAIGSLIST_SUBDOMAIN}.craigslist.org/search/{category_code}"
        f"?postal=02111&search_distance={int(config.MAX_DISTANCE_MILES)}"
    )


def _parse_price(price_text: Optional[str]) -> tuple[float, bool]:
    if not price_text or not price_text.strip():
        return 0.0, True
    match = _PRICE_RE.search(price_text)
    if not match:
        return 0.0, True
    amount = float(match.group(0).replace(",", ""))
    return amount, amount == 0.0


def _extract_result_nodes(soup: BeautifulSoup) -> list:
    # Craigslist has used a couple of different list-item structures over
    # the years; try each in order and use whichever actually matches.
    nodes = soup.select("li.cl-search-result")
    if nodes:
        return nodes
    nodes = soup.select("li.result-row")
    if nodes:
        return nodes
    return soup.select("div.cl-search-result")


def _first_text(node, selectors: list[str]) -> Optional[str]:
    for sel in selectors:
        found = node.select_one(sel)
        if found and found.get_text(strip=True):
            return found.get_text(strip=True)
    return None


def parse_search_results(html: str, category: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    results: list[Listing] = []

    for node in _extract_result_nodes(soup):
        pid = node.get("data-pid") or node.get("data-id")

        title = _first_text(
            node,
            [".cl-app-anchor .label", "a.titlestring", "a.title", "a.result-title"],
        )
        link_el = node.select_one("a.cl-app-anchor") or node.select_one("a.result-title") or node.select_one("a")
        url = link_el.get("href") if link_el else None
        if not url or not title:
            continue
        if not pid:
            m = re.search(r"/(\d{6,})\.html", url)
            pid = m.group(1) if m else url

        price_text = _first_text(node, [".priceinfo", "span.price", ".price"])
        price, is_free = _parse_price(price_text)

        location = _first_text(node, [".location", "span.location"]) or ""

        time_el = node.select_one("time")
        posted_at = None
        if time_el and time_el.get("datetime"):
            try:
                posted_at = datetime.fromisoformat(time_el["datetime"])
            except ValueError:
                posted_at = None

        # Search-result pages don't include the full body text or lat/lon;
        # those come from the detail page. Stage 1 keeps this to one
        # request per search page (not per listing) to stay polite and
        # fast, using the title + any teaser text available as the
        # "description" and falling back to town-name distance matching.
        teaser = _first_text(node, [".cl-search-result-body", ".supertitle"]) or ""
        description = teaser if teaser and teaser != title else ""

        lat = lon = None
        if node.get("data-latitude") and node.get("data-longitude"):
            try:
                lat = float(node["data-latitude"])
                lon = float(node["data-longitude"])
            except ValueError:
                pass

        results.append(
            Listing(
                source="craigslist",
                external_id=str(pid),
                url=url,
                title=title,
                description=description,
                price=price,
                is_free=is_free,
                posted_at=posted_at,
                location_text=location,
                lat=lat,
                lon=lon,
                raw={"category": category},
            )
        )

    return results


def parse_detail_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    body_el = soup.select_one("#postingbody")
    description = body_el.get_text(" ", strip=True) if body_el else ""
    description = description.replace("QR Code Link to This Post", "").strip()

    lat = lon = None
    map_el = soup.select_one("#map")
    if map_el and map_el.get("data-latitude") and map_el.get("data-longitude"):
        try:
            lat = float(map_el["data-latitude"])
            lon = float(map_el["data-longitude"])
        except ValueError:
            pass

    return {"description": description, "lat": lat, "lon": lon}


def fetch_listing_detail(session: requests.Session, url: str) -> dict:
    """Fetch a single listing's detail page for full body text + geo.

    Kept separate from parse_detail_html so the pipeline can choose to
    skip this (faster, less load on Craigslist) or use it to fill in
    description/lat/lon for listings that already look promising from the
    search page alone, and so the parsing logic is testable without a
    network call.
    """
    resp = session.get(url, headers=config.REQUEST_HEADERS, timeout=config.REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    return parse_detail_html(resp.text)


class CraigslistSource(Source):
    name = "craigslist"

    def __init__(self, fetch_details: bool = True, detail_fetch_limit: int = 60):
        self.fetch_details = fetch_details
        self.detail_fetch_limit = detail_fetch_limit
        self.session = requests.Session()

    def fetch(self) -> list[Listing]:
        all_listings: list[Listing] = []
        seen_ids: set[str] = set()

        for category, code in config.CRAIGSLIST_CATEGORIES.items():
            try:
                resp = self.session.get(
                    _search_url(code),
                    headers=config.REQUEST_HEADERS,
                    timeout=config.REQUEST_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("craigslist: failed to fetch category %s: %s", category, exc)
                continue

            listings = parse_search_results(resp.text, category)
            for listing in listings:
                if listing.external_id in seen_ids:
                    continue
                seen_ids.add(listing.external_id)
                all_listings.append(listing)

        if self.fetch_details:
            for listing in all_listings[: self.detail_fetch_limit]:
                try:
                    detail = fetch_listing_detail(self.session, listing.url)
                except requests.RequestException as exc:
                    logger.warning("craigslist: detail fetch failed for %s: %s", listing.url, exc)
                    continue
                if detail["description"]:
                    listing.description = detail["description"]
                if detail["lat"] is not None:
                    listing.lat = detail["lat"]
                    listing.lon = detail["lon"]

        return all_listings
