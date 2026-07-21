#!/usr/bin/env python3
"""Unit coverage for core/arch_review.py — the DoD #5 "architecture review due" cadence
counter (2026-07-21). Pure dict-in/dict-out logic (bump/is_due/ack + the nudge line), same
shape as health.py's counter, so it's the cheap high-value coverage: prove the counter
accrues, trips at the threshold, and resets on ack — the mechanical half of the judgment gate."""
from __future__ import annotations

import sys

from _harness import Suite
import arch_review as ar


def main() -> list[str]:
    s = Suite("arch_review cadence counter")

    # bump: creates the block on first run, then increments in place ---------------------------
    runs: dict = {}
    block = ar.bump(runs, due_default=10)
    s.eq(block["sessions_since"], 1, "bump on empty runs creates the counter at 1")
    s.eq(block["due_at_sessions"], 10, "bump seeds due_at_sessions from the passed default")
    s.ok("arch_review" in runs and runs["arch_review"] is block, "bump mutates runs in place")
    for _ in range(4):
        ar.bump(runs, due_default=10)
    s.eq(runs["arch_review"]["sessions_since"], 5, "five bumps -> sessions_since 5")

    # is_due: trips only at/after the threshold ------------------------------------------------
    s.ok(not ar.is_due(runs["arch_review"]), "5 < 10 -> not due")
    runs["arch_review"]["sessions_since"] = 9
    s.ok(not ar.is_due(runs["arch_review"]), "9 < 10 -> still not due")
    runs["arch_review"]["sessions_since"] = 10
    s.ok(ar.is_due(runs["arch_review"]), "10 >= 10 -> due")
    runs["arch_review"]["sessions_since"] = 14
    s.ok(ar.is_due(runs["arch_review"]), "14 >= 10 -> due")

    # a profile that overrides due_at_sessions is honoured over the default --------------------
    s.ok(ar.is_due({"sessions_since": 3, "due_at_sessions": 3}, due_default=10),
         "an explicit smaller due_at_sessions trips earlier than the default")
    s.ok(not ar.is_due({"sessions_since": 3}, due_default=10),
         "no due_at_sessions -> falls back to the passed default (3 < 10)")

    # ack: resets to 0 and stamps a date -------------------------------------------------------
    acked = ar.ack(runs)
    s.eq(acked["sessions_since"], 0, "ack resets sessions_since to 0")
    s.ok(bool(acked.get("last")), "ack stamps a 'last' date")
    s.ok(not ar.is_due(runs["arch_review"]), "after ack the counter is no longer due")

    # nudge line names the cadence + the ack command (Claude's cue to ASSESS, not to obey) -----
    line = ar.nudge_line({"sessions_since": 12, "last": "2026-07-21", "due_at_sessions": 10})
    s.ok("12" in line and "DoD #5" in line and "--ack" in line,
         "nudge_line reports the count, cites DoD #5, and points at the ack command")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
