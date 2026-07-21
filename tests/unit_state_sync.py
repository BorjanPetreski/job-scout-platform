#!/usr/bin/env python3
"""Unit coverage for core/state_sync.py's pure push-failure classification.

_is_push_race (2026-07-21): found during a full architecture regression pass — push()'s
retry loop used to treat EVERY non-zero push return code as "someone else pushed in
between" and retry via pull()+push, up to 4 times with backoff. Auth failures,
protected-branch rejections, and network errors aren't races pull() can fix — retrying
them just burns 4 attempts before failing with the same unfixable error."""
from __future__ import annotations

import json
import sys

from _harness import Suite
import state_sync as ss


def main() -> list[str]:
    s = Suite("state_sync push-race classification")

    s.ok(ss._is_push_race("! [rejected] main -> main (non-fast-forward)"),
         "real non-fast-forward rejection -> a race, retry")
    s.ok(ss._is_push_race("To github.com:x/y.git\n ! [rejected] (fetch first)"),
         "'fetch first' rejection variant -> still a race")
    s.ok(not ss._is_push_race("fatal: Authentication failed for 'https://github.com/...'"),
         "auth failure -> NOT a race, don't burn retries on it")
    s.ok(not ss._is_push_race("remote: error: GH006: Protected branch update failed"),
         "protected-branch rejection -> NOT a race")
    s.ok(not ss._is_push_race("fatal: unable to access '...': Could not resolve host"),
         "network error -> NOT a race")
    s.ok(not ss._is_push_race(""), "empty stderr -> NOT a race (never crashes on None-ish input)")

    # --- pure state-merge functions (2026-07-21 architecture-quality pass, testing gap F8.2):
    #     these decide whether a concurrent cloud run's scan decisions survive a push race —
    #     the "never lose this run's decisions" invariant the module docstring promises — yet
    #     had zero coverage. They are pure string->string / json->json, trivially testable.
    _merge_jsonl_cases(s)
    _merge_runs_cases(s)

    return s.done()


def _merge_jsonl_cases(s: Suite) -> None:
    # union merge: remote (theirs) history FIRST, then local additions; duplicates dropped;
    # blank lines dropped. Order matters only in that dedup.load_seen is last-wins by key, so
    # a slightly reordered union stays safe.
    ours = '{"url":"a"}\n{"url":"b"}\n'
    theirs = '{"url":"a"}\n{"url":"c"}\n'
    merged = ss._merge_jsonl(ours, theirs)
    s.eq(merged, '{"url":"a"}\n{"url":"c"}\n{"url":"b"}\n',
         "jsonl union: theirs-first, dup 'a' kept once, local 'b' appended")
    s.ok('{"url":"c"}' in merged and '{"url":"b"}' in merged,
         "jsonl union loses NO line from either side")
    s.eq(ss._merge_jsonl("", ""), "\n", "two empty jsonl sides -> a lone newline, never a crash")
    s.eq(ss._merge_jsonl('{"x":1}\n\n\n', ""),
         '{"x":1}\n', "blank lines are dropped from the union")


def _merge_runs_cases(s: Suite) -> None:
    a = json.dumps({"2026-07-21": {"AM": {"new": 3}},
                    "recompute": {"last": "2026-07-20", "sessions_since": 2, "due_at_sessions": 5}})
    b = json.dumps({"2026-07-21": {"PM": {"new": 1}}, "2026-07-22": {"AM": {"new": 2}},
                    "recompute": {"last": "2026-07-21", "sessions_since": 5, "due_at_sessions": 5}})
    m = json.loads(ss._merge_runs(a, b))
    s.eq(sorted(k for k in m if k != "recompute"), ["2026-07-21", "2026-07-22"],
         "runs merge unions days from both sides")
    s.eq(sorted(m["2026-07-21"].keys()), ["AM", "PM"],
         "same-day AM (ours) + PM (theirs) both survive the label-level merge")
    s.eq(m["recompute"]["sessions_since"], 5, "recompute.sessions_since takes the MAX of both")
    s.eq(m["recompute"]["last"], "2026-07-21", "recompute.last takes the later date")
    # malformed input must degrade, never crash the sync round-trip
    s.eq(ss._merge_runs("{not json", '{"x":1}'), "{not json",
         "un-parseable runs json falls back to ours, no crash")


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
