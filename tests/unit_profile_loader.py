#!/usr/bin/env python3
"""Unit coverage for core/profile_loader.py's pure deep-merge helper.

_merge (2026-07-21): found during a full architecture regression pass — the merge's base
case treated an explicit `key: null` in a profile as "not set, keep the template's value,"
silently defeating the documented D20 floorless contract (a profile writing
`compensation.floor: null` over a template that DOES set a floor kept the template's floor,
no error, no warning). "Later wins" must mean later wins even when later is null."""
from __future__ import annotations

import sys

from _harness import Suite
import profile_loader as pl


def main() -> list[str]:
    s = Suite("profile_loader._merge")

    # plain scalar override --------------------------------------------------------------
    s.eq(pl._merge({"a": 1}, {"a": 2}), {"a": 2}, "scalar override wins")
    s.eq(pl._merge({"a": 1}, {}), {"a": 1}, "key absent from override -> base kept")

    # nested dict deep-merges, non-overridden siblings survive ---------------------------
    s.eq(pl._merge({"a": {"x": 1, "y": 2}}, {"a": {"x": 9}}), {"a": {"x": 9, "y": 2}},
         "nested dict: override merges in, sibling key untouched")

    # THE bug: explicit null override on a key whose base value is a dict ----------------
    s.eq(pl._merge({"compensation": {"floor": {"amount": 2500, "currency": "EUR"}}},
                   {"compensation": {"floor": None}}),
         {"compensation": {"floor": None}},
         "explicit null over a template-set dict value -> null wins (D20 floorless contract)")

    # null override on a plain scalar base (same rule, simpler shape) --------------------
    s.eq(pl._merge({"a": {"b": 5}}, {"a": {"b": None}}), {"a": {"b": None}},
         "explicit null over a scalar base value -> null wins")

    # list override still replaces wholesale, never merges element-wise ------------------
    s.eq(pl._merge({"a": [1, 2, 3]}, {"a": [9]}), {"a": [9]},
         "list override replaces wholesale (never element-merged)")

    # a key genuinely new to override still lands even when base lacks it ----------------
    s.eq(pl._merge({"a": 1}, {"b": 2}), {"a": 1, "b": 2}, "new key from override is added")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
