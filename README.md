# Boston Flipperbot — Stage 1

A sourcing scraper/digest tool for a bulky-item flipping business in
Boston. Stage 1 only: it finds candidate listings and writes a ranked
markdown digest. **It does not message sellers, relist items, book
logistics, or handle payments** — those are later stages.

## What it does

On each run it:

1. Pulls listings from Craigslist (free + furniture/household/appliances
   sections for Greater Boston), Facebook Marketplace, and Nextdoor
   (manual-paste, see below).
2. Applies hard filters — a listing must pass **all** of these to be a
   candidate:
   - Price ≤ $50, or free
   - Bulky/heavy category (furniture, appliances, pianos/organs, exercise
     equipment, large electronics — not stuff that fits in a car trunk)
   - Contains pickup-friction language ("must pick up," "you haul," "no
     delivery," "moving must go," "free to good home," "curb alert," etc.)
   - Within ~15 miles of central Boston
   - Posted within the last 24 hours
3. Scores every candidate 0–100 (category value, photo-quality-gap proxy,
   free-vs-cheap, urgency language, description detail, minus a distance
   penalty beyond 5 miles — see `boston_flipper/config.py` and
   `boston_flipper/scoring.py` for exact weights).
4. Writes `output/digest_<timestamp>.md` (and updates `output/latest.md`)
   with every candidate ranked by score, including the verbatim listing
   text, price, platform + link, score breakdown, distance, and how long
   ago it was posted.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # only needed for the Facebook source
cp .env.example .env          # optional, defaults are sane
```

Run everything:

```bash
python -m boston_flipper.cli run
```

Run a subset of sources (useful while Facebook's session is stale, or if
you don't use Nextdoor):

```bash
python -m boston_flipper.cli run --sources craigslist,nextdoor
```

## The three sources, and why they're built differently

### Craigslist — fully automated, no login

Craigslist search results are public, server-rendered HTML, so
`boston_flipper/sources/craigslist.py` just does plain HTTP requests +
HTML parsing (`requests` + `BeautifulSoup`). This is the most reliable
source and needs no session management at all. Its one weak point is that
Craigslist tweaks its markup occasionally; the parser tries a couple of
known selector variants and is covered by
`tests/test_craigslist_parser.py` against a saved fixture page, so a
markup change shows up as a failing test rather than a silent
zero-results run.

### Facebook Marketplace — automated, but fragile by nature (flagged)

Facebook Marketplace has no public API and requires a logged-in session.
**This is the "known hard problem" called out in the stage 1 brief.**

**Decision made:** persist a logged-in browser session via Playwright's
`storage_state` (cookies + local storage), captured by you logging in
once, by hand, in a real visible browser window
(`scripts/capture_facebook_session.py`). The scraper then reuses that
session headlessly on scheduled runs.

**Why not store a username/password and script the login form instead?**
Scripting the login flow itself (typing credentials into the form via
automation) is one of the most reliable ways to get an account flagged
for suspicious login activity — it's a very different signal than
reusing an already-established session's cookies. Logging in by hand
sidesteps that, and it also means no Facebook credentials ever exist in
this repo, in `.env`, or anywhere a scheduler needs to read them.

**The tradeoff:** the session *will* expire eventually — Facebook cycles
sessions on its own schedule (inactivity, security checks, a password
change, a new device flag, etc.), and there's no way to predict exactly
when. When it does, scheduled runs will log `0 listings from facebook`
plus a warning, and you'll need to re-run
`scripts/capture_facebook_session.py` once (2–5 minutes). This is a
manual, recurring chore — I didn't find a way to fully automate it that
doesn't reintroduce the "scripted login" bot-detection risk above.

Beyond the session, this source is also fragile in the ordinary sense:
Facebook Marketplace is a heavy JS single-page app with no stable,
documented markup, so `boston_flipper/sources/facebook.py` scrapes
rendered text off cards using Playwright and parses it heuristically. It
degrades gracefully (a broken card is skipped and logged, not a crash),
but expect to need to patch selectors/parsing occasionally as Facebook's
UI changes. **I was not able to test this against live Facebook data** —
see "What I could not verify" below.

### Nextdoor — manual-paste fallback (deliberately not scraped)

**Decision made:** rather than ship an untested, likely-to-break
Nextdoor scraper, stage 1 uses a manual-paste inbox
(`data/nextdoor_manual_inbox.md`) — when you see a bulky-item post on
Nextdoor, you paste it into that file in a simple format, and it flows
through the exact same filters/scoring/digest as the other two sources.

**Why not automate it like Facebook:** Nextdoor gates its
classifieds/"Finds" behind address-verified accounts tied to a specific
neighborhood. A flagged/locked account has no real recovery path the way
a Facebook account does (you can't just re-verify a new address on a
neighborhood network), so the downside of tripping bot detection here is
worse, and I have no way to validate a scraper against it from this build
environment anyway. If you want real Nextdoor automation in a later
stage, the same `storage_state`-persistence pattern used for Facebook
would be the starting point — budget time for UI reverse-engineering and
accept the account risk described above.

Format for `data/nextdoor_manual_inbox.md`:

```
## Free sectional, must go this week
url: https://nextdoor.com/p/abc123
price: free
location: Jamaica Plain
posted: 2026-09-17T08:00:00
---
Moving out Sunday, must pick up. Great condition sectional, you haul.
---
```

Stack as many entries as you want; stale ones just fall out on the next
run via the 24-hour freshness filter.

## Scheduling

Nothing in this repo schedules itself — stage 1 is a CLI you point cron
(or launchd, systemd timer, etc.) at. Example, every 4 hours:

```
0 */4 * * * cd /path/to/boston-flipper-bot && .venv/bin/python -m boston_flipper.cli run >> logs/cron.log 2>1
```

**Run this somewhere with a persistent filesystem and normal internet
access** — a laptop, a small always-on server, or a VPS. It needs to be
able to reach facebook.com/craigslist.org/nextdoor.com directly, and it
needs `data/sessions/facebook_storage_state.json` to still be there
between runs (an ephemeral/container environment that resets on every run
won't work for the Facebook source, since you'd be re-doing the manual
login every single time).

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

27 unit tests cover the hard filters, scoring math, the Craigslist HTML
parser (against a saved fixture page), the Nextdoor manual-inbox parser,
and distance resolution. None of them touch the network.

## What I could not verify, and what to check on your end

This was built in a sandboxed environment with **no outbound network
access to Craigslist, Facebook, or Nextdoor** (only package registries).
So:

- **I could not run this against live data.** I proved the pipeline
  works end-to-end using synthetic/fixture listings (see
  `examples/sample_digest.md`, generated by
  `scripts/generate_sample_digest.py`) and unit tests, but the actual
  scrapers have not touched real Craigslist/Facebook/Nextdoor pages.
- **You should run `python -m boston_flipper.cli run --sources craigslist`
  first**, since it needs no login and is the most likely to work
  unmodified. Check `output/latest.md` for real candidates.
- **Craigslist selectors may need a small tweak.** They're written
  against Craigslist's markup as I know it, but I'd treat the first live
  run as a "does this return anything" smoke test. If it returns zero
  results across all categories, that's the signal to inspect a saved
  search-results page and adjust the selectors in
  `boston_flipper/sources/craigslist.py::_extract_result_nodes` /
  `_first_text`.
- **Facebook needs the most hands-on setup and the most patience**: run
  `scripts/capture_facebook_session.py`, then
  `python -m boston_flipper.cli run --sources facebook --fb-headed` once
  to watch it work (or fail) in a visible browser and iterate on
  selectors in `boston_flipper/sources/facebook.py` if the card
  parsing (`_parse_card_text`) comes back empty or garbled.
- **The geocoding is a static town-name lookup table**
  (`boston_flipper/config.py::TOWN_CENTROIDS`), not a real geocoder —
  it's dependency-free and good enough for a ~15-mile radius check, but
  if a listing's location text doesn't match a known town name it fails
  the distance filter (fails closed, not open). Add towns to that table
  as you notice good listings getting dropped for "could not determine
  distance."
- **The photo-quality-gap score is a heuristic, not real image
  analysis** — it scores off photo *count* only (fewer photos = more
  points), as a proxy for "might be underpriced because the listing
  looks low-effort." Actual visual quality assessment (blur/lighting
  detection) would be a reasonable stage 2+ enhancement if this proxy
  turns out to be too noisy in practice.

## Explicitly out of scope for stage 1

No seller messaging, no relisting, no GoShare/logistics integration, no
payment handling. Those are later stages per the project brief.
