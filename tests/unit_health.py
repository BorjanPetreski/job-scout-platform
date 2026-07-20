#!/usr/bin/env python3
"""Unit coverage for core/health.py — the Layer-1 mechanical health signals (the "scripts
flag" half of Platform Health). compute_health() is pure in→out over runs.json-shaped
telemetry, so this is the cheap high-value coverage validate.py can't give: it proves each
signal actually fires on the shape it's meant to and stays quiet otherwise — especially
SELECTOR_SUSPECT, the silent 200-parses-0 break that source_down alone misses."""
from __future__ import annotations

import sys

from _harness import Suite
import health

# Tight thresholds so small fixtures exercise every branch deterministically.
TH = {"window": 8, "down_streak": 3, "yield_collapse_factor": 0.25,
      "min_baseline": 6, "never_produced_min_runs": 4, "systemic_frac": 0.7}


def _stat(raw, source_down=False, http_ok=None):
    # http_ok defaults to "reached unless it went hard-down" — mirrors the scan recorder
    return {"raw": raw, "source_down": source_down,
            "http_ok": (not source_down) if http_ok is None else http_ok}


def _runs(*run_stats: dict) -> dict:
    """Build a runs.json-shaped dict from an ordered list of {platform: stat} runs."""
    runs: dict = {"recompute": {"last": "2026-07-01", "sessions_since": 1}}
    for i, ps in enumerate(run_stats):
        day = f"2026-07-{i + 1:02d}"
        runs[day] = {"AM": {"ran_at": f"{day}T08:00:00+00:00", "platform_stats": ps,
                            "platforms_covered": [n for n, s in ps.items() if not s["source_down"]],
                            "sources_down": [n for n, s in ps.items() if s["source_down"]]}}
    return runs


def _flags(report, platform):
    return sorted(f["flag"] for f in report["findings"] if f["platform"] == platform)


def main() -> list[str]:
    s = Suite("health signals")

    # SELECTOR_SUSPECT — the silent break: reached (http_ok) but 0 rows, historically many ----
    healthy_hist = _stat(20)
    sel = compute = health.compute_health(
        _runs({"BoardA": healthy_hist}, {"BoardA": healthy_hist}, {"BoardA": healthy_hist},
              {"BoardA": _stat(0, source_down=True, http_ok=True)}),  # 200 but parsed 0
        active_names=["BoardA"], thresholds=TH)
    s.eq(_flags(sel, "BoardA"), ["SELECTOR_SUSPECT"],
         "SELECTOR_SUSPECT: 200-parses-0 after a rich history -> flag")

    # a board that produces 0 but was NEVER rich enough (below min_baseline) must NOT flag -----
    thin = health.compute_health(
        _runs({"B": _stat(3)}, {"B": _stat(2)}, {"B": _stat(0, source_down=True, http_ok=True)}),
        active_names=["B"], thresholds=TH)
    s.eq(_flags(thin, "B"), [], "SELECTOR_SUSPECT: thin history (median < min_baseline) -> quiet")

    # DOWN_STREAK — hard down (never reached) N in a row; must NOT be called a selector break --
    down = health.compute_health(
        _runs({"C": _stat(0, source_down=True)}, {"C": _stat(0, source_down=True)},
              {"C": _stat(0, source_down=True)}),
        active_names=["C"], thresholds=TH)
    s.eq(_flags(down, "C"), ["DOWN_STREAK"], "DOWN_STREAK: hard-down 3 in a row -> flag")

    # 2 downs is below the streak threshold -> quiet ------------------------------------------
    two = health.compute_health(
        _runs({"C": _stat(5)}, {"C": _stat(0, source_down=True)}, {"C": _stat(0, source_down=True)}),
        active_names=["C"], thresholds=TH)
    s.eq(_flags(two, "C"), [], "DOWN_STREAK: only 2 in a row -> quiet")

    # YIELD_COLLAPSE — still producing but far below trailing median ---------------------------
    coll = health.compute_health(
        _runs({"D": _stat(40)}, {"D": _stat(38)}, {"D": _stat(42)}, {"D": _stat(3)}),
        active_names=["D"], thresholds=TH)
    s.eq(_flags(coll, "D"), ["YIELD_COLLAPSE"],
         "YIELD_COLLAPSE: raw 3 vs median 40 -> flag")

    # a normal dip (above the collapse floor) must NOT flag ------------------------------------
    dip = health.compute_health(
        _runs({"D": _stat(40)}, {"D": _stat(38)}, {"D": _stat(42)}, {"D": _stat(30)}),
        active_names=["D"], thresholds=TH)
    s.eq(_flags(dip, "D"), [], "YIELD_COLLAPSE: shallow dip -> quiet")

    # NEVER_PRODUCED — active, reached across many runs, zero candidates ever ------------------
    never = health.compute_health(
        _runs({"E": _stat(0)}, {"E": _stat(0)}, {"E": _stat(0)}, {"E": _stat(0)}),
        active_names=["E"], thresholds=TH)
    s.eq(_flags(never, "E"), ["NEVER_PRODUCED"],
         "NEVER_PRODUCED: active + reached + always 0 -> flag")

    # ...but NOT if the board isn't in the active set (unknown scope) --------------------------
    never_inactive = health.compute_health(
        _runs({"E": _stat(0)}, {"E": _stat(0)}, {"E": _stat(0)}, {"E": _stat(0)}),
        active_names=[], thresholds=TH)
    s.eq(_flags(never_inactive, "E"), [], "NEVER_PRODUCED: not in active set -> quiet")

    # SYSTEMIC — most active boards at ~0 in the latest run: one cause, not N symptoms ---------
    good = {f"P{i}": _stat(10) for i in range(5)}
    bad = {f"P{i}": _stat(0, source_down=True) for i in range(5)}  # all 5 down at once
    sysrep = health.compute_health(_runs(good, good, good, bad),
                                   active_names=list(good), thresholds=TH)
    sys_flags = [f["flag"] for f in sysrep["findings"]]
    s.ok("SYSTEMIC" in sys_flags, "SYSTEMIC: 5/5 boards ~0 in latest run -> flag")
    s.ok(sys_flags.count("DOWN_STREAK") == 0,
         "SYSTEMIC: per-board DOWN_STREAK suppressed (symptoms of the one cause)")

    # a healthy history returns no findings ---------------------------------------------------
    ok = health.compute_health(_runs({"H": _stat(12)}, {"H": _stat(14)}, {"H": _stat(11)}),
                               active_names=["H"], thresholds=TH)
    s.ok(ok["healthy"] and not ok["findings"], "healthy history -> no findings")

    # empty telemetry is healthy, not a crash ------------------------------------------------
    empty = health.compute_health({"recompute": {}}, active_names=[], thresholds=TH)
    s.ok(empty["healthy"] and empty["runs_analyzed"] == 0, "no runs -> healthy, 0 analyzed")

    # legacy runs (no platform_stats) still yield DOWN_STREAK from covered/down lists ----------
    legacy = {"2026-07-01": {"AM": {"ran_at": "2026-07-01T08:00:00+00:00",
                                    "platforms_covered": [], "sources_down": ["L"]}},
              "2026-07-02": {"AM": {"ran_at": "2026-07-02T08:00:00+00:00",
                                    "platforms_covered": [], "sources_down": ["L"]}},
              "2026-07-03": {"AM": {"ran_at": "2026-07-03T08:00:00+00:00",
                                    "platforms_covered": [], "sources_down": ["L"]}}}
    leg = health.compute_health(legacy, active_names=["L"], thresholds=TH)
    s.eq(_flags(leg, "L"), ["DOWN_STREAK"], "legacy telemetry: DOWN_STREAK from sources_down")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
