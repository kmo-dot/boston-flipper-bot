"""Distance helpers. No external geocoding API -- stage 1 keeps this
dependency-free by matching location text against a known-town centroid
table (config.TOWN_CENTROIDS) when a source doesn't hand us a precise
lat/lon.
"""
from __future__ import annotations

import math
import re
from typing import Optional

from . import config

EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def distance_from_center(lat: float, lon: float) -> float:
    return haversine_miles(config.CENTER_LAT, config.CENTER_LON, lat, lon)


def guess_town_coords(location_text: str) -> Optional[tuple[float, float]]:
    """Best-effort town match from a free-text location string.

    Longest known town name found in the text wins, so "Jamaica Plain"
    matches before a stray "Boston" substring, etc.
    """
    if not location_text:
        return None
    text = location_text.lower()
    text = re.sub(r"[^a-z\s]", " ", text)
    matches = [name for name in config.TOWN_CENTROIDS if name in text]
    if not matches:
        return None
    best = max(matches, key=len)
    return config.TOWN_CENTROIDS[best]


def resolve_distance_miles(
    lat: Optional[float], lon: Optional[float], location_text: str
) -> Optional[float]:
    """Distance in miles from the central-Boston reference point, or None
    if it can't be determined from either coordinates or town-name match.
    """
    if lat is not None and lon is not None:
        return distance_from_center(lat, lon)
    coords = guess_town_coords(location_text)
    if coords is None:
        return None
    return distance_from_center(*coords)
