#!/usr/bin/env python3
"""Unit coverage for core/state_sync.py's pure push-failure classification.

_is_push_race (2026-07-21): found during a full architecture regression pass — push()'s
retry loop used to treat EVERY non-zero push return code as "someone else pushed in
between" and retry via pull()+push, up to 4 times with backoff. Auth failures,
protected-branch rejections, and network errors aren't races pull() can fix — retrying
them just burns 4 attempts before failing with the same unfixable error."""
from __future__ import annotations

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

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
