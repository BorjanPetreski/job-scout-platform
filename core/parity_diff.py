#!/usr/bin/env python3
"""parity_diff.py — Phase 1 acceptance (PROFILE_CONFIG_SPEC.md §8): prove the resolved
borjan-pm effective config reproduces job-scout-pm v3's effective configuration
key-for-key. A comparison script, not eyeballing. Exit 0 = parity holds.

ACCEPTED deltas (each printed, none silent):
  A1  Remote Rocketship display names are stream-neutral now
      ("(SM worldwide)" -> "(worldwide)", "(PM Europe)" -> "(Europe)"). Cosmetic:
      Notion select uses notion_platform_name ("Remote Rocketship"), which is unchanged.
  A2  JustJoin.it api URL: old config carried a STALE endpoint (offers?categories[]=13);
      the v3 fetcher actually used the by-cursor endpoint with category 15 hardcoded.
      The new config states what actually runs; the fetcher now reads it from config.
  A3  hard_filters.salary_floor shape: old = three hand-set numbers; new = structured
      floor + published_equivalents carrying the same numbers verbatim (checked below).
  A4  flag name pure_ba -> excl_business_analyst (generic role-exclusion builder);
      pattern equivalence checked semantically below.
  A5  tool_lockin regex is built from the profile's tool list; equivalence checked
      semantically against a battery of known hits/misses.
  A6  quirks text: knowledge carried over but reworded in places (docs, not behavior).
  A7  new additive keys (slug, params, skipped_platforms, sweep, scoring, profile, ...)
      that v3 had no equivalent for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import profile_loader

REPO = Path(__file__).resolve().parent.parent
OLD_CONFIG = REPO / "job-scout-pm" / "config.yaml"

NAME_MAP = {  # A1
    "Remote Rocketship (worldwide)": "Remote Rocketship (SM worldwide)",
    "Remote Rocketship (Europe)": "Remote Rocketship (PM Europe)",
}

problems: list[str] = []
accepted: list[str] = []


def diff(path: str, old, new, note: str | None = None):
    if old != new:
        if note:
            accepted.append(f"{path}: {note}")
        else:
            problems.append(f"{path}: old={old!r} new={new!r}")


def main() -> int:
    old = yaml.safe_load(OLD_CONFIG.read_text(encoding="utf-8"))
    cfg = profile_loader.load("borjan-pm")

    # ---- platforms, matched by numeric id
    old_by_id = {p["id"]: p for p in old["platforms"]}
    new_by_id = {p["id"]: p for p in cfg["platforms"]}
    diff("platform id set", sorted(old_by_id), sorted(new_by_id))
    for pid in sorted(old_by_id):
        o, n = old_by_id[pid], new_by_id.get(pid)
        if n is None:
            continue
        label = f"platform[{pid}] ({o['name']})"
        mapped_new_name = NAME_MAP.get(n["name"], n["name"])
        diff(f"{label}.name", o["name"], mapped_new_name,
             note="A1 stream-neutral rename" if mapped_new_name != n["name"] and o["name"] == mapped_new_name else None)
        if o["name"] != mapped_new_name:
            problems.append(f"{label}.name: old={o['name']!r} new={n['name']!r}")
        diff(f"{label}.tier", o.get("tier"), n.get("tier"))
        diff(f"{label}.active", bool(o.get("active")), bool(n.get("active")))
        diff(f"{label}.fetch_mode", o.get("fetch_mode"), n.get("fetch_mode"))
        diff(f"{label}.urls", o.get("urls") or [], n.get("urls") or [])
        diff(f"{label}.rss", o.get("rss") or [], n.get("rss") or [])
        if pid == 17:  # A2
            diff(f"{label}.api", o.get("api"), n.get("api"),
                 note="A2 old config carried a stale JJ.it endpoint; fetcher used by-cursor/15")
        else:
            diff(f"{label}.api", o.get("api") or [], n.get("api") or [])
        diff(f"{label}.api_pattern", o.get("api_pattern"), n.get("api_pattern"))
        diff(f"{label}.boards", o.get("boards"), n.get("boards"))
        diff(f"{label}.mirrors", o.get("mirrors") or [], n.get("mirrors") or [])
        diff(f"{label}.expired_markers", o.get("expired_markers") or [], n.get("expired_markers") or [])
        diff(f"{label}.notion_platform_name", dict(o.get("notion_platform_name") or {}),
             dict(n.get("notion_platform_name") or {}))
        diff(f"{label}.per_job_fetch_mode", o.get("per_job_fetch_mode"), n.get("per_job_fetch_mode"))
        diff(f"{label}.recheck_after", o.get("recheck_after"), n.get("recheck_after"))
        if (o.get("quirks") or "").strip() != (n.get("quirks") or "").strip():
            accepted.append(f"{label}.quirks: A6 reworded (knowledge carried, not behavior)")

    # ---- keywords (exact — the 1.8.0 invariant)
    diff("keywords.core", old["keywords"]["core"], cfg["keywords"]["core"])
    diff("keywords.expanded", old["keywords"]["expanded"], cfg["keywords"]["expanded"])

    # ---- hard filters
    ohf, nhf = old["hard_filters"], cfg["hard_filters"]
    for k in ("us_only", "clearance", "travel", "grind_culture"):
        diff(f"auto_drop_patterns.{k}", ohf["auto_drop_patterns"].get(k),
             nhf["auto_drop_patterns"].get(k))
    diff("auto_drop key set", sorted(ohf["auto_drop_patterns"]), sorted(nhf["auto_drop_patterns"]))
    for k in ("timezone", "eu_citizenship", "latam_payroll"):
        diff(f"flag_patterns.{k}", ohf["flag_patterns"].get(k), nhf["flag_patterns"].get(k))

    # A4/A5: semantic equivalence batteries
    batteries = {
        ("pure_ba", "excl_business_analyst"): (
            ["business analyst", "Senior Business Analyst wanted", "BUSINESS ANALYST"],
            ["business analysis", "analyst", "pure delivery manager"]),
        ("tool_lockin", "tool_lockin"): (
            ["dynamics 365", "Salesforce Administrator", "SAP consultant", "Workday certified",
             "oracle architect", "ServiceNow certification", "Dynamics consultant"],
            ["salesforce experience a plus", "SAP exposure", "oracle db", "project manager"]),
    }
    for (ok, nk), (hits, misses) in batteries.items():
        op, np_ = ohf["flag_patterns"].get(ok), nhf["flag_patterns"].get(nk)
        if not op or not np_:
            problems.append(f"flag pattern missing: old {ok!r}={bool(op)} new {nk!r}={bool(np_)}")
            continue
        for s in hits:
            if not re.search(op, s) or not re.search(np_, s):
                problems.append(f"{ok}->{nk}: expected HIT diverges on {s!r} "
                                f"(old={bool(re.search(op, s))} new={bool(re.search(np_, s))})")
        for s in misses:
            if re.search(op, s) or re.search(np_, s):
                problems.append(f"{ok}->{nk}: expected MISS diverges on {s!r} "
                                f"(old={bool(re.search(op, s))} new={bool(re.search(np_, s))})")
        accepted.append(f"flag_patterns.{ok} -> {nk}: A4/A5 semantically equivalent "
                        f"({len(hits)} hits + {len(misses)} misses verified)")

    det_o, det_n = ohf["eu_country_list_detector"], nhf["eu_country_list_detector"]
    diff("eu_country_list_detector.countries", det_o["countries"], det_n["countries"])
    diff("eu_country_list_detector.open_ended_markers", det_o["open_ended_markers"], det_n["open_ended_markers"])
    diff("eu_country_list_detector.must_include", det_o["must_include"], det_n["must_include"])

    # A3: salary floor numbers survive verbatim
    sf_o, sf_n = ohf["salary_floor"], nhf["salary_floor"]
    diff("salary_floor net amount", sf_o["eur_net_month"],
         sf_n["floor"]["amount"] if sf_n["floor"]["basis"] == "net" and sf_n["floor"]["currency"] == "EUR" else None)
    diff("salary_floor published gross", sf_o["eur_gross_month"],
         sf_n["published_equivalents"].get("eur_gross_month"))
    diff("salary_floor published usd/yr", sf_o["usd_year"],
         sf_n["published_equivalents"].get("usd_year"))
    accepted.append("salary_floor: A3 structured shape (numbers verified equal above)")

    # ---- caps / scan / recompute / linkedin / notion
    for k, v in old["caps"].items():
        diff(f"caps.{k}", v, cfg["caps"].get(k))
    for k, v in old["scan"].items():
        diff(f"scan.{k}", v, cfg["scan"].get(k))
    diff("recompute.due_at_sessions", old["recompute"]["due_at_sessions"],
         cfg["recompute"]["due_at_sessions"])
    olt = old["linkedin_tripwire"]
    nlt = cfg["linkedin_tripwire"]
    for k in ("enabled", "keywords", "locations", "remote_filter", "freshness"):
        diff(f"linkedin_tripwire.{k}", olt.get(k, True), nlt.get(k))
    onot, nnot = old["notion"], cfg["notion"]
    diff("notion.tracker", onot["tracker"]["data_source_id"], nnot["tracker"]["data_source_id"])
    diff("notion.tracker parent", onot["tracker"]["parent_page_id"], nnot["tracker"]["parent_page_id"])
    diff("notion.passed_seen", onot["passed_seen"]["data_source_id"], nnot["passed_seen"]["data_source_id"])
    diff("notion.passed_seen parent", onot["passed_seen"]["parent_page_id"], nnot["passed_seen"]["parent_page_id"])
    diff("notion.pinned job_scout_runs", onot["pinned_pages"]["job_scout_runs"],
         nnot["pinned_pages"]["job_scout_runs"])
    diff("notion.tracker_status_options", onot["tracker_status_options"],
         nnot.get("tracker_status_options"))

    # ---- tiers as effective name lists (old tiers block, mapped through A1 renames)
    for t in (1, 2, 3):
        old_names = sorted(old["tiers"][t])
        new_names = sorted(NAME_MAP.get(x, x) for x in cfg["tiers"][t])
        # old tiers block lists inactive platforms too (EuropeRemotely, Otta in tier 3);
        # the new tiers view is active-only — compare on the active subset
        active_old = sorted(n for n in old_names if n not in ("EuropeRemotely", "Otta"))
        diff(f"tiers[{t}] (active)", active_old, new_names)

    # ---- rejected platforms (names + reasons verbatim)
    old_rej = {r["name"]: r["reason"] for r in old["rejected_platforms"]}
    new_rej = {r["name"]: r["reason"] for r in cfg["rejected_platforms"]}
    diff("rejected_platforms", old_rej, new_rej)

    print(f"PARITY DIFF — borjan-pm resolved config vs job-scout-pm/config.yaml")
    print(f"\nAccepted deltas ({len(accepted)}):")
    for a in accepted:
        print(f"  ≈ {a}")
    if problems:
        print(f"\nUNEXPECTED differences ({len(problems)}):")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("\n✅ PARITY HOLDS: everything else key-for-key identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
