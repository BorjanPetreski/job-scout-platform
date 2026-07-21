#!/usr/bin/env python3
"""Unit coverage for the pure normalization helpers in core/dedup.py — the functions that decide
whether two postings are "the same" (the dedup key) and drive the country-clone cross-check.
A regression here silently splits or merges postings, so they're worth pinning."""
from __future__ import annotations

import sys

from _harness import Suite
import dedup


def main() -> list[str]:
    s = Suite("dedup helpers")

    # norm_url: lowercase, drop scheme + www, drop query/fragment, drop a bare trailing slash ----
    s.eq(dedup.norm_url("https://www.Example.com/Job"), "example.com/job",
         "norm_url: lowercases, strips scheme+www")
    s.eq(dedup.norm_url("http://justjoin.it/job-offer/abc/"), "justjoin.it/job-offer/abc",
         "norm_url: strips a bare trailing slash")
    s.eq(dedup.norm_url("HTTPS://Example.com/a#frag"), "example.com/a",
         "norm_url: strips fragment")
    s.eq(dedup.norm_url("https://x.com/p?utm_source=1"), "x.com/p",
         "norm_url: strips tracking query")

    # FIXED 2026-07-20 (was a pinned quirk): the trailing slash is now stripped AFTER the query, so
    # a slash sitting in front of a query no longer survives — '/job/?utm=x' == '/job?utm=x' == '/job'.
    s.eq(dedup.norm_url("https://x.com/job/?utm=x"), "x.com/job",
         "norm_url: trailing slash before a query is stripped")
    s.eq(dedup.norm_url("https://x.com/job/?utm=x"), dedup.norm_url("https://x.com/job?utm=x"),
         "norm_url: '/job/?x' and '/job?x' key identically")

    # norm_company: strip stacked legal suffixes -------------------------------------------------
    s.eq(dedup.norm_company("Foo Group Ltd"), "foo", "norm_company: strips stacked 'Group Ltd'")
    s.eq(dedup.norm_company("Acme, Inc."), "acme", "norm_company: strips 'Inc.'")
    s.eq(dedup.norm_company("Andersen"), "andersen", "norm_company: plain name unchanged")
    # FIXED 2026-07-20 (was a pinned quirk): the Polish 'Sp. z o.o.' family is now in LEGAL_SUFFIXES,
    # so 'Finture Sp. z o.o.' key-matches a bare 'Finture' (JustJoin.it postings vary the suffix).
    s.eq(dedup.norm_company("Finture Sp. z o.o."), "finture",
         "norm_company: Polish 'Sp. z o.o.' is stripped")
    s.eq(dedup.norm_company("Finture Sp. z o.o."), dedup.norm_company("Finture"),
         "norm_company: 'Finture Sp. z o.o.' and 'Finture' key identically")
    s.eq(dedup.norm_company("Acme Sp. z o.o. Sp. k."), "acme",
         "norm_company: strips the combined 'Sp. z o.o. Sp. k.'")

    # role_family: strip a trailing location/scope qualifier (the country-clone cross-check) ------
    s.eq(dedup.role_family("Delivery Manager - Belgrade"), "delivery manager",
         "role_family: strips '- Belgrade'")
    s.eq(dedup.role_family("Delivery Manager (Poland)"), "delivery manager",
         "role_family: strips '(Poland)'")
    s.eq(dedup.role_family("Project Manager, Senior"), "project manager",
         "role_family: strips ', Senior'")
    s.eq(dedup.role_family("AI Project Manager"), "ai project manager",
         "role_family: no qualifier -> unchanged")

    # make_seen_record: the canonical record-shape constructor (2026-07-21 coupling fix 4.1). Pin
    # the exact field set + defaults so the scan→notion contract can't drift silently again. ------
    rec = dedup.make_seen_record(company="Acme", role="PM", locdom="EU", url="u",
                                 platform="Greenhouse", status="dropped",
                                 reason="Filtered Out", notes="why")
    s.eq(set(rec), {"company", "role", "locdom", "url", "platform", "status", "reason",
                    "fit", "archetype", "keyword_source", "notes"},
         "make_seen_record: exactly the 11 canonical fields, no more/less")
    s.eq((rec["fit"], rec["archetype"], rec["keyword_source"]), ("N/A", "", "PM"),
         "make_seen_record: fit/archetype defaults + keyword_source defaults to role")
    s.eq(dedup.make_seen_record(company="A", role="PM", locdom="", url="u", platform="X",
                                status="dropped", reason="R", notes="n",
                                keyword_source="kw")["keyword_source"], "kw",
         "make_seen_record: explicit keyword_source overrides the role default")
    # append() must accept the constructor's output and round-trip through load_seen unchanged.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "seen.jsonl"
        dedup.append(dedup.make_seen_record(company="Acme", role="PM", locdom="EU", url="http://u",
                                            platform="Greenhouse", status="dropped",
                                            reason="Filtered Out", notes="why"), path=p)
        got = dedup.load_seen(p)["by_url"][dedup.norm_url("http://u")]
        s.eq((got["role"], got["status"], got["synced_to_notion"]), ("PM", "dropped", False),
             "make_seen_record -> append -> load_seen round-trips + gets append's defaults")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
