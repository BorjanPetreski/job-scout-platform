#!/usr/bin/env python3
"""Unit coverage for the pure detectors in core/scan.py — the "scripts flag" logic layer where
the recent leaks lived (Polish requirement, hybrid/on-site, full-time-on-B2B, stated-language).
Pure in→out functions, no I/O; this is the cheap, high-value coverage validate.py can't give
(it only proves the file COMPILES, never that a detector returns the right answer)."""
from __future__ import annotations

import sys
from datetime import date

from _harness import Suite
import scan

# ~60 stopword-rich words so detect_language clears its 50-word floor.
EN = ("We are looking for a manager who will work with our team and who has the experience that "
      "you would want. This is the work that you have been doing and they were the ones who would "
      "work while others should have done what they must for our team and your future with us.")
PL = ("Poszukujemy osoby na stanowisko która jest odpowiedzialna oraz ma doświadczenie i "
      "umiejętności. Praca w naszym zespole dla nas jest ważna a wymagania oraz obowiązki są "
      "jasne. Mile widziane jest znajomość narzędzi oraz nasz zespół oczekuje że kandydat jest "
      "gotowy jako lider. To jest praca dla osób z doświadczeniem oraz umiejętnościami zespołu.")


def main() -> list[str]:
    s = Suite("scan detectors")

    # detect_language ---------------------------------------------------------------------
    s.eq(scan.detect_language(EN), "en", "detect_language: English body -> en")
    s.eq(scan.detect_language(PL), "pl", "detect_language: Polish body -> pl")
    s.eq(scan.detect_language("too short to judge"), None, "detect_language: <50 words -> None")

    # language_flag (JD's OWN dominant language) ------------------------------------------
    s.eq(scan.language_flag(PL, {"en"})[0], "non_target_language",
         "language_flag: Polish JD, target en -> flag")
    s.eq(scan.language_flag(EN, {"en"})[0], None, "language_flag: English JD, target en -> no flag")
    s.eq(scan.language_flag(PL, {"pl", "en"})[0], None,
         "language_flag: Polish JD, pl in target set -> no flag")

    # stated_language_requirement (English JD that STATES a non-target requirement) --------
    S = scan.stated_language_requirement
    s.eq(S("PM role. Requirements: Polish C1 and English B2.", {"en"})[0],
         "stated_language_requirement", "stated: 'Polish C1' -> flag")
    s.eq(S("Great role. The application must be submitted in Polish.", {"en"})[0],
         "stated_language_requirement", "stated: 'apply in Polish' -> flag")
    s.eq(S("Delivery Manager. Native German speaker required.", {"en"})[0],
         "stated_language_requirement", "stated: 'native German' -> flag")
    s.eq(S("PM role. English required. Polish is a nice to have.", {"en"})[0], None,
         "stated: Polish nice-to-have -> no flag")
    s.eq(S("PM role. English C1 required. Remote B2B.", {"en"})[0], None,
         "stated: English C1 (target lang) -> no flag")
    s.eq(S("PM role, B2B contract, advanced tooling, English fluent.", {"en"})[0], None,
         "stated: 'B2B'/'advanced' no false positive")
    s.eq(S("Delivery Manager. Native German speaker required.", {"de", "en"})[0], None,
         "stated: German requirement but de in target set -> no flag")

    # detect_employment -------------------------------------------------------------------
    s.eq(scan.detect_employment("Full-time B2B contract role"), {"full_time", "b2b", "contract"},
         "employment: full-time + b2b + contract")
    s.eq(scan.detect_employment("Part-time freelance gig"), {"part_time", "freelance"},
         "employment: part-time + freelance")
    s.eq(scan.detect_employment("Project Manager, remote"), set(),
         "employment: unstated -> empty set (not full_time)")

    # detect_work_arrangement (structured loc tag wins over body prose) -------------------
    s.eq(scan.detect_work_arrangement("Kraków (hybrid)", "we are fully remote"), {"hybrid"},
         "work_arrangement: (hybrid) loc tag beats 'remote' in body")
    s.eq(scan.detect_work_arrangement("Warszawa (remote)", ""), {"remote"},
         "work_arrangement: (remote) loc tag")
    s.eq(scan.detect_work_arrangement("Berlin (office)", ""), {"on_site"},
         "work_arrangement: (office) synonym -> on_site")
    s.eq(scan.detect_work_arrangement("Warsaw", "fully remote position"), {"remote"},
         "work_arrangement: no tag -> body 'fully remote'")

    # start_date_passed -------------------------------------------------------------------
    today = date(2026, 7, 1)
    s.eq(scan.start_date_passed("Project start: 06.2025", today), (True, "2025-06"),
         "start_date_passed: stated start already gone -> True")
    s.eq(scan.start_date_passed("Planned start 06.2027", today)[0], False,
         "start_date_passed: future start -> False")
    s.eq(scan.start_date_passed("Some date 06.2020 appears with no start context", today)[0], False,
         "start_date_passed: date without start context -> False")

    # detect_seniority (longest lexicon key wins) -----------------------------------------
    lex = {"senior": "senior", "lead": "lead", "tech lead": "lead", "mid": "mid"}
    s.eq(scan.detect_seniority("Senior Project Manager", lex), "senior",
         "seniority: 'Senior' -> senior")
    s.eq(scan.detect_seniority("Tech Lead", lex), "lead",
         "seniority: 'Tech Lead' longest-key wins -> lead")
    s.eq(scan.detect_seniority("Project Manager", lex), None,
         "seniority: no band term -> None")

    return s.done()


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
