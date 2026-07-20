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

    # CHARACTERIZATION (known quirk, 2026-07-20): a trailing slash is stripped BEFORE the query is
    # removed, so a slash that sits in front of a query survives — '/job/?utm=x' != '/job'. Pinned
    # so a later norm_url reorder is a DELIBERATE change (update this test + prove borjan-pm keys).
    s.eq(dedup.norm_url("https://x.com/job/?utm=x"), "x.com/job/",
         "norm_url: [known quirk] trailing slash + query keeps the slash")

    # norm_company: strip stacked legal suffixes -------------------------------------------------
    s.eq(dedup.norm_company("Foo Group Ltd"), "foo", "norm_company: strips stacked 'Group Ltd'")
    s.eq(dedup.norm_company("Acme, Inc."), "acme", "norm_company: strips 'Inc.'")
    s.eq(dedup.norm_company("Andersen"), "andersen", "norm_company: plain name unchanged")
    # CHARACTERIZATION (known quirk): the Polish 'Sp. z o.o.' suffix is NOT in LEGAL_SUFFIXES, so
    # it survives — 'Finture Sp. z o.o.' won't key-match a bare 'Finture'. Pinned as current
    # behavior; adding the suffix is a deliberate dedup change (borjan-pm keys must be re-proven).
    s.eq(dedup.norm_company("Finture Sp. z o.o."), "finture sp. z o.o",
         "norm_company: [known quirk] Polish 'Sp. z o.o.' not stripped")

    # role_family: strip a trailing location/scope qualifier (the country-clone cross-check) ------
    s.eq(dedup.role_family("Delivery Manager - Belgrade"), "delivery manager",
         "role_family: strips '- Belgrade'")
    s.eq(dedup.role_family("Delivery Manager (Poland)"), "delivery manager",
         "role_family: strips '(Poland)'")
    s.eq(dedup.role_family("Project Manager, Senior"), "project manager",
         "role_family: strips ', Senior'")
    s.eq(dedup.role_family("AI Project Manager"), "ai project manager",
         "role_family: no qualifier -> unchanged")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
