#!/usr/bin/env python3
"""Unit coverage for pure sizing/parsing helpers in core/fetch_boards.py — logic that decides
HOW MUCH to fetch or WHAT counts as a posting, kept separate from the actual HTTP/render I/O
(which stays outside unit-test scope per tests/README.md's honest-failure doctrine).

himalayas_pages_for_gap: found 2026-07-20 during a platform-health low-yield sweep — a fixed
1000-job pagination window left a real blind spot after a multi-day scan gap (real borjan-pm
gaps ranged 5-98h, while the window only reached ~10h back at the site's observed posting
rate). This pins the sizing math (floor/ceiling/scaling) so a future tweak can't silently
reintroduce either failure mode: too few pages after a long gap, or runaway fetch time."""
from __future__ import annotations

import sys

from _harness import Suite
import fetch_boards as fb


def main() -> list[str]:
    s = Suite("fetch_boards helpers")

    # floor — a fresh/short gap still gets the minimum sample, never fewer pages -------------
    s.eq(fb.himalayas_pages_for_gap(0), fb.HIMALAYAS_MIN_PAGES,
         "gap=0h -> floor (never zero pages)")
    s.eq(fb.himalayas_pages_for_gap(5), fb.HIMALAYAS_MIN_PAGES,
         "gap=5h -> still floor (5h * 100/h * 1.5 = 750 jobs < 1000 floor)")

    # scales with the gap once it exceeds what the floor already covers ---------------------
    s.ok(fb.himalayas_pages_for_gap(22) > fb.HIMALAYAS_MIN_PAGES,
         "gap=22h -> more than the floor")
    s.ok(fb.himalayas_pages_for_gap(33) > fb.himalayas_pages_for_gap(22),
         "larger gap -> more pages (monotonic)")

    # ceiling — a huge gap (multi-day skip) never blows up unbounded -------------------------
    s.eq(fb.himalayas_pages_for_gap(98), fb.HIMALAYAS_MAX_PAGES,
         "gap=98h -> capped at the ceiling")
    s.eq(fb.himalayas_pages_for_gap(10_000), fb.HIMALAYAS_MAX_PAGES,
         "an absurd gap -> still capped, never runaway")

    # never negative / never below the floor even for a bogus negative input ----------------
    s.eq(fb.himalayas_pages_for_gap(-5), fb.HIMALAYAS_MIN_PAGES,
         "negative gap (clock skew/bad input) -> floor, not a crash or 0")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
