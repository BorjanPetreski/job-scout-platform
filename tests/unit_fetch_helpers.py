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

    # --- fetch_all: concurrency caps + order preservation (stubbed fetch_platform, no network).
    # Deliberately queues MORE than each cap in BOTH groups — a bug that leaves one group
    # unbounded (e.g. a pool sized by input count instead of the real cap; this exact bug
    # shipped once, caught only because a fresh run with >12 HTTP platforms queued was tried)
    # is invisible with too few tasks to ever hit the ceiling. ------------------------------
    lock = threading.Lock()
    concurrent_headless = concurrent_http = 0
    max_concurrent_headless_seen = max_concurrent_http_seen = 0
    orig_fetch_platform = fb.fetch_platform

    def fake_fetch_platform(p, cfg):
        nonlocal concurrent_headless, concurrent_http, max_concurrent_headless_seen, max_concurrent_http_seen
        is_h = fb._is_headless_platform(p)
        with lock:
            if is_h:
                concurrent_headless += 1
                max_concurrent_headless_seen = max(max_concurrent_headless_seen, concurrent_headless)
            else:
                concurrent_http += 1
                max_concurrent_http_seen = max(max_concurrent_http_seen, concurrent_http)
        time.sleep(0.02)
        with lock:
            if is_h:
                concurrent_headless -= 1
            else:
                concurrent_http -= 1
        return {"platform": p["name"], "candidates": [], "source_down": False, "note": ""}

    fb.fetch_platform = fake_fetch_platform
    try:
        n_headless, n_http = fb.MAX_CONCURRENT_HEADLESS * 3, fb.MAX_CONCURRENT_HTTP * 2
        platforms = ([{"slug": f"headless-{i}", "name": f"H{i}", "id": i, "tier": 1,
                        "active": True, "fetch_mode": "headless"} for i in range(n_headless)]
                     + [{"slug": f"api-{i}", "name": f"A{i}", "id": 100 + i, "tier": 2,
                         "active": True, "fetch_mode": "api"} for i in range(n_http)])
        results = fb.fetch_all({"platforms": platforms})
        s.eq([r["platform"] for r in results],
             [f"H{i}" for i in range(n_headless)] + [f"A{i}" for i in range(n_http)],
             "fetch_all: output order matches tier-sort order, not completion order")
        s.ok(max_concurrent_headless_seen <= fb.MAX_CONCURRENT_HEADLESS,
             f"fetch_all: headless concurrency never exceeded its cap "
             f"(saw {max_concurrent_headless_seen}, cap {fb.MAX_CONCURRENT_HEADLESS})")
        s.eq(max_concurrent_headless_seen, fb.MAX_CONCURRENT_HEADLESS,
             f"fetch_all: with {n_headless} headless platforms queued, its cap is actually "
             "reached (proves it's a real bound, not accidentally unconstrained)")
        s.ok(max_concurrent_http_seen <= fb.MAX_CONCURRENT_HTTP,
             f"fetch_all: HTTP concurrency never exceeded its cap "
             f"(saw {max_concurrent_http_seen}, cap {fb.MAX_CONCURRENT_HTTP}) — regression "
             "guard for the bug where this pool was sized by len(platforms) instead of the cap")
        s.eq(max_concurrent_http_seen, fb.MAX_CONCURRENT_HTTP,
             f"fetch_all: with {n_http} HTTP platforms queued, its cap is actually reached")
    finally:
        fb.fetch_platform = orig_fetch_platform

    # --- jobgether_should_continue: found 2026-07-21 (manual platform audit) — Jobgether
    # paginates at 50/page but the generic single-fetch harvester only ever saw page 1, a 3x
    # undercount for any category exceeding 50 live postings. The stop-rule deliberately
    # ignores Jobgether's own total/maxPages counters (proved unreliable live: maxPages
    # undercounts a big worldwide listing, total was flat-out wrong — 134,141 — for a
    # different category) in favor of real page content, pinned here in isolation from the
    # HTTP fetch, same split as himalayas_pages_for_gap.
    s.ok(fb.jobgether_should_continue(50, 50, 1),
         "page full of all-new links, under the ceiling -> keep going")
    s.ok(not fb.jobgether_should_continue(0, 0, 1),
         "empty page (real end of data, confirmed live at Jobgether's page 34) -> stop")
    s.ok(not fb.jobgether_should_continue(50, 0, 2),
         "page had content but nothing NEW (redirect/param-drop loop-back case) -> stop, "
         "never spin on duplicate content")
    s.ok(not fb.jobgether_should_continue(50, 50, fb.JOBGETHER_MAX_PAGES),
         "at the safety ceiling -> stop regardless of yield, never runaway")
    s.ok(fb.jobgether_should_continue(6, 6, fb.JOBGETHER_MAX_PAGES - 1),
         "one page short of the ceiling with real new content -> still continues")

    # --- dynamite_title_company: found 2026-07-21 (manual platform audit, Borjan's live
    # find) — Dynamite Jobs' category URL was wrong (301'd to the homepage) AND its listings
    # load in scroll-triggered batches a plain headless render can't get past. Switched to
    # their public sitemap, which usually carries a "Company - Title (remote job)" caption;
    # pins the pure caption parse in isolation from the HTTP fetch.
    s.eq(fb.dynamite_title_company(
        "Alyssa Nobriga - Program Manager — Academic Programs &amp; Master’s Pathway (remote job)",
        "https://dynamitejobs.com/company/alyssanobriga/remote-job/program-manager-x"),
        ("Program Manager — Academic Programs & Master’s Pathway", "Alyssa Nobriga"),
        "real caption -> (title, company), HTML entities unescaped, trailing '(remote job)' stripped")
    s.eq(fb.dynamite_title_company(
        "ClickGUARD Inc. - GTM Engineer - Demand Generation (remote job)",
        "https://dynamitejobs.com/company/clickguard/remote-job/gtm-engineer"),
        ("GTM Engineer - Demand Generation", "ClickGUARD Inc."),
        "a title that itself contains ' - ' -> splits on the FIRST separator only "
        "(company can never contain it, titles sometimes do)")
    s.eq(fb.dynamite_title_company(None,
        "https://dynamitejobs.com/company/novantro/remote-job/coo"),
        ("coo", ""),
        "no caption (2026-07-21 sample: ~5% of entries) -> falls back to the URL slug, "
        "empty company rather than a guess")
    s.eq(fb.dynamite_title_company("malformed caption with no separator",
        "https://dynamitejobs.com/company/x/remote-job/some-role"),
        ("some role", ""),
        "caption present but doesn't match the expected 'Company - Title' shape -> "
        "falls back to the URL slug (_slug_title) rather than misparsing")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
