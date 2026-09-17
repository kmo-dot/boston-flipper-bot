"""Command-line entrypoint.

    python -m boston_flipper.cli run
    python -m boston_flipper.cli run --sources craigslist,nextdoor
    python -m boston_flipper.cli run --no-facebook-details
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import config
from .pipeline import run_pipeline
from .sources.craigslist import CraigslistSource
from .sources.facebook import FacebookMarketplaceSource
from .sources.nextdoor import NextdoorManualSource

ALL_SOURCE_NAMES = ["craigslist", "facebook", "nextdoor"]


def build_sources(names: list[str], fb_headless: bool, fb_details: bool) -> list:
    sources = []
    for name in names:
        if name == "craigslist":
            sources.append(CraigslistSource())
        elif name == "facebook":
            sources.append(
                FacebookMarketplaceSource(headless=fb_headless, visit_detail_pages=fb_details)
            )
        elif name == "nextdoor":
            sources.append(NextdoorManualSource())
        else:
            raise ValueError(f"unknown source: {name}")
    return sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boston-flipperbot")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="fetch all sources and write a digest")
    run_p.add_argument(
        "--sources", default=",".join(ALL_SOURCE_NAMES),
        help="comma-separated list of sources to run (default: all)",
    )
    run_p.add_argument("--output-dir", default=config.OUTPUT_DIR)
    run_p.add_argument(
        "--fb-headed", action="store_true",
        help="run Facebook's browser with a visible window (useful for debugging)",
    )
    run_p.add_argument(
        "--no-fb-details", action="store_true",
        help="skip visiting each Facebook listing's detail page (faster, but no timestamp/description)",
    )
    run_p.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        names = [n.strip() for n in args.sources.split(",") if n.strip()]
        sources = build_sources(
            names, fb_headless=not args.fb_headed, fb_details=not args.no_fb_details
        )
        path = run_pipeline(sources, output_dir=args.output_dir)
        print(f"Digest written to {path}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
