<!--
Nextdoor manual inbox.

Nextdoor listings aren't scraped automatically in stage 1 (see
boston_flipper/sources/nextdoor.py for why). Instead, when you spot a
bulky-item post on Nextdoor, paste it below in this format before running
the digest. NOTE: the format below is shown inside a code fence
(indented with backticks) specifically so it does NOT get parsed as a
real entry itself -- when you add a real entry, it must start at the
left margin with a line beginning "## " (no leading backticks/spaces).

    ## <title, e.g. "Free sectional couch">
    url: <link to the post, or n/a if you don't have one>
    price: <amount, or "free">
    location: <neighborhood/town>
    posted: <ISO datetime like 2026-09-16T14:30:00, or relative like "3 hours ago">
    ---
    <paste the verbatim listing text here>
    ---

You can stack as many real entries as you want below this comment block.
Delete entries after each run (or leave them -- stale ones just get
dropped by the 24h freshness filter automatically).
-->
