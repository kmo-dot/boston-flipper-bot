"""Central configuration for filters, scoring, and geography.

All tunables live here so stage 2+ work (and day-to-day tuning) doesn't
require touching scraper or scoring logic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

# Central Boston reference point (Downtown Crossing). Distance for every
# listing is measured from here.
CENTER_LAT = 42.3555
CENTER_LON = -71.0600

MAX_DISTANCE_MILES = float(os.environ.get("BFB_MAX_DISTANCE_MILES", 15))
FREE_DISTANCE_RADIUS_MILES = 5  # no distance penalty within this radius

# Known town/neighborhood centroids used to estimate distance when a source
# doesn't give us a precise lat/lon (e.g. Facebook relative-location text).
# Not exhaustive -- extend as needed. Towns roughly within 15mi of downtown
# Boston.
TOWN_CENTROIDS: dict[str, tuple[float, float]] = {
    "boston": (42.3601, -71.0589),
    "cambridge": (42.3736, -71.1097),
    "somerville": (42.3876, -71.0995),
    "brookline": (42.3318, -71.1212),
    "newton": (42.3370, -71.2092),
    "watertown": (42.3709, -71.1828),
    "waltham": (42.3765, -71.2356),
    "belmont": (42.3959, -71.1786),
    "arlington": (42.4154, -71.1565),
    "medford": (42.4184, -71.1062),
    "malden": (42.4251, -71.0662),
    "everett": (42.4084, -71.0537),
    "chelsea": (42.3918, -71.0328),
    "revere": (42.4084, -71.0120),
    "winthrop": (42.3751, -70.9834),
    "quincy": (42.2529, -71.0023),
    "milton": (42.2495, -71.0662),
    "dedham": (42.2432, -71.1662),
    "needham": (42.2809, -71.2356),
    "dorchester": (42.3016, -71.0676),
    "roxbury": (42.3111, -71.0899),
    "jamaica plain": (42.3097, -71.1150),
    "west roxbury": (42.2793, -71.1595),
    "hyde park": (42.2554, -71.1245),
    "south boston": (42.3381, -71.0476),
    "east boston": (42.3751, -71.0392),
    "charlestown": (42.3782, -71.0602),
    "allston": (42.3539, -71.1337),
    "brighton": (42.3496, -71.1543),
    "melrose": (42.4584, -71.0662),
    "winchester": (42.4526, -71.1370),
    "stoneham": (42.4801, -71.0995),
    "woburn": (42.4793, -71.1523),
    "braintree": (42.2223, -71.0023),
    "weymouth": (42.2180, -70.9395),
    "brookline village": (42.3318, -71.1212),
}

# ---------------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------------

MAX_PRICE_USD = float(os.environ.get("BFB_MAX_PRICE", 50))
MAX_LISTING_AGE_HOURS = float(os.environ.get("BFB_MAX_AGE_HOURS", 24))

# Category keywords -> bulky/heavy item classification. Listing text
# (title + description) is matched against these (case-insensitive).
BULKY_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "piano_organ": ["piano", "organ", "baby grand", "upright piano"],
    "sectional_sofa": ["sectional", "sofa", "couch", "loveseat", "chaise"],
    "bedroom_furniture": [
        "bed frame", "mattress", "dresser", "armoire", "wardrobe",
        "bunk bed", "headboard", "nightstand",
    ],
    "dining_furniture": [
        "dining table", "dining set", "china cabinet", "hutch", "buffet",
        "credenza",
    ],
    "office_furniture": ["desk", "bookshelf", "bookcase", "file cabinet"],
    "appliance": [
        "refrigerator", "fridge", "freezer", "washer", "dryer",
        "dishwasher", "stove", "oven", "range", "microwave",
        "water heater", "air conditioner", "ac unit",
    ],
    "exercise_equipment": [
        "treadmill", "elliptical", "peloton", "exercise bike",
        "weight bench", "squat rack", "power rack", "rowing machine",
        "home gym",
    ],
    "large_electronics": [
        'tv', "television", "big screen", "projector screen",
        "entertainment center", "entertainment unit",
    ],
    "outdoor_bulky": [
        "patio set", "grill", "trampoline", "swing set", "shed",
        "hot tub",
    ],
    "general_furniture": ["furniture", "table", "chair set", "recliner"],
}

# Phrases in the "large_electronics" bucket that require a size qualifier to
# avoid false positives (a "tv stand" isn't inherently bulky, a "65 inch tv"
# is). Handled specially in filters.py.
TV_SIZE_PATTERN = r"(\d{2,3})\s*[\"'-]?\s*(inch|in\.?|\")?\s*(tv|television)"
TV_MIN_INCHES = 40

# Non-bulky phrases that should exclude a listing even if a keyword above
# matched (things that fit in a car trunk).
SMALL_ITEM_EXCLUSIONS = [
    "lamp only", "chair only -", "end table only", "side table only",
    "mini fridge", "tv stand only", "desk lamp", "table lamp", "floor lamp",
    "desk chair only", "desk organizer",
]

PICKUP_FRICTION_PHRASES = [
    "must pick up", "must be picked up", "you haul", "u haul", "you move",
    "no delivery", "cannot deliver", "can't deliver", "will not deliver",
    "moving, must go", "moving must go", "moving sale", "moving out",
    "free to good home", "curb alert", "curbside", "obo just want it gone",
    "just want it gone", "must go asap", "must go today", "must go this",
    "porch pickup", "garage pickup", "pick up only", "pickup only",
    "no shipping", "local pickup only", "heavy, you lift", "bring help",
    "bring muscle", "need strong",
]

# ---------------------------------------------------------------------------
# Soft scoring
# ---------------------------------------------------------------------------

HIGH_VALUE_CATEGORY_SCORE = {
    "piano_organ": 30,
    "sectional_sofa": 25,
    "appliance": 22,
    "exercise_equipment": 20,
    "dining_furniture": 18,
    "bedroom_furniture": 16,
    "large_electronics": 16,
    "office_furniture": 12,
    "outdoor_bulky": 14,
    "general_furniture": 10,
}

PREMIUM_BRAND_KEYWORDS = [
    "west elm", "pottery barn", "herman miller", "ethan allen",
    "crate and barrel", "crate & barrel", "room and board", "room & board",
    "restoration hardware", "rh ", "design within reach", "steinway",
    "yamaha", "kawai", "sub-zero", "subzero", "wolf range", "viking range",
    "bosch", "kitchenaid", "miele", "peloton", "nordictrack", "bowflex",
]
PREMIUM_BRAND_BONUS = 8  # added on top of category score, still capped at 30

URGENCY_PHRASES = [
    "must go", "moving sunday", "moving monday", "moving tuesday",
    "moving wednesday", "moving thursday", "moving friday",
    "moving saturday", "this week", "today only", "asap", "urgent",
    "deadline", "by friday", "by monday", "gone by", "need gone",
    "act fast", "first come",
]

DETAIL_WORD_COUNT_FOR_MAX_SCORE = 60  # description length considered "detailed"
DETAIL_WORD_COUNT_MIN = 8  # below this, zero detail points

DISTANCE_PENALTY_PER_MILE = 1  # points subtracted per mile beyond free radius

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

CRAIGSLIST_SUBDOMAIN = os.environ.get("BFB_CL_SUBDOMAIN", "boston")
# Craigslist search "category" path segments we poll. `zip` = free stuff,
# the rest are "for sale by owner" sections likely to carry bulky items.
CRAIGSLIST_CATEGORIES = {
    "free": "zip",
    "furniture": "fuo",
    "household": "hso",
    "appliances": "ppo",
}

FACEBOOK_STORAGE_STATE_PATH = os.environ.get(
    "BFB_FB_STORAGE_STATE", "data/sessions/facebook_storage_state.json"
)
FACEBOOK_MARKETPLACE_LOCATION_SLUG = os.environ.get("BFB_FB_LOCATION_SLUG", "boston")
FACEBOOK_SEARCH_QUERIES = [
    "free furniture", "free couch", "moving must go", "piano free",
    "appliances free", "treadmill free", "sectional",
]

NEXTDOOR_STORAGE_STATE_PATH = os.environ.get(
    "BFB_ND_STORAGE_STATE", "data/sessions/nextdoor_storage_state.json"
)
NEXTDOOR_MANUAL_INBOX_PATH = os.environ.get(
    "BFB_ND_MANUAL_INBOX", "data/nextdoor_manual_inbox.md"
)

OUTPUT_DIR = os.environ.get("BFB_OUTPUT_DIR", "output")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT_SECONDS = 20
