#!/usr/bin/env python3
"""Unit coverage for core/salary.py — pure salary parse/normalize/floor-compare logic.

Why this exists (2026-07-21 architecture-quality pass, testing-architecture gap F8.1):
salary.py was the ONE pure scoring module with zero committed tests, yet it drives a
mechanical judgment input (scan.py calls salary.assess on every survivor). tests/README's
own rule is "unit-test the pure logic (detectors, dedup/scoring helpers)" — this closes
that gap. The cases below deliberately PIN the two regressions the module's own docstrings
memorialize (the `3.500`→3500 thousands-vs-decimal split, and the currency-neutral period
inference that fixed the 2026-07-13 `24998 PLN/month`-read-as-annual bug), plus the
salary-floor clears/below/borderline boundary and the "unstated → never a drop" contract.

Also pins the currently-SAFE `zł`-suffix behavior surfaced (and mis-severity-claimed) in the
same pass: a `zł`-suffixed amount is UNPARSEABLE (falls to estimation heuristics), NOT
mis-read as USD — the safe side. If someone "fixes" the dead `_CUR_SYMBOL['zł']` entry, this
test makes them confront what the parse actually does today."""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from _harness import Suite
import salary

DEFAULTS = yaml.safe_load((Path(__file__).resolve().parent.parent / "core" / "defaults.yaml")
                          .read_text(encoding="utf-8"))


def main() -> list[str]:
    s = Suite("salary parse/normalize/assess")

    # --- _num: thousands-vs-decimal disambiguation (the "3.500" regression the docstring cites)
    s.eq(salary._num("3.500"), 3500.0, "'3.500' is 3500 (dotted thousands, not 3.5 decimal)")
    s.eq(salary._num("3.5"), 3.5, "'3.5' stays a decimal")
    s.eq(salary._num("65k"), 65000.0, "'65k' expands to 65000")
    s.eq(salary._num("3,000"), 3000.0, "'3,000' comma thousands -> 3000")
    s.eq(salary._num("3 000"), 3000.0, "'3 000' space thousands -> 3000")

    # --- parse: needs a currency OR a period to trust a number; range max drives the floor test
    p = salary.parse("12 000 - 18 000 PLN net/month B2B")
    s.eq((p["amount_max"], p["currency"], p["basis"]), (18000.0, "PLN", "net"),
         "PLN range parses max=18000, currency=PLN, basis=net")
    s.ok(salary.parse("great team, competitive pay") is None,
         "prose with no number/currency -> None")
    s.ok(salary.parse("apply by 2026") is None, "a bare year is not a salary")
    # zł suffix is UNREACHABLE by the regex symbol class -> unparseable (safe side), not USD.
    s.ok(salary.parse("12 000 zł / month") is None,
         "zł-suffixed amount is unparseable (safe side), NOT mis-read as a currency")
    # bare number WITH a stated period defaults currency to USD (documented behavior).
    s.eq(salary.parse("5000 per month")["currency"], "USD",
         "bare number + stated period defaults currency USD (documented)")

    # --- _infer_period: currency-neutral magnitude (2026-07-13 PLN-read-as-annual regression pin)
    s.eq(salary._infer_period(24998, "PLN", DEFAULTS), "month",
         "24998 PLN reads as MONTHLY (not annual) — currency-neutral magnitude")
    s.eq(salary._infer_period(200, "EUR", DEFAULTS), "day", "200 EUR/unit-of-time -> day band")
    s.eq(salary._infer_period(120000, "EUR", DEFAULTS), "year", "120k EUR -> annual band")
    s.ok(salary._infer_period(5000, "XYZ", DEFAULTS) is None, "unknown currency -> None")

    # --- to_canonical: target-currency gross/month; None on unknown currency
    s.eq(salary.to_canonical(3000, "EUR", "month", "gross", "EUR", 0.75, DEFAULTS), 3000.0,
         "3000 EUR gross/month in EUR canon = 3000")
    s.ok(salary.to_canonical(3000, "XYZ", "month", "gross", "EUR", 0.75, DEFAULTS) is None,
         "unknown source currency -> None")
    # net -> gross grosses UP by the ratio (net/ratio > net)
    s.ok(salary.to_canonical(3000, "EUR", "month", "net", "EUR", 0.75, DEFAULTS) > 3000,
         "net basis grosses up (divides by ratio)")

    # --- normalize_floor: set floor, floorless (D20), and part-time pro-rate (D22)
    fl = salary.normalize_floor(
        {"floor": {"amount": 2500, "currency": "EUR", "basis": "net", "period": "month"},
         "gross_net_ratio": 0.83}, DEFAULTS)
    s.eq(fl["canonical_gross_month"], 3012.05, "2500 EUR net/month @0.83 -> 3012.05 gross/month")
    floorless = salary.normalize_floor({}, DEFAULTS)
    s.ok(floorless["canonical_gross_month"] is None,
         "floorless (D20) -> canonical None (below-floor first-pass disabled)")
    pt = salary.normalize_floor(
        {"floor": {"amount": 3000, "currency": "EUR", "basis": "gross", "period": "month"},
         "gross_net_ratio": 0.8, "fte_fraction": 0.5}, DEFAULTS)
    s.eq(pt["canonical_gross_month"], 1500.0, "fte_fraction 0.5 pro-rates a 3000 floor to 1500")

    # --- assess: the clears / below_floor / borderline / unparseable boundary
    s.eq(salary.assess("12 000 - 18 000 PLN net/month B2B", fl, DEFAULTS)["status"], "clears",
         "18k PLN net/month clears a 2500 EUR net floor")
    s.eq(salary.assess("1000 EUR per month", fl, DEFAULTS)["status"], "below_floor",
         "1000 EUR/month is below a ~3012 gross floor")
    s.eq(salary.assess("3000 EUR gross per month", fl, DEFAULTS)["status"], "borderline",
         "3000 EUR ~= the 3012 floor (within ±10%) -> borderline")
    s.eq(salary.assess("", fl, DEFAULTS)["status"], "unparseable",
         "no salary text -> unparseable (never a drop; estimation heuristics take over)")
    s.eq(salary.assess("12 000 zł / month", fl, DEFAULTS)["status"], "unparseable",
         "zł-suffixed salary -> unparseable (safe side, not a false clears/below)")
    s.eq(salary.assess("5000 USD/month", floorless, DEFAULTS)["status"], "unparseable",
         "floorless profile -> assess always unparseable (judgment layer estimates)")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
