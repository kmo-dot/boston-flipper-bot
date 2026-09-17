"""Renders a run's candidates into a markdown digest file."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .models import Candidate


def _fmt_age(posted_at) -> str:
    if posted_at is None:
        return "unknown"
    now = datetime.now(timezone.utc)
    posted = posted_at if posted_at.tzinfo else posted_at.replace(tzinfo=timezone.utc)
    delta = now - posted
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{int(delta.total_seconds() / 60)} min ago"
    return f"{hours:.1f} hr ago"


def _fmt_price(candidate: Candidate) -> str:
    listing = candidate.listing
    return "FREE" if listing.is_free else f"${listing.price:.0f}"


def render_digest(candidates: list[Candidate], run_time: datetime | None = None,
                   source_errors: dict[str, str] | None = None,
                   source_counts: dict[str, int] | None = None) -> str:
    run_time = run_time or datetime.now(timezone.utc)
    lines: list[str] = []
    lines.append(f"# Boston Flipperbot Digest — {run_time.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append(f"**{len(candidates)} candidate(s)** passed all hard filters this run.")
    lines.append("")

    if source_counts:
        lines.append("## Run summary")
        for source, count in sorted(source_counts.items()):
            lines.append(f"- {source}: {count} listing(s) fetched")
        lines.append("")

    if source_errors:
        lines.append("## Source errors this run")
        for source, err in sorted(source_errors.items()):
            lines.append(f"- **{source}**: {err}")
        lines.append("")

    if not candidates:
        lines.append("_No candidates cleared all hard filters this run._")
        return "\n".join(lines) + "\n"

    ranked = sorted(candidates, key=lambda c: c.score.total, reverse=True)

    lines.append("## Candidates (ranked by score)")
    lines.append("")

    for i, c in enumerate(ranked, start=1):
        listing = c.listing
        top_factors = c.score.top_factors(3)
        factors_str = ", ".join(f"{name} ({val:+.1f})" for name, val in top_factors)
        distance_str = (
            f"{c.filter_result.distance_miles:.1f} mi"
            if c.filter_result.distance_miles is not None
            else "unknown"
        )

        lines.append(f"### {i}. {listing.title}")
        lines.append("")
        lines.append(f"- **Category:** {c.filter_result.category}")
        lines.append(f"- **Price:** {_fmt_price(c)}")
        lines.append(f"- **Platform:** {listing.source} — [listing link]({listing.url})")
        lines.append(f"- **Score:** {c.score.total:.1f}/100 — top factors: {factors_str}")
        lines.append(f"- **Distance:** {distance_str}")
        lines.append(f"- **Posted:** {_fmt_age(listing.posted_at)}")
        lines.append(f"- **Location (as posted):** {listing.location_text or 'n/a'}")
        if c.filter_result.matched_friction_phrases:
            lines.append(
                f"- **Pickup-friction signals:** "
                f"{', '.join(c.filter_result.matched_friction_phrases)}"
            )
        lines.append("")
        lines.append("**Verbatim listing text:**")
        lines.append("")
        lines.append("> " + listing.description.replace("\n", "\n> "))
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_digest(candidates: list[Candidate], output_dir: str,
                  run_time: datetime | None = None,
                  source_errors: dict[str, str] | None = None,
                  source_counts: dict[str, int] | None = None) -> str:
    run_time = run_time or datetime.now(timezone.utc)
    os.makedirs(output_dir, exist_ok=True)
    filename = f"digest_{run_time.strftime('%Y%m%d_%H%M%S')}.md"
    path = os.path.join(output_dir, filename)
    content = render_digest(
        candidates, run_time=run_time,
        source_errors=source_errors, source_counts=source_counts,
    )
    with open(path, "w") as f:
        f.write(content)

    latest_path = os.path.join(output_dir, "latest.md")
    with open(latest_path, "w") as f:
        f.write(content)

    return path
