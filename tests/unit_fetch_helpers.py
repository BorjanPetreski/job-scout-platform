#!/usr/bin/env python3
"""Unit coverage for pure sizing/parsing helpers in core/fetch_boards.py — logic that decides
HOW MUCH to fetch or WHAT counts as a posting, kept separate from the actual HTTP/render I/O
(which stays outside unit-test scope per tests/README.md's honest-failure doctrine).

himalayas_pages_for_gap: found 2026-07-20 during a platform-health low-yield sweep — a fixed
1000-job pagination window left a real blind spot after a multi-day scan gap (real borjan-pm
gaps ranged 5-98h, while the window only reached ~10h back at the site's observed posting
rate). This pins the sizing math (floor/ceiling/scaling) so a future tweak can't silently
reintroduce either failure mode: too few pages after a long gap, or runaway fetch time.

fetch_all concurrency (2026-07-21): platform fetching went from strictly sequential to
bounded-concurrent (a slower/deeper scan was taking noticeably longer wall-clock). Pins two
invariants a future tweak could silently break: the headless (Playwright) group never exceeds
MAX_CONCURRENT_HEADLESS regardless of how many are active, and the returned list always
matches tier-sort order regardless of which platform's fetch actually finished first."""
from __future__ import annotations

import sys
import threading
import time

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
    s.eq(fb.himalayas_pages_for_gap(200), fb.HIMALAYAS_MAX_PAGES,
         "gap=200h -> capped at the ceiling")
    s.eq(fb.himalayas_pages_for_gap(10_000), fb.HIMALAYAS_MAX_PAGES,
         "an absurd gap -> still capped, never runaway")

    # never negative / never below the floor even for a bogus negative input ----------------
    s.eq(fb.himalayas_pages_for_gap(-5), fb.HIMALAYAS_MIN_PAGES,
         "negative gap (clock skew/bad input) -> floor, not a crash or 0")

    # --- _is_headless_platform: classification drives which concurrency group a platform
    # lands in, so it has to be right ---------------------------------------------------------
    s.ok(fb._is_headless_platform({"slug": "nodesk", "fetch_mode": "headless"}),
         "fetch_mode=headless, not a HANDLERS entry -> headless group")
    s.ok(fb._is_headless_platform({"slug": "landing-jobs", "fetch_mode": "headless_scroll"}),
         "fetch_mode=headless_scroll -> headless group")
    s.ok(not fb._is_headless_platform({"slug": "greenhouse", "fetch_mode": "api"}),
         "a HANDLERS entry -> HTTP group regardless of fetch_mode")
    s.ok(not fb._is_headless_platform({"slug": "himalayas", "fetch_mode": "direct"}),
         "himalayas: fetch_mode=direct label, but IS a HANDLERS entry -> HTTP group, not headless")
    s.ok(not fb._is_headless_platform({"slug": "wttj", "fetch_mode": "direct"}),
         "fetch_mode=direct, not a HANDLERS entry -> HTTP group (occasional escalation, not steady-state)")

    # --- fetch_all: concurrency cap + order preservation (stubbed fetch_platform, no network) -
    lock = threading.Lock()
    concurrent_headless = 0
    max_concurrent_headless_seen = 0
    orig_fetch_platform = fb.fetch_platform

    def fake_fetch_platform(p, cfg):
        nonlocal concurrent_headless, max_concurrent_headless_seen
        is_h = fb._is_headless_platform(p)
        if is_h:
            with lock:
                concurrent_headless += 1
                max_concurrent_headless_seen = max(max_concurrent_headless_seen, concurrent_headless)
        time.sleep(0.02)
        if is_h:
            with lock:
                concurrent_headless -= 1
        return {"platform": p["name"], "candidates": [], "source_down": False, "note": ""}

    fb.fetch_platform = fake_fetch_platform
    try:
        platforms = ([{"slug": f"headless-{i}", "name": f"H{i}", "id": i, "tier": 1,
                        "active": True, "fetch_mode": "headless"} for i in range(12)]
                     + [{"slug": f"api-{i}", "name": f"A{i}", "id": 100 + i, "tier": 2,
                         "active": True, "fetch_mode": "api"} for i in range(6)])
        results = fb.fetch_all({"platforms": platforms})
        s.eq([r["platform"] for r in results], [f"H{i}" for i in range(12)] + [f"A{i}" for i in range(6)],
             "fetch_all: output order matches tier-sort order, not completion order")
        s.ok(max_concurrent_headless_seen <= fb.MAX_CONCURRENT_HEADLESS,
             f"fetch_all: headless concurrency never exceeded the cap "
             f"(saw {max_concurrent_headless_seen}, cap {fb.MAX_CONCURRENT_HEADLESS})")
        s.eq(max_concurrent_headless_seen, fb.MAX_CONCURRENT_HEADLESS,
             "fetch_all: with 12 headless platforms queued, the cap is actually reached "
             "(proves it's a real bound, not accidentally unconstrained)")
    finally:
        fb.fetch_platform = orig_fetch_platform

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
