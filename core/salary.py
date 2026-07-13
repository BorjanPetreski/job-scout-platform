#!/usr/bin/env python3
"""salary.py — salary parsing + normalization (PROFILE_CONFIG_SPEC.md §5).

Canonical comparison unit: the PROFILE's floor currency, GROSS, per MONTH.
Precision beyond "does it clear the floor" is not a goal: FX is a static table
(core/defaults.yaml), gross<->net is the profile's ratio knob (no tax engine), and
anything within the borderline margin of the floor is flagged "borderline — verify",
never auto-dropped. Unstated salary is NEVER a drop — the judgment layer applies the
template's estimation heuristics. Every assessment records the assumptions used.
"""

from __future__ import annotations

import re

# amount like 3000 / 3,000 / 3.5k / 65k
_AMOUNT = r"(\d{1,3}(?:[,.\s]\d{3})+|\d+(?:\.\d+)?)\s*[kK]?"
_CUR_SYMBOL = {"€": "EUR", "$": "USD", "£": "GBP", "zł": "PLN"}
_CUR_CODE = r"(EUR|USD|GBP|PLN|CHF|CZK|SEK|NOK|DKK|CAD|AUD|MXN|BRL)"

SALARY_RE = re.compile(
    rf"(?P<sym>[€$£])?\s*(?P<a1>{_AMOUNT})(?:\s*[-–—to]+\s*(?P<sym2>[€$£])?\s*(?P<a2>{_AMOUNT}))?"
    rf"\s*(?P<code>{_CUR_CODE})?\s*(?:/|\bper\b|\ba\b)?\s*(?P<period>hour|hr|day|month|mo|year|yr|annum|annually|monthly|daily|hourly)?",
    re.IGNORECASE,
)

PERIOD_MAP = {"hour": "hour", "hr": "hour", "hourly": "hour", "day": "day", "daily": "day",
              "month": "month", "mo": "month", "monthly": "month",
              "year": "year", "yr": "year", "annum": "year", "annually": "year"}


def _num(raw: str) -> float:
    s = raw.strip()
    k = s.lower().endswith("k")
    s = s.rstrip("kK").replace(",", "").replace(" ", "")
    # "3.500" style thousands (single dot, 3 trailing digits) vs decimal "3.5"
    if re.fullmatch(r"\d+\.\d{3}", s):
        s = s.replace(".", "")
    v = float(s)
    return v * 1000 if k else v


def parse(text: str) -> dict | None:
    """Best-effort parse of the FIRST plausible salary mention.
    Returns {amount_max, amount_min, currency, period, basis} or None.
    Range maximum drives the floor test (a role whose top can't reach the floor is out)."""
    if not text:
        return None
    for m in SALARY_RE.finditer(text):
        if not (m.group("a1")):
            continue
        cur = None
        if m.group("code"):
            cur = m.group("code").upper()
        elif m.group("sym") or m.group("sym2"):
            cur = _CUR_SYMBOL.get(m.group("sym") or m.group("sym2"))
        period = PERIOD_MAP.get((m.group("period") or "").lower())
        if cur is None and period is None:
            continue  # bare number — not a salary mention we can trust
        a1 = _num(m.group("a1"))
        a2 = _num(m.group("a2")) if m.group("a2") else a1
        lo, hi = min(a1, a2), max(a1, a2)
        if hi < 5:  # noise
            continue
        window = text[max(0, m.start() - 60): m.end() + 60].lower()
        basis = "net" if re.search(r"\b(net|netto)\b", window) else "gross"
        if period is None:  # infer: yearly figures are big, monthly mid, daily small
            period = "year" if hi >= 20000 else ("month" if hi >= 900 else "day")
        return {"amount_min": lo, "amount_max": hi, "currency": cur or "USD",
                "period": period, "basis": basis}
    return None


def to_canonical(amount: float, currency: str, period: str, basis: str,
                 target_currency: str, gross_net_ratio: float, defaults: dict) -> float | None:
    """Convert an amount to target-currency GROSS per MONTH. None if currency unknown."""
    sal = defaults.get("salary", {})
    fx = sal.get("fx_to_eur", {})
    if currency not in fx or target_currency not in fx:
        return None
    factor = sal.get("period_to_month_factor", {}).get(period)
    if factor is None:
        return None
    monthly = amount * float(factor)
    gross = monthly / gross_net_ratio if basis == "net" else monthly
    eur = gross * fx[currency]
    return eur / fx[target_currency]


def normalize_floor(compensation: dict, defaults: dict) -> dict:
    """Profile floor -> canonical gross/month in the floor's own currency."""
    fl = compensation["floor"]
    ratio = float(compensation.get("gross_net_ratio", 0.75))
    canonical = to_canonical(float(fl["amount"]), fl["currency"], fl["period"], fl["basis"],
                             fl["currency"], ratio, defaults)
    return {"floor": dict(fl), "gross_net_ratio": ratio,
            "canonical_gross_month": round(canonical, 2) if canonical else None,
            "currency": fl["currency"],
            "published_equivalents": compensation.get("published_equivalents", {})}


def assess(text: str | None, floor_norm: dict, defaults: dict) -> dict:
    """Judgment-layer INPUT, additive metadata only — never a machine drop.
    status: clears | below_floor | borderline | unparseable"""
    parsed = parse(text or "")
    if not parsed or not floor_norm.get("canonical_gross_month"):
        return {"status": "unparseable", "detail": "no parseable salary; apply estimation heuristics"}
    canon = to_canonical(parsed["amount_max"], parsed["currency"], parsed["period"],
                         parsed["basis"], floor_norm["currency"],
                         floor_norm["gross_net_ratio"], defaults)
    if canon is None:
        return {"status": "unparseable", "detail": f"unknown currency {parsed['currency']}"}
    floor = floor_norm["canonical_gross_month"]
    margin = float(defaults.get("salary", {}).get("borderline_margin", 0.10))
    ratio = canon / floor
    detail = (f"range max ≈ {canon:,.0f} {floor_norm['currency']} gross/month vs floor "
              f"{floor:,.0f} (parsed {parsed['amount_max']:,.0f} {parsed['currency']} "
              f"{parsed['basis']}/{parsed['period']})")
    if ratio >= 1 + margin:
        return {"status": "clears", "detail": detail}
    if ratio <= 1 - margin:
        return {"status": "below_floor", "detail": detail + " — verify before dropping"}
    return {"status": "borderline", "detail": detail + " — borderline, verify"}


if __name__ == "__main__":
    import sys
    import yaml
    from pathlib import Path

    defaults = yaml.safe_load((Path(__file__).parent / "defaults.yaml").read_text(encoding="utf-8"))
    text = " ".join(sys.argv[1:]) or "12 000 - 18 000 PLN net/month B2B"
    print("parse:", parse(text))
    floor = normalize_floor({"floor": {"amount": 2500, "currency": "EUR", "basis": "net", "period": "month"},
                             "gross_net_ratio": 0.83}, defaults)
    print("floor:", floor)
    print("assess:", assess(text, floor, defaults))
