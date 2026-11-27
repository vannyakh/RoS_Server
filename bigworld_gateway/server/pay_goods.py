"""Diamond amounts for original-client IAP bids (Top-up > General and related tabs).

The client sends a goods `bid` string when starting a purchase. On a private server we grant
`ingot + ingot_send` without a real payment provider. Known General-tab packs (LIMITED EXTRA 50%)
are listed by bid suffix; anything else falls back to a numeric bid or the smallest pack.
"""

import re

# (ingot, ingot_send) — matches onConfirmPayOrder and the General-tab bonus labels.
_BY_TOTAL = {
    90: (60, 30),
    185: (125, 60),
    280: (190, 90),
    470: (320, 150),
    960: (660, 300),
    1980: (1380, 600),
    5060: (3560, 1500),
    10380: (7380, 3000),
}

# Common NetEase-style product suffixes seen on Ros builds (bid may be a long product id).
_SUFFIX_PACKS = {
    "60": (60, 30),
    "120": (120, 60),
    "180": (180, 90),
    "300": (300, 150),
    "600": (600, 300),
    "1200": (1200, 600),
    "3000": (3000, 1500),
    "6000": (6000, 3000),
}


def diamonds_for_bid(bid: str) -> tuple[int, int]:
    """Return (ingot, ingot_send) for a Top-up goods bid string."""
    text = (bid or "").strip()
    if not text:
        return 60, 30
    if text in _SUFFIX_PACKS:
        return _SUFFIX_PACKS[text]
    digits = re.findall(r"\d+", text)
    for part in reversed(digits):
        n = int(part)
        if n in _SUFFIX_PACKS:
            return _SUFFIX_PACKS[n]
        if n in _BY_TOTAL:
            return _BY_TOTAL[n]
        if 10 <= n <= 50_000:
            bonus = n // 2 if n in (60, 120, 180, 300, 600, 1200, 3000, 6000) else max(n // 5, 0)
            return n, bonus
    return 60, 30