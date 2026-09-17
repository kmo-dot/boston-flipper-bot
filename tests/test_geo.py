from boston_flipper.geo import guess_town_coords, resolve_distance_miles


def test_guess_town_coords_matches_known_town():
    assert guess_town_coords("Free couch, Cambridge, MA") is not None


def test_guess_town_coords_returns_none_for_unknown():
    assert guess_town_coords("Worcester, MA") is None


def test_guess_town_coords_prefers_longer_match():
    # "jamaica plain" should win over a coincidental "boston" substring.
    coords = guess_town_coords("Jamaica Plain, Boston area")
    from boston_flipper import config
    assert coords == config.TOWN_CENTROIDS["jamaica plain"]


def test_resolve_distance_uses_lat_lon_when_available():
    d = resolve_distance_miles(42.3601, -71.0589, "irrelevant text")
    assert d is not None
    assert d < 1  # essentially at the Boston center point


def test_resolve_distance_falls_back_to_town_text():
    d = resolve_distance_miles(None, None, "Somerville")
    assert d is not None
    assert d < 10


def test_resolve_distance_none_when_unresolvable():
    assert resolve_distance_miles(None, None, "Nowhereville") is None
