#!/usr/bin/env python3
"""One-time (well, occasional) interactive login to capture a Facebook
session for the scraper to reuse.

Why this instead of storing a username/password:
  - No credentials ever touch the repo, .env, or any config file.
  - We never script the login form itself. Typing a password into a
    headless-automated form field is one of the most reliable ways to get
    a Facebook account flagged for suspicious activity; logging in by
    hand in a real, visible browser window looks exactly like a human
    logging in, because it is one.
  - The tradeoff: Facebook sessions expire (device/session policy,
    inactivity, a password change, a security check, etc.), so you'll
    need to re-run this occasionally -- there's no fixed schedule, you'll
    know it's time when scheduled runs start logging
    "no Facebook session found" or "0 listings from facebook".

Usage:
    python scripts/capture_facebook_session.py

A real Chromium window opens to facebook.com. Log in normally (including
2FA if prompted), navigate to Marketplace once to confirm you're in, then
come back to the terminal and press Enter. The session (cookies + local
storage) is saved to data/sessions/facebook_storage_state.json, which the
scraper (boston_flipper/sources/facebook.py) loads on every run.

That file is a live login session -- treat it like a password. It's
git-ignored by default (see .gitignore); don't commit it or share it.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from boston_flipper import config  # noqa: E402


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is not installed. Run:\n  pip install playwright\n  playwright install chromium")
        return 1

    out_path = config.FACEBOOK_STORAGE_STATE_PATH
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.facebook.com/marketplace/")

        print()
        print("A browser window has opened.")
        print("1. Log in to Facebook normally (handle 2FA if asked).")
        print("2. Click into Marketplace to confirm you're logged in and it loads listings.")
        print("3. Come back here and press Enter to save the session.")
        input()

        context.storage_state(path=out_path)
        browser.close()

    print(f"Session saved to {out_path}")
    print("Re-run this script whenever the scraper reports 0 Facebook listings / login errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
