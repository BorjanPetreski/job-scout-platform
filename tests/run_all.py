#!/usr/bin/env python3
"""Behavioral test entry point — runs the unit suites (pure logic) + the acceptance sims
(cross-boundary flows vs mocked Notion) and exits non-zero if any fails. Wired into CI
alongside core/validate.py: validate.py is the STRUCTURAL gate (compiles/resolves), this is
the BEHAVIORAL gate (the detectors/dedup/sync actually return the right answers).

Each target runs as its own subprocess so a sim's module-global monkeypatching (ns._req, …)
can't leak into another target. Run: python3 tests/run_all.py"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    ("unit: scan detectors", "tests/unit_detectors.py"),
    ("unit: dedup helpers", "tests/unit_dedup.py"),
    ("unit: health signals", "tests/unit_health.py"),
    ("sim: reconcile new-tracker box", "sims/reconcile_new_tracker_box.py"),
    ("sim: twin-row dedup", "sims/twin_row_dedup.py"),
]


def main() -> int:
    failed: list[str] = []
    for name, rel in TARGETS:
        print(f"\n{'=' * 70}\n=== {name}  ({rel})\n{'=' * 70}")
        r = subprocess.run([sys.executable, str(ROOT / rel)])
        if r.returncode != 0:
            failed.append(name)
    print("\n" + "=" * 70)
    if failed:
        print(f"BEHAVIORAL TESTS FAILED: {len(failed)} target(s): {failed}")
        return 1
    print(f"BEHAVIORAL TESTS PASSED: {len(TARGETS)} targets green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
