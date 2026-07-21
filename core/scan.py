#!/usr/bin/env python3
"""scan.py — orchestrator. Runs the rotation for ONE PROFILE, emits candidates JSON.
DOES NOT SCORE.

Scoring, archetype tagging, judgment-layer filter reads, and the shortlist table are
Claude's job in the session, reading profiles/<id>/state/last_run_candidates.json +
the JD cache. Regexes here are a FIRST PASS (Spiralyze lesson: scripts flag, Claude
decides) — only unambiguous mechanical drops are auto-logged.

Usage:
  scan.py [--profile ID]      full active rotation (r2 default)
  scan.py --plan              print the resolved scan plan (platforms, URLs, keywords,
                              filters) WITHOUT fetching anything — dry-run/acceptance
  scan.py --half AM|PM        retained for degraded/manual use only
  scan.py --full-sweep        ignore the freshness window (scheduler runs this on Mondays)
  scan.py --no-headless       skip headless escalations (fast smoke run)
  scan.py --no-sweep          skip the shortlist liveness sweep (parity/debug only)
  scan.py --verbose|-v        stream per-phase / per-platform progress to STDERR (the stdout
                              ledger is unchanged; a long silent run becomes watchable)

What gets auto-logged to seen.jsonl by a scan (everything else is Claude's call):
  dropped/Filtered Out    auto_drop_patterns / auto_drop_title_patterns / the closed-location-
                          list detector matched, OR (opt-in per profile) a hard-eligibility drop
                          on work_arrangement_mismatch / employment_off_target /
                          non_target_language when the profile sets that filter to "drop" mode
  dropped/Stale-Expired   liveness check said stale (mechanical) — incl. the sweep's
                          post-shortlist retirements (ARCHITECTURE.md §6)
  unverified_blocked      no JD obtainable AND liveness unverifiable — confirmed dead end
                          (SysMap rule; suppressed on future scans, reason updated if later resolved)
  applied (back-fill)     scan-start reconciliation (3a.4, D8): a role the Application Companion
                          recorded as applied (Tracker row) is READ from the Tracker and its
                          matching seen.jsonl record flipped shortlisted→applied, so it dedups
                          this run and leaves the sweep's scope. Token-gated, idempotent,
                          READ-ONLY on the Tracker (firewall intact); no fetch/filter/score change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arch_review
import check_links
import dedup
import fetch_boards
import linkedin_tripwire
import paths
import profile_loader
import salary
import sweep


def validate_config(cfg: dict) -> None:
    """Invariant #14 (Pinpoint lesson): every active platform must have a tier, and every
    platform must be reachable by a run selector — a config error, not a silent skip."""
    errors = []
    for p in cfg["platforms"]:
        if p.get("active") and p.get("tier") not in (1, 2, 3):
            errors.append(f"platform {p.get('name')!r} is active but has no valid tier")
        if p.get("active") and not (p.get("urls") or p.get("api") or p.get("api_pattern")
                                    or p.get("slug") in fetch_boards.HANDLERS):
            errors.append(f"platform {p.get('name')!r} has no fetch entry point")
    if errors:
        raise SystemExit("config validation FAILED:\n  " + "\n  ".join(errors))


def _keyword_match(title: str, keywords: list[str]) -> str | None:
    t = (title or "").lower()
    for k in keywords:
        if k in t:
            return k
    return None


def _fresh(posted_at, cutoff: datetime) -> bool:
    if not posted_at:
        return True  # undated → cannot scope; keep (NoDesk rule: unverified-by-default is a flag, not a drop)
    s = str(posted_at)
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00")[:19]).replace(tzinfo=timezone.utc)
            return dt >= cutoff
        dt = datetime.strptime(s[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return True


# --- Non-target-language JD detector (4.1 → 4.6 generalized). Lesson origin: JustJoin.it PM
# offers with Polish-only JDs/ATS forms despite international tags — not caught by any keyword or
# location filter, discovered only at apply time. Generalized (Borjan 2026-07-19): the constraint
# is not "not English", it is "not in the languages the USER can apply in" — a user may set
# German primary + English secondary, so a German JD is fine and everything else drops. Detection
# scores the dominant language by function-word frequency against a small known set; the profile's
# `search.languages` (default ["en"]) is the acceptable set. Conservative: fires only on
# substantial text whose dominant language is KNOWN and NOT in the target set — an unknown or
# mixed JD is never flagged (false negatives are the safe side).
_LANG_STOPWORDS = {
    "en": frozenset("the and for with you are our will this that have from your about who what "
                    "would should must team work experience they their been were which while when has".split()),
    "pl": frozenset("się jest oraz dla lub jako że praca doświadczenie umiejętności zespół wymagania "
                    "stanowisko obowiązki mile widziane znajomość firmy poszukujemy nasz".split()),
    "de": frozenset("und der die das mit für sie wir ist auf von den dem ein eine im zu als "
                    "werden unsere deine erfahrung kenntnisse aufgaben".split()),
    "es": frozenset("de la que el en los una para con por las del al se su como más "
                    "experiencia conocimientos equipo trabajo empresa".split()),
    "fr": frozenset("le la les des une pour avec vous nous est dans que qui sur au aux "
                    "votre notre expérience compétences équipe entreprise".split()),
    "it": frozenset("di che il la le per con una del gli nel come più sono nostro "
                    "esperienza competenze squadra azienda lavoro".split()),
    "nl": frozenset("de het een van en met voor zijn wij je onze aan door bij ervaring "
                    "kennis team werk bedrijf".split()),
    "pt": frozenset("de que os para com uma por das dos como mais são nossa "
                    "experiência conhecimentos equipa empresa trabalho".split()),
}
# Diacritic sets that BOOST a language's score when present (a cheap disambiguator; en has none).
_LANG_DIACRITICS = {"pl": "ąćęłńóśźż", "de": "äöüß", "fr": "àâçéèêëîïôûùüÿœ",
                    "es": "áíñóúü¿¡", "it": "àèéìíòóù", "pt": "ãõáâàçéêíóôú"}


def detect_language(text: str) -> str | None:
    """Best-guess dominant language code from _LANG_STOPWORDS, or None if too little text /
    no language scores distinctively. Diacritics nudge the score for languages that use them."""
    words = re.findall(r"[^\W\d_]+", (text or "").lower(), flags=re.UNICODE)
    if len(words) < 50:
        return None  # too little text to judge
    n = len(words)
    scores = {lang: sum(1 for w in words if w in sw) / n for lang, sw in _LANG_STOPWORDS.items()}
    for lang, diac in _LANG_DIACRITICS.items():
        if any(ch in diac for ch in text):
            scores[lang] = scores.get(lang, 0) + 0.01
    best = max(scores, key=scores.get)
    return best if scores[best] >= 0.02 else None  # below floor = indistinct, don't guess


def language_flag(text: str, target_langs: set[str]) -> tuple[str | None, str]:
    """Return ('non_target_language', note) when the JD's dominant language is known and not in
    the user's acceptable `target_langs` set. Unknown/indistinct language never flags."""
    lang = detect_language(text)
    if lang and lang not in target_langs:
        return "non_target_language", (f"JD appears predominantly '{lang}' — not in the profile's "
                                       f"languages {sorted(target_langs)} (local-hire / apply-wall signal)")
    return None, ""


# --- Stated-language-requirement detector (2026-07-20, borjan-pm scan lesson). Distinct from
# language_flag above: that reads the JD's OWN dominant language. This one fires when a JD written
# IN A TARGET LANGUAGE (English) nonetheless STATES a hard requirement in a NON-target language —
# "Polish C1", "fluent Polish", "native German", or "application must be submitted in Polish".
# Four of five of Borjan's 2026-07-20 declines were exactly this shape (Addepto/Finture/TT MS
# Polish C1/C2/fluency, Vazco apply-in-Polish); detect_language() reads them as 'en' (a target
# language) so non_target_language never fires, and the local-hire barrier reaches the shortlist
# where only the judgment layer catches it — by hand, every single time. Conservative: a
# nice-to-have / "a plus" language mention never flags; only requirement-strength wording next to a
# non-target language name does. Flag-only (scripts flag, Claude decides) — no mechanical drop.
_LANG_NAMES = {
    "polish": "pl", "german": "de", "french": "fr", "spanish": "es", "italian": "it",
    "dutch": "nl", "portuguese": "pt", "english": "en", "czech": "cs", "slovak": "sk",
    "slovenian": "sl", "hungarian": "hu", "romanian": "ro", "bulgarian": "bg", "croatian": "hr",
    "serbian": "sr", "ukrainian": "uk", "russian": "ru", "greek": "el", "turkish": "tr",
    "swedish": "sv", "norwegian": "no", "danish": "da", "finnish": "fi", "estonian": "et",
    "latvian": "lv", "lithuanian": "lt",
}
# Requirement-strength wording that, in the same window as a language name, marks a real barrier.
# Deliberately excludes generic level words (b2/advanced alone) that collide with JD boilerplate
# ("B2B", "advanced tooling") — the C1/C2/fluent/native/proficient/speaking set is unambiguous.
_LANG_REQ = re.compile(
    r"(c1|c2|fluent|fluency|fluently|native|proficien\w*|mother[\s-]?tongue|command of|"
    r"upper[\s-]?intermediate|speaking|must speak|required|mandatory)")
# Nice-to-have qualifiers — if present in the window, the language is optional, NOT a barrier.
_LANG_NICE = re.compile(
    r"(nice to have|a plus|advantage|asset|welcome|optional|beneficial|preferred|desirable|"
    r"bonus|not required|not mandatory|would be nice|is a plus)")
# "apply / CV / application … in <lang>" — an apply-wall in a non-target language.
_APPLY_IN = re.compile(
    r"(appl(?:y|ication|ications|ying)|cv|resume|résumé|cover\s+letter|correspondence)"
    r"[^.\n]{0,30}\bin\s+(" + "|".join(_LANG_NAMES) + r")\b")
# Per-language-name word-boundary patterns, compiled ONCE at import (2026-07-21 perf finding
# A#7): stated_language_requirement's part (b) scans the JD once per non-target language name
# — up to 26 full-text passes per survivor — and previously rebuilt the `\bNAME\b` pattern
# string on every pass of every candidate. The names are a static set, so the patterns are
# hoisted here; the loop below just indexes this map.
_LANG_NAME_RES = {nm: re.compile(rf"\b{nm}\b") for nm in _LANG_NAMES}


def stated_language_requirement(text: str, target_langs: set[str]) -> tuple[str | None, str]:
    """Return ('stated_language_requirement', note) when a JD states a hard proficiency requirement
    in a NON-target language, or requires applying in one. Conservative: an explicit nice-to-have
    mention is skipped; only requirement-strength wording next to a non-target language name fires.
    Flag-only — the judgment layer decides."""
    low = (text or "").lower()
    if not low:
        return None, ""
    # (a) apply-wall: "application must be submitted in Polish", "CV in German".
    for am in _APPLY_IN.finditer(low):
        code = _LANG_NAMES.get(am.group(2))
        if code and code not in target_langs:
            snip = " ".join(low[max(0, am.start() - 12): am.end() + 12].split())
            return "stated_language_requirement", (
                f"JD requires applying in {am.group(2).capitalize()} ('{code}' not in the profile's "
                f"languages {sorted(target_langs)}) — apply-wall barrier: \"…{snip}…\"")
    # (b) proficiency requirement next to a non-target language name.
    for nm, code in _LANG_NAMES.items():
        if code in target_langs:
            continue
        for m in _LANG_NAME_RES[nm].finditer(low):
            win = low[max(0, m.start() - 45): m.end() + 45]
            if _LANG_NICE.search(win):
                continue                              # explicitly optional — not a barrier
            if _LANG_REQ.search(win):
                snip = " ".join(win.split())
                return "stated_language_requirement", (
                    f"JD states a {nm.capitalize()} proficiency requirement ('{code}' not in the "
                    f"profile's languages {sorted(target_langs)}) — likely a local-hire barrier the "
                    f"fit score misses: \"…{snip}…\"")
    return None, ""


# --- Stated-start-date-in-the-past detector (4.1, Cyclad lesson: posted months ago,
# the JD's own start/target date already gone, the platform still shows it live). Only
# dates in an explicit start/kick-off context count — never a stray date in the body.
_MONTHS = {m: i for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_START_CTX = re.compile(
    r"(start(?:ing|s)?|kick[- ]?off|target start|expected start|planned start|"
    r"project start|earliest start|commencement|commenc\w*)", re.I)
_DATE_PATS = [
    (re.compile(r"(\d{1,2})[./](\d{4})"), "num"),                                  # 06.2026
    (re.compile(r"(\d{4})-(\d{2})"), "iso"),                                       # 2026-06
    (re.compile(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})", re.I), "mon"),
]


def start_date_passed(text: str, today: date) -> tuple[bool, str]:
    """(True, 'YYYY-MM') if the JD states a start/target month already before this month."""
    for cm in _START_CTX.finditer(text or ""):
        window = text[cm.end():cm.end() + 45]
        for pat, kind in _DATE_PATS:
            m = pat.search(window)
            if not m:
                continue
            try:
                if kind == "num":
                    mo, yr = int(m.group(1)), int(m.group(2))
                elif kind == "iso":
                    yr, mo = int(m.group(1)), int(m.group(2))
                else:
                    mo, yr = _MONTHS[m.group(1).lower()[:3]], int(m.group(2))
            except (ValueError, KeyError):
                continue
            if 1 <= mo <= 12 and 2000 <= yr <= 2100 and (yr, mo) < (today.year, today.month):
                return True, f"{yr:04d}-{mo:02d}"
    return False, ""


# --- Seniority + employment-type signals (Phase 2, D7/D8). ADDITIVE annotations only —
# never a machine drop. target_seniority (soft/strict) and employment_type (hard) are
# ENFORCED by the judgment layer (skills/job-scout-run) reading these; scan.py just
# contributes the cheap mechanical signal where a posting states it plainly. Both run
# ONLY when the profile sets the field — a profile that sets neither (e.g. borjan-pm)
# gets byte-identical candidate records.
def detect_seniority(title: str, lexicon: dict) -> str | None:
    """Map a posting TITLE to a band via the resolved lexicon (base + template
    seniority_titles). Word-boundary, case-insensitive; LONGEST key wins on overlap
    ('tech lead' beats 'lead'). Title only — the JD is the judgment layer's to read."""
    t = (title or "").lower()
    for term in sorted(lexicon, key=len, reverse=True):
        if re.search(r"\b" + re.escape(term) + r"\b", t):
            return lexicon[term]
    return None


_EMPLOYMENT_MARKERS = {
    "part_time": r"\bpart[\s-]?time\b",
    "full_time": r"\bfull[\s-]?time\b",
    "contract": r"\b(contract(?:or)?|fixed[\s-]term|temporary|interim)\b",
    "b2b": r"\bb2b\b",
    "freelance": r"\bfreelanc\w*\b",
    "internship": r"\b(intern(?:ship)?|trainee|working student|apprentice)\b",
}


def detect_employment(text: str) -> set[str]:
    """Employment-type tokens a posting states plainly (title + JD). Conservative —
    a miss is not 'full-time', it's 'unstated' (the judgment layer decides)."""
    t = (text or "").lower()
    return {tok for tok, pat in _EMPLOYMENT_MARKERS.items() if re.search(pat, t)}


# Work-arrangement (D-remote): remote / hybrid / on_site as a posting states it. The
# platform's structured location tag ("Kraków (hybrid)", "Warszawa (remote)" on JustJoin.it)
# is authoritative when present — it is a curated field, not incidental body prose; a bare
# "remote" in a JD menu/footer must not override a "(hybrid)" loc tag. Falls back to loc+JD
# keywords only when the loc carries no explicit tag. Vocab matches search.work_model
# (remote/hybrid/on_site). Conservative: no signal = unstated, never a machine drop on its own.
_ARRANGEMENT_MARKERS = {
    "remote": r"\b(fully[\s-]?remote|remote[\s-]?first|100%\s*remote|remote)\b",
    "hybrid": r"\bhybrid\b",
    "on_site": (r"\b(on[\s-]?site|in[\s-]?office|from the office|stationary)\b"
                r"|\b\d+\s*days?\b[^.]{0,20}\b(office|on[\s-]?site|onsite)\b"),
}
_LOC_ARR_TAG = re.compile(r"\((remote|hybrid|on[\s-]?site|onsite|stationary|office)\)")
_LOC_ARR_TAG_MAP = {"onsite": "on_site", "on-site": "on_site", "on site": "on_site",
                    "stationary": "on_site", "office": "on_site"}


def detect_work_arrangement(loc: str, jd: str) -> set[str]:
    """Return the arrangement(s) a posting states, subset of {remote, hybrid, on_site}.
    A structured loc tag wins outright; otherwise scan loc+JD for the markers.
    2026-07-19 lesson: JustJoin.it also tags on-site postings "(office)" — a synonym
    missed on first pass, which let 6 on-site roles leak past a remote-only profile."""
    tag = _LOC_ARR_TAG.search((loc or "").lower())
    if tag:
        t = tag.group(1)
        return {_LOC_ARR_TAG_MAP.get(t, t)}
    hay = f"{(loc or '').lower()} {(jd or '').lower()}"
    return {name for name, pat in _ARRANGEMENT_MARKERS.items() if re.search(pat, hay)}


def hard_filter(cand: dict, hf: dict) -> tuple[str | None, list[str]]:
    """Returns (drop_reason, flags). Drop only on the machine-certain patterns."""
    hay = " ".join(str(cand.get(k) or "") for k in ("title", "loc", "salary", "jd_text"))
    flags = []
    # Title-scoped hard-drops (role_hard_drop_terms, task #12): a no-go domain naming itself in
    # the TITLE is a mechanical drop. Matched against the title alone — a body mention stays a
    # judgment flag (below), never a silent drop.
    title = str(cand.get("title") or "")
    for name, pat in (hf.get("auto_drop_title_patterns") or {}).items():
        if re.search(pat, title):
            return f"auto-drop: {name}", flags
    for name, pat in (hf.get("auto_drop_patterns") or {}).items():
        if re.search(pat, hay):
            return f"auto-drop: {name}", flags
    for name, pat in (hf.get("flag_patterns") or {}).items():
        if re.search(pat, hay):
            flags.append(name)
    # Closed-location-list enumeration detector (filter #13, 2.10.0 — generalized:
    # must_include comes from the profile's location_match_terms)
    det = hf.get("eu_country_list_detector") or {}
    countries = det.get("countries", [])
    found = [c for c in countries if re.search(rf"\b{re.escape(c)}\b", hay)]
    if len(found) >= 4:
        open_ended = any(m.lower() in hay.lower() for m in det.get("open_ended_markers", []))
        named = any(m.lower() in hay.lower() for m in det.get("must_include", []))
        if not open_ended and not named:
            return "auto-drop: closed_location_list (closed list, candidate location absent)", flags
    return None, flags


def _log_drop(c: dict, status: str, reason: str, notes: str) -> None:
    """Append one mechanical-drop record for candidate `c`, through dedup's canonical
    record constructor. Was four hand-built raw-dict literals in run_scan (2026-07-21
    coupling finding 4.1) — same 11-field shape each, varying only status/reason/notes —
    so a field rename drifted silently against notion_sync's field-by-field reader."""
    dedup.append(dedup.make_seen_record(
        company=c["company"], role=c["title"], locdom=c.get("loc", ""), url=c["url"],
        platform=c["platform"], status=status, reason=reason, notes=notes))


def print_plan(cfg: dict) -> None:
    """--plan: the resolved scan plan, zero network. The dry-run acceptance surface."""
    prof = cfg["profile"]
    print(f"## Scan plan — profile {cfg['profile_id']!r} "
          f"(template {prof.get('template') or 'none'}, stream {prof['search']['stream']})")
    print(f"keywords core: {', '.join(cfg['keywords']['core'])}")
    print(f"keywords expanded: {', '.join(cfg['keywords']['expanded'])}")
    hf = cfg["hard_filters"]
    print(f"auto-drop filters: {', '.join(hf['auto_drop_patterns'])}")
    if hf.get("auto_drop_title_patterns"):
        print(f"auto-drop (title-only) filters: {', '.join(hf['auto_drop_title_patterns'])}")
    print(f"flag filters: {', '.join(hf['flag_patterns'])}")
    det = hf.get("eu_country_list_detector")
    if det:
        print(f"closed-location-list detector: must_include {det['must_include']}")
    sf = hf["salary_floor"]
    if sf.get("floor"):
        fte = sf.get("fte_fraction")
        fte_note = f", pro-rated to {fte} FTE" if fte is not None else ""
        print(f"salary floor: {sf['floor']['amount']} {sf['floor']['currency']} "
              f"{sf['floor']['basis']}/{sf['floor']['period']} "
              f"(canonical ≈{sf['canonical_gross_month']} {sf['currency']} gross/month{fte_note})")
    else:
        print("salary floor: none set — below-floor first-pass disabled; "
              "judgment-layer estimation via template heuristics (D20)")
    active = fetch_boards.active_platforms(cfg)
    print(f"\nrotation ({len(active)} active platforms, tier order):")
    for p in active:
        targets = (p.get("api") or []) + (p.get("urls") or [])
        boards = f" boards={p.get('boards')}" if p.get("api_pattern") else ""
        print(f"  T{p['tier']} {p['name']:36} {p['fetch_mode']:9}"
              f" {targets[0] if targets else p.get('api_pattern', '?')}{boards}")
        for t in targets[1:]:
            print(f"      {'':36}          {t}")
    for name, why in (cfg.get("skipped_platforms") or {}).items():
        print(f"  ⏭  {name}: {why}")
    lt = cfg["linkedin_tripwire"]
    print(f"linkedin tripwire: enabled={lt['enabled']} keywords={lt['keywords']} "
          f"locations={lt['locations']}")
    if cfg["notion"].get("dry_run"):
        print("notion: DRY-RUN profile — writes refused")
    print(f"schedule: freshness {cfg['scan']['freshness_window_h']}h, "
          f"full sweep {cfg['scan']['full_sweep_dow']}, "
          f"shortlist-sweep every {cfg['sweep']['recheck_interval_h']}h")


def run_scan(cfg: dict, half: str | None, full_sweep: bool, use_headless: bool = True,
             run_shortlist_sweep: bool = True, verbose: bool = False,
             gap_hours: float | None = None) -> dict:
    def _log(msg: str) -> None:
        """Opt-in progress to STDERR (never stdout — the ledger stays machine-parseable).
        Additive observability only; changes nothing the scan fetches/filters/scores/writes."""
        if verbose:
            print(f"[scan] {msg}", file=sys.stderr, flush=True)

    validate_config(cfg)
    # ---- scan-start reconciliation (3a.4, D8): READ the Applications Tracker and back-fill
    # matching seen.jsonl records to `applied` BEFORE dedup + the sweep, so a companion-recorded
    # application dedups this run and exits the sweep's scope. Token-gated + idempotent; the
    # Tracker firewall holds (read-only); board fetch/filter/score untouched. Runs before
    # load_seen so the reload reflects the back-filled statuses.
    import notion_sync
    _log("reconciling applied roles from the Applications Tracker (read-only)…")
    reconcile = notion_sync.reconcile_applied_from_tracker(cfg)
    if reconcile.get("tokenless"):
        _log("  reconcile skipped — no NOTION_TOKEN")
    elif reconcile.get("skipped"):
        _log(f"  reconcile skipped — {reconcile['skipped']}")
    else:
        _log(f"  reconcile: {reconcile['tracker_rows']} tracker rows, "
             f"{reconcile['backfilled']} back-filled, {reconcile['already']} already")
    # #13: read Passed/Seen resolutions back into local state (Notion-resolved rows stop looking
    # `shortlisted` locally). Read-only on Notion, token-gated, idempotent.
    resolutions = notion_sync.reconcile_resolutions_from_passed_seen(cfg)
    if not resolutions.get("tokenless") and not resolutions.get("skipped"):
        _log(f"  resolutions: {resolutions['resolved']} resolved from Passed/Seen "
             f"(of {resolutions['ps_rows']} rows, {resolutions['already']} already)")
    seen = dedup.load_seen()
    keywords = [k.lower() for k in (cfg["keywords"]["core"] + cfg["keywords"]["expanded"])]
    caps = cfg.get("caps", {})
    window_h = int(cfg.get("scan", {}).get("freshness_window_h", 48))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_h)
    today = date.today().isoformat()
    label = "AM" if datetime.now().hour < 12 else "PM"

    # ---- scan-gap hours (2026-07-20 health finding): Himalayas' unfiltered newest-jobs feed
    # needs to know how far back to page — a fixed page count either wastes time on a fresh
    # profile's short gaps or leaves a real blind spot after a multi-day skip (found live: real
    # gaps ranged 5-98h, while a fixed 1000-job window only reached ~10h back at the site's
    # observed ~100 jobs/hour rate). Computed once here (read-only peek at runs.json BEFORE this
    # run's own entry is added) and threaded through cfg so fetch_himalayas can size its own
    # pagination to the ACTUAL elapsed gap instead of guessing a constant.
    scan_gap_hours = 24.0  # first-ever scan for this profile: reasonable default, not a guess of 0
    _runs_peek_path = paths.runs_path()
    if _runs_peek_path.exists():
        try:
            _runs_peek = json.loads(_runs_peek_path.read_text(encoding="utf-8"))
            _last_ran_at = max(
                (rec["ran_at"] for day, labels in _runs_peek.items()
                 if day not in ("recompute", "health_review", "arch_review") and isinstance(labels, dict)
                 for rec in labels.values() if isinstance(rec, dict) and rec.get("ran_at")),
                default=None)
            if _last_ran_at:
                _last_dt = datetime.fromisoformat(_last_ran_at)
                scan_gap_hours = max(0.0, (datetime.now(timezone.utc) - _last_dt).total_seconds() / 3600)
        except (json.JSONDecodeError, ValueError):
            pass  # malformed/legacy runs.json — fall back to the default above, never crash the scan
    if gap_hours is not None:  # manual override (--gap-hours) — e.g. a one-off deep catch-up
        scan_gap_hours = gap_hours
    cfg["scan_gap_hours"] = scan_gap_hours

    platforms = fetch_boards.active_platforms(cfg)
    if half:  # degraded/manual mode only — the r2 default is the full rotation
        mid = (len(platforms) + 1) // 2
        platforms = platforms[:mid] if half == "AM" else platforms[mid:]

    # Concurrent fetch (2026-07-21): platforms are different hosts, so fetching them in
    # parallel doesn't add load to any single server beyond what it already tolerates
    # sequentially (_polite() rate-limits per-host, unaffected by cross-platform concurrency).
    # fetch_boards.fetch_many() owns the concurrency policy (bulkhead: separately-pooled caps
    # for headless vs. HTTP platforms) and returns results in ORIGINAL tier-order, not
    # completion order — so the rest of this function (ledger, candidates JSON) is
    # byte-identical to the old sequential run, only faster.
    _log(f"fetching {len(platforms)} active platforms (tier order, up to "
         f"{fetch_boards.MAX_CONCURRENT_HTTP} concurrent / "
         f"{fetch_boards.MAX_CONCURRENT_HEADLESS} concurrent headless)…")

    def _log_progress(done: int, total: int, p: dict, r: dict) -> None:
        _log(f"  [{done}/{total}] T{p.get('tier','?')} {p.get('name','?')} → "
             f"{len(r.get('candidates') or [])} raw"
             + (" · SOURCE DOWN" if r.get('source_down') else ""))

    results = fetch_boards.fetch_many(platforms, cfg, on_progress=_log_progress)
    if cfg["linkedin_tripwire"].get("enabled", True):
        _log("  LinkedIn tripwire…")
        # Same fault-isolation boundary every board gets via fetch_platform (a fetcher bug
        # must never take down the whole run). The tripwire was previously called raw, outside
        # that boundary, then dereferenced with r["source_down"]/r["note"] below — a raise or
        # missing key here would crash the entire scan (2026-07-21 finding A#1).
        try:
            results.append(linkedin_tripwire.fetch_tripwire(cfg))
        except Exception as exc:
            # mirror the tripwire's own result shape (http_ok/healed are read with .get defaults
            # downstream, exactly as they are for a normal tripwire result which omits them).
            results.append({"platform": linkedin_tripwire.PLATFORM, "candidates": [],
                            "source_down": True,
                            "note": f"tripwire crashed: {type(exc).__name__}: {exc}"})

    sources_down = [r["platform"] for r in results if r["source_down"]]
    notes = {r["platform"]: r["note"] for r in results if r["note"]}
    # Per-platform health telemetry (HEALTH_MONITORING.md Layer 1): raw enumeration count +
    # whether the board actually answered (http_ok). `http_ok` is what lets health.py tell a
    # silent selector break (200 + HTML, 0 rows) apart from a plain outage. Recorded per run so
    # a baseline accrues the moment a board goes active. `healed` surfaces Layer-1.5 recoveries.
    platform_stats = {
        r["platform"]: {
            "raw": len(r.get("candidates") or []),
            "source_down": bool(r["source_down"]),
            "http_ok": bool(r.get("http_ok", not r["source_down"])),
        }
        for r in results
    }
    healed = {r["platform"]: r["healed"] for r in results if r.get("healed")}

    # ---- triage: keyword filter → freshness → dedup → hard filters
    new_cands, dropped, link_dead = [], 0, 0
    # Per-param drop telemetry (Borjan balance ask): count drops by the PARAM that caused them and
    # the funnel size they were measured against, so a single hard filter can't silently zero the
    # results. `funnel_in` = candidates that passed keyword+freshness+dedup and reached the
    # mechanical/judgment filters (the honest denominator for "param X dropped N of M").
    drop_by_param: dict[str, int] = {}
    funnel_in = 0

    def _drop_param(reason: str) -> str:
        # "auto-drop: us_only (…)" → "us_only"; "auto-drop: closed_location_list (…)" → that; else raw.
        m = re.match(r"auto-drop:\s*([a-z0-9_]+)", reason or "")
        return m.group(1) if m else (reason or "unknown").split(":")[0].strip()

    for r in results:
        for c in r["candidates"]:
            kw = _keyword_match(c["title"], keywords)
            if not kw:
                continue  # enumeration noise, never a logged drop
            if not full_sweep and not _fresh(c.get("posted_at"), cutoff):
                continue  # outside the delta window; weekly sweep catches strays
            hit = dedup.match({"url": c["url"], "company": c["company"], "role": c["title"],
                               "locdom": c.get("loc", "")}, seen)
            if hit:
                continue  # silent — both-log dedup, URL-exact first (2.3.0)
            c["keyword_matched"] = kw
            funnel_in += 1
            reason, flags = hard_filter(c, cfg.get("hard_filters", {}))
            c["flags"] = sorted(set((c.get("flags") or []) + flags))
            if reason:
                _log_drop(c, "dropped", "Filtered Out", reason)
                dropped += 1
                drop_by_param[_drop_param(reason)] = drop_by_param.get(_drop_param(reason), 0) + 1
                continue
            new_cands.append(c)

    _log(f"triage done: {len(new_cands)} new candidates survive keyword+freshness+dedup+hard-filter "
         f"({dropped} auto-dropped)")

    # ---- full JD reads for survivors lacking one (local parses; cap is politeness)
    max_reads = int(caps.get("max_full_reads_per_run", 15))
    _log(f"reading full JDs (up to {max_reads})…")
    reads = 0
    for c in new_cands:
        c["source_url"] = None
        if c.get("jd_text") and len(c["jd_text"]) > 400:
            c["jd_status"] = "from_enumeration"
        elif c["platform"] == "LinkedIn (tripwire)":
            c["jd_status"] = "linkedin_card_only"
        elif reads < max_reads:
            text, html, method = fetch_boards.fetch_jd(c["url"])
            reads += 1
            c["jd_status"] = f"fetched_{method}" if text else "fetch_failed"
            if text:
                c["jd_text"] = text
                src = fetch_boards.resolve_source_url(html)
                if src and dedup.norm_url(src) != dedup.norm_url(c["url"]):
                    c["source_url"] = src  # the ATS URL is the liveness authority (2.7.0)
        else:
            c["jd_status"] = "read_cap_deferred"

    # ---- liveness pass on the authoritative URL set
    to_check = [(c, c.get("source_url") or c["url"]) for c in new_cands
                if c["platform"] != "LinkedIn (tripwire)"]
    verdicts = {}
    if to_check:
        urls = [u for _, u in to_check]
        _log(f"liveness pass on {len(urls)} URLs…")
        for res in check_links.check_urls(urls, cfg, use_headless=use_headless):
            verdicts[res["url"]] = res
    survivors = []
    for c in new_cands:
        if c["platform"] == "LinkedIn (tripwire)":
            c["link_status"] = "❓ tripwire card"
            survivors.append(c)
            continue
        v = verdicts.get(c.get("source_url") or c["url"], {"verdict": "unverifiable_direct"})
        if v["verdict"] == "stale":
            _log_drop(c, "dropped", "Stale/Expired",
                      f"link check: {v.get('note', '')} (source URL {c.get('source_url') or 'n/a'})")
            link_dead += 1
            drop_by_param["stale"] = drop_by_param.get("stale", 0) + 1
            continue
        if v["verdict"] == "unverifiable_direct" and not c.get("jd_text"):
            # nothing to evaluate and no way to verify: confirmed dead end (2.6.0 / SysMap)
            _log_drop(c, "unverified_blocked", "Unverified/Blocked", f"blocked: {v.get('note', '')}")
            dropped += 1
            drop_by_param["unverified_blocked"] = drop_by_param.get("unverified_blocked", 0) + 1
            continue
        c["link_status"] = {"live": "✅ live",
                            "unverifiable_direct": "❓ unverified"}.get(v["verdict"], "❓ unverified")
        survivors.append(c)

    # ---- salary assessment (4.0, ADDITIVE metadata for the judgment layer — never a
    # machine drop; unstated salary applies the template's estimation heuristics)
    floor_norm = cfg["hard_filters"]["salary_floor"]
    defaults = cfg.get("defaults", {})
    for c in survivors:
        text = " ".join(str(c.get(k) or "") for k in ("salary", "jd_text"))
        c["salary_assessment"] = salary.assess(text, floor_norm, defaults)

    # ---- candidate-quality + prior-history annotations (4.1 judgment-layer inputs;
    # ADDITIVE flags/notes only — never a machine drop, the judgment layer decides).
    # Runs on FULL jd_text, before it is truncated for the cache below.
    comp_idx = dedup.company_index()
    search_cfg = cfg.get("profile", {}).get("search", {})
    target_seniority = search_cfg.get("target_seniority")          # None unless profile sets it
    employment_type = search_cfg.get("employment_type")           # None unless profile sets it
    et_accept = set((employment_type or {}).get("accept") or [])
    seniority_lexicon = cfg.get("seniority_lexicon", {})
    hf_cfg = cfg.get("hard_filters", {})
    work_model = set(search_cfg.get("work_model") or [])           # required field, e.g. {remote}
    wa_mode = hf_cfg.get("work_arrangement", "off")               # off (default) | flag | drop
    target_langs = set(search_cfg.get("languages") or ["en"])    # languages the user can apply in
    for c in survivors:
        flags = set(c.get("flags") or [])
        if not dedup.norm_company(c.get("company", "")):
            flags.add("missing_company")            # scan-side data-quality note (lesson 6)
        jd = c.get("jd_text") or ""
        lang_flag, lang_note = language_flag(jd, target_langs)   # non-target-language JD (lesson 1, generalized)
        if not lang_flag:
            # Title-level fallback: a JD-less/light dedup twin (empty jd_text) never reaches the
            # 50-word floor, so a non-target-market title ("bankowość", "z praktyką") slips through.
            # A title carrying a NON-target language's diacritics still signals it.
            title_l = (c.get("title") or "").lower()
            for lg, diac in _LANG_DIACRITICS.items():
                if lg not in target_langs and any(ch in diac for ch in title_l):
                    lang_flag = "non_target_language"
                    lang_note = f"title carries '{lg}' diacritics — likely {lg}-market posting (JD unavailable to confirm)"
                    break
        if lang_flag:
            flags.add(lang_flag)
            c["language_note"] = lang_note
        req_flag, req_note = stated_language_requirement(jd, target_langs)  # stated non-target-lang req (2026-07-20)
        if req_flag:
            flags.add(req_flag)
            c["language_requirement_note"] = req_note
        passed, when = start_date_passed(jd, date.today())  # stated start gone (lesson 4)
        if passed:
            flags.add("start_date_passed")
            c["start_date_note"] = f"stated start {when} is already past (posting may be stale)"
        # Prior reqs from the same company — surface so the judgment layer never has to
        # re-ask "did I already apply to a variant of this?" (lessons 2 + 3).
        prior = [r for r in comp_idx.get(dedup.norm_company(c.get("company", "")), [])
                 if dedup.norm_url(r.get("url", "")) != dedup.norm_url(c["url"])]
        if prior:
            c["company_prior"] = [
                {"role": r.get("role", ""), "locdom": r.get("locdom", ""),
                 "status": r.get("status", ""), "reason": r.get("reason", "")}
                for r in prior[:8]]
            fam = dedup.role_family(c["title"])
            applied_variants = [r for r in prior if r.get("status") == "applied"
                                and dedup.role_family(r.get("role", "")) == fam]
            if len(applied_variants) >= 2:  # location-agnostic country-clone saturation
                flags.add("applied_variant_saturation")
        # Seniority signal (D7) — only when the profile targets bands. seniority_off_target
        # is a soft flag; the judgment layer deprioritizes (soft) or drops (strict).
        if target_seniority:
            band = detect_seniority(c.get("title", ""), seniority_lexicon)
            if band:
                c["seniority_detected"] = band
                if band not in set(target_seniority.get("bands") or []):
                    flags.add("seniority_off_target")
        # Employment-type signal (D8) — only when the profile constrains it and 'any' is
        # not the escape. Off-target = a stated type, none of which is in the accept set.
        if employment_type and "any" not in et_accept:
            detected = detect_employment(" ".join(str(c.get(k) or "") for k in ("title", "jd_text")))
            if detected:
                c["employment_detected"] = sorted(detected)
                off_target = not (detected & et_accept)
                # Part-time seeker guard: an explicitly FULL-TIME posting is off-target even when
                # a contract/b2b model co-occurs. "Full-time B2B" is full-time HOURS on a B2B
                # contract — time-commitment and contract-vehicle are orthogonal, so the accept
                # match on 'contract'/'b2b' must NOT mask the full-time disqualifier (the JustJoin.it
                # leak: 36 full-time roles reached Ani's part-time shortlist this way). Only when
                # part-time isn't ALSO offered.
                if "part_time" in et_accept and "full_time" in detected and "part_time" not in detected:
                    off_target = True
                if off_target:
                    flags.add("employment_off_target")
        # Work-arrangement signal (D-remote) — only when the profile opts in (wa_mode != off).
        # search.work_model is required, but enforcing it is opt-in so profiles that share the
        # remote default (e.g. borjan-pm) are byte-identical until they turn this on. Mismatch =
        # a stated arrangement, none of which the profile accepts (hybrid/on-site vs remote-only)
        # and remote is NOT also offered.
        if work_model and wa_mode != "off":
            arr = detect_work_arrangement(c.get("loc", ""), jd)
            if arr:
                c["work_arrangement_detected"] = sorted(arr)
                if not (arr & work_model):
                    flags.add("work_arrangement_mismatch")
        c["flags"] = sorted(flags)

    # ---- opt-in hard-eligibility enforcement (D-remote / D8 drop mode). A profile MAY declare
    # that a machine-certain, impossible-to-satisfy mismatch is a mechanical DROP rather than a
    # judgment flag — the same class as us_only/closed_location_list (you cannot work a Kraków
    # hybrid desk remotely from Skopje). Off by default: with wa_mode=off and em_mode=flag nothing
    # is dropped here, so profiles that don't opt in are byte-identical. Dropped rows go to
    # seen.jsonl as "Filtered Out" (recoverable/auditable), never reaching the shortlist. This is
    # the deliberate flag→drop conversion the doctrine reserves for hard eligibility (CLAUDE.md).
    em_mode = hf_cfg.get("employment_mismatch", "flag")           # flag (default) | drop
    lm_mode = hf_cfg.get("language_mismatch", "flag")             # flag (default) | drop
    if wa_mode == "drop" or em_mode == "drop" or lm_mode == "drop":
        kept = []
        for c in survivors:
            fset = set(c.get("flags") or [])
            reason = None
            param = None
            if wa_mode == "drop" and "work_arrangement_mismatch" in fset:
                param = "work_arrangement"
                reason = (f"work arrangement {c.get('work_arrangement_detected') or '?'} off-target "
                          f"(work_model requires {sorted(work_model)})")
            elif em_mode == "drop" and "employment_off_target" in fset:
                param = "employment_mismatch"
                reason = (f"employment {c.get('employment_detected') or '?'} off-target "
                          f"(accepts {sorted(et_accept)})")
            elif lm_mode == "drop" and "non_target_language" in fset:
                param = "language_mismatch"
                reason = c.get("language_note") or f"non-target language (accepts {sorted(target_langs)})"
            if reason:
                _log_drop(c, "dropped", "Filtered Out", reason)
                dropped += 1
                drop_by_param[param] = drop_by_param.get(param, 0) + 1
                continue
            kept.append(c)
        _log(f"hard-eligibility drop: {len(survivors) - len(kept)} off-target "
             f"(work_arrangement={wa_mode}, employment_mismatch={em_mode}, "
             f"language_mismatch={lm_mode})")
        survivors = kept

    # ---- shortlist liveness sweep (4.0, step 8 — ARCHITECTURE.md §6)
    sweep_counts = {"scope": 0, "checked": 0, "stale": 0, "unverifiable": 0,
                    "escalated": 0, "live": 0, "deferred": 0}
    if run_shortlist_sweep:
        _log("shortlist liveness sweep (re-checking accumulated New — Unreviewed rows)…")
        sweep_counts = sweep.run_sweep(cfg, use_headless=use_headless)
    _log("writing candidates JSON + ledger…")

    # ---- cache JDs, emit candidates JSON
    jd_cache = paths.jd_cache_dir()
    jd_cache.mkdir(parents=True, exist_ok=True)
    for c in survivors:
        if c.get("jd_text"):
            h = hashlib.sha256(c["url"].encode()).hexdigest()[:16]
            (jd_cache / f"{h}.txt").write_text(c["jd_text"], encoding="utf-8")
            c["jd_cache"] = f"state/jd_cache/{h}.txt"
            c["jd_text"] = c["jd_text"][:1500]  # candidates JSON stays skimmable; full text in cache

    # ---- over-constraint nudge (Borjan balance ask): if any single param dropped a large share
    # of the funnel, surface it so a hard filter can't silently zero results. A high share isn't
    # necessarily wrong (Ani's remote-only legitimately drops ~half — Poland is hybrid-heavy), so
    # this INFORMS, never auto-relaxes. Threshold: ≥40% of the candidates that reached filtering.
    drop_nudges = []
    if funnel_in:
        for param, n in sorted(drop_by_param.items(), key=lambda kv: -kv[1]):
            share = n / funnel_in
            if share >= 0.40:
                drop_nudges.append(
                    f"{param} dropped {n}/{funnel_in} ({share:.0%}) — if unexpected, consider "
                    f"relaxing this hard filter (flag instead of drop)")

    out_path = paths.candidates_path()
    out_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": cfg["profile_id"],
        "run": f"{today} {label}", "half": half, "full_sweep": full_sweep,
        "candidates": survivors,
        "sources_down": sources_down, "platform_notes": notes,
        "skipped_platforms": cfg.get("skipped_platforms", {}),
        "shortlist_sweep": sweep_counts,
        "funnel_in": funnel_in, "drop_by_param": drop_by_param, "drop_nudges": drop_nudges,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- runs.json ledger + recompute counter
    runs_path = paths.runs_path()
    runs = json.loads(runs_path.read_text()) if runs_path.exists() else {"recompute": {
        "last": today, "sessions_since": 0,
        "due_at_sessions": cfg["recompute"].get("due_at_sessions", 5)}}
    day = runs.setdefault(today, {})
    day[label] = {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platforms_covered": [r["platform"] for r in results if not r["source_down"]],
        "sources_down": sources_down,
        "platform_stats": platform_stats,
        "healed": healed,
        "new": len(survivors), "dropped": dropped, "link_dead": link_dead,
        "funnel_in": funnel_in, "drop_by_param": drop_by_param, "drop_nudges": drop_nudges,
        "sweep": sweep_counts, "reconcile": reconcile,
        "half": half, "full_sweep": full_sweep,
    }
    runs["recompute"]["sessions_since"] = runs["recompute"].get("sessions_since", 0) + 1
    # health-review counter (HEALTH_MONITORING.md): rides the same mechanism as recompute — the
    # scan prints "⚠ platform health review due" every N sessions, which is Claude's cue to run
    # core/health.py and diagnose flagged boards (Layer 2). core/health.py acks it (resets to 0).
    hr = runs.setdefault("health_review", {"last": today, "sessions_since": 0,
                                           "due_at_sessions": cfg.get("health", {}).get("due_at_sessions", 6)})
    hr["sessions_since"] = hr.get("sessions_since", 0) + 1
    # architecture-review-due counter (CLAUDE.md DoD #5): same rails again — prints "⚠ architecture
    # review due" every N scans as Claude's cue to ASSESS whether a full whole-codebase pass is worth
    # running (a judgment call, not an order). core/arch_review.py --ack resets it after a pass.
    ar = arch_review.bump(runs, cfg.get("arch_review", {}).get("due_at_sessions",
                                                               arch_review.DEFAULT_DUE_AT_SESSIONS))
    runs_path.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- ledger print (replaces the 20-item chat checklist; partial-labeled-partial)
    print(f"## Job Scout scan — {cfg['profile_id']} — {today} {label}"
          + (f" (half={half})" if half else " (full rotation)")
          + (" [full sweep]" if full_sweep else f" [fresh window {window_h}h]"))
    print(f"{len(survivors)} new candidates / {dropped} auto-dropped / {link_dead} link-dead"
          + (f" (of {funnel_in} that reached filtering)" if funnel_in else ""))
    for nudge in drop_nudges:
        print(f"  ⚠ over-constraint: {nudge}")
    covered = [r["platform"] for r in results if not r["source_down"]]
    print(f"covered ({len(covered)}): {', '.join(covered)}")
    print(f"sources down: {', '.join(sources_down) if sources_down else 'none'}")
    # honest-failure floor: a heal is always reported, never a silent paper-over (Layer 1.5)
    for plat, hlist in healed.items():
        print(f"  ✚ healed[{plat}]: {'; '.join(hlist)}")
    for name, why in (cfg.get("skipped_platforms") or {}).items():
        print(f"  ⏭ skipped[{name}]: {why}")
    for plat, note in notes.items():
        if any(k in note for k in ("DEGRADED", "REGRESSED", "no boards")):
            print(f"  note[{plat}]: {note[:110]}")
    print(f"shortlist sweep: {sweep_counts['scope']} unreviewed in scope, "
          f"{sweep_counts['checked']} rechecked, {sweep_counts['stale']} went stale, "
          f"{sweep_counts['unverifiable']} unverifiable"
          + (f" ({sweep_counts['escalated']} escalated — check manually)" if sweep_counts["escalated"] else ""))
    if reconcile.get("tokenless"):
        print("tracker reconcile: skipped — no NOTION_TOKEN (applied-role dedup back-fill not run)")
    elif reconcile.get("skipped"):
        print(f"tracker reconcile: skipped — {reconcile['skipped']}")
    else:
        print(f"tracker reconcile: {reconcile['tracker_rows']} tracker rows, "
              f"{reconcile['backfilled']} back-filled applied, {reconcile['already']} already, "
              f"{reconcile['unmatched']} unmatched")
    dq = {f: sum(1 for c in survivors if f in (c.get("flags") or []))
          for f in ("non_target_language", "start_date_passed", "missing_company",
                    "applied_variant_saturation")}
    dq = {k: v for k, v in dq.items() if v}
    if dq:
        print("  candidate flags: " + ", ".join(f"{k}×{v}" for k, v in dq.items()))
    rc = runs["recompute"]
    if rc["sessions_since"] >= rc.get("due_at_sessions", 5):
        print(f"⚠ tier recompute due: {rc['sessions_since']} sessions since {rc['last']} "
              "(data session with the user — not automated)")
    if hr["sessions_since"] >= hr.get("due_at_sessions", 6):
        print(f"⚠ platform health review due: {hr['sessions_since']} sessions since {hr['last']} "
              "(run `python3 core/health.py` and diagnose flagged boards)")
    if arch_review.is_due(ar):
        print(arch_review.nudge_line(ar))
    print(f"candidates JSON: {out_path.relative_to(paths.REPO_ROOT)}")
    return {"new": len(survivors), "dropped": dropped, "link_dead": link_dead,
            "sweep": sweep_counts, "sources_down": sources_down}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None, help="profile id under profiles/")
    ap.add_argument("--plan", action="store_true",
                    help="print the resolved scan plan without fetching (dry-run)")
    ap.add_argument("--half", choices=["AM", "PM"], default=None,
                    help="degraded/manual half rotation (r2 default is full)")
    ap.add_argument("--full-sweep", action="store_true", help="ignore freshness window")
    ap.add_argument("--gap-hours", type=float, default=None,
                     help="override the auto-computed scan gap (hours since last run) that "
                          "sizes Himalayas' pagination depth — e.g. --gap-hours 168 for a "
                          "one-off ~1-week deep catch-up. Omit for normal runs.")
    ap.add_argument("--no-headless", action="store_true", help="skip headless escalation")
    ap.add_argument("--no-sweep", action="store_true",
                    help="skip the shortlist liveness sweep (parity/debug only)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="stream per-phase / per-platform progress to stderr (the stdout ledger "
                         "is unchanged) — useful for watching a long run")
    args = ap.parse_args()
    config = profile_loader.load(args.profile or paths.get_profile())
    if args.plan:
        validate_config(config)
        print_plan(config)
    else:
        run_scan(config, args.half, args.full_sweep, use_headless=not args.no_headless,
                 run_shortlist_sweep=not args.no_sweep, verbose=args.verbose,
                 gap_hours=args.gap_hours)
