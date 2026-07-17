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
        # period stays None when the text doesn't state it — currency-neutral inference
        # happens in assess() on the EUR-normalized magnitude (a raw-magnitude guess is
        # wrong for non-USD: 24998 PLN/month tripped a ">=20000 → annual" rule and read
        # 12x too low, 2026-07-13 cutover run).
        return {"amount_min": lo, "amount_max": hi, "currency": cur or "USD",
                "period": period, "period_stated": period is not None, "basis": basis}
    return None


def _infer_period(amount: float, currency: str, defaults: dict) -> str | None:
    """Infer pay period from the EUR-normalized magnitude of a single figure —
    currency-neutral, so a monthly PLN salary in the tens of thousands is not mistaken
    for an annual one. None if the currency isn't in the FX table."""
    fx = defaults.get("salary", {}).get("fx_to_eur", {})
    if currency not in fx:
        return None
    eur = amount * fx[currency]
    if eur >= 30000:
        return "year"
    if eur >= 1200:
        return "month"
    if eur >= 150:
        return "day"
    return "hour"


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
    """Profile floor -> canonical gross/month in the floor's own currency.

    Floorless (D20): when `compensation.floor` is unset, the machine below-floor
    first-pass is DISABLED — canonical_gross_month is None and assess() returns
    'unparseable' so salary judgment falls entirely to the template's
    salary_estimation_heuristics (never an auto-drop).

    Part-time (D22): when `fte_fraction` is present, the canonical floor is pro-rated
    by that fraction before comparison (a full-time 3000/mo floor at 0.5 FTE compares
    against 1500). The templater sets fte_fraction ONLY for part-time targets; a
    full-time profile leaves it unset and its floor is unchanged.
    """
    fl = compensation.get("floor")
    ratio = float(compensation.get("gross_net_ratio", 0.75))
    fte = compensation.get("fte_fraction")
    fte_f = float(fte) if fte is not None else None
    if not fl:
        return {"floor": None, "gross_net_ratio": ratio, "canonical_gross_month": None,
                "currency": None, "fte_fraction": fte_f,
                "published_equivalents": compensation.get("published_equivalents", {})}
    canonical = to_canonical(float(fl["amount"]), fl["currency"], fl["period"], fl["basis"],
                             fl["currency"], ratio, defaults)
    if canonical is not None and fte_f is not None:
        canonical = canonical * fte_f
    return {"floor": dict(fl), "gross_net_ratio": ratio,
            "canonical_gross_month": round(canonical, 2) if canonical else None,
            "currency": fl["currency"], "fte_fraction": fte_f,
            "published_equivalents": compensation.get("published_equivalents", {})}


def assess(text: str | None, floor_norm: dict, defaults: dict) -> dict:
    """Judgment-layer INPUT, additive metadata only — never a machine drop.
    status: clears | below_floor | borderline | unparseable"""
    parsed = parse(text or "")
    if not parsed or not floor_norm.get("canonical_gross_month"):
        return {"status": "unparseable", "detail": "no parseable salary; apply estimation heuristics"}
    period = parsed["period"] or _infer_period(parsed["amount_max"], parsed["currency"], defaults)
    if period is None:
        return {"status": "unparseable", "detail": f"unknown currency {parsed['currency']}"}
    canon = to_canonical(parsed["amount_max"], parsed["currency"], period,
                         parsed["basis"], floor_norm["currency"],
                         floor_norm["gross_net_ratio"], defaults)
    if canon is None:
        return {"status": "unparseable", "detail": f"unknown currency {parsed['currency']}"}
    floor = floor_norm["canonical_gross_month"]
    margin = float(defaults.get("salary", {}).get("borderline_margin", 0.10))
    ratio = canon / floor
    stated = "" if parsed.get("period_stated") else " [period inferred]"
    detail = (f"range max ≈ {canon:,.0f} {floor_norm['currency']} gross/month vs floor "
              f"{floor:,.0f} (parsed {parsed['amount_max']:,.0f} {parsed['currency']} "
              f"{parsed['basis']}/{period}{stated})")
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
