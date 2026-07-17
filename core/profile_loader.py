#!/usr/bin/env python3
"""profile_loader.py — resolve catalog + template + profile into the EFFECTIVE CONFIG.

The effective config has the exact shape the v3 engine consumed (platforms list with
concrete URLs, keywords, hard_filters with compiled regex first-pass, caps, scan,
notion) so the battle-tested scan machinery changed minimally in the extraction.

Resolution order (deep merge, later wins):
    template defaults  <-  profile
Lists REPLACE on merge (a profile that sets keywords owns them) except
platforms.rejected, which concatenates (template evidence + profile's own).

Validation is STRICT (v2.7.1 lesson generalized: silent skips come from tolerated
config gaps): unknown keys, a tierless active platform, a floor without currency —
all refuse the run with named errors. Schema doc: core/schema/profile.schema.yaml.

Filter compilation: the profile's TYPED filters select and parameterize entries from
core/defaults.yaml's filter_library — e.g. us_only is skipped for a US candidate, the
closed-location-list detector takes must_include from candidate.location_match_terms.
Regexes remain a FIRST PASS: scripts flag, Claude decides.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
import salary

ENGINE_VERSION = "4.0.0"

_TOP_KEYS = {"schema_version", "id", "template", "dry_run", "candidate", "search",
             "compensation", "hard_filters", "filter_notes", "scoring", "platforms",
             "sweep", "output", "schedule", "run", "writeback"}
# Phase 2 enums (§3.1). "medior" is a lexicon TITLE mapping to `mid` (D21), NOT a band.
_SENIORITY_BANDS = {"intern", "junior", "mid", "senior", "staff", "principal", "lead", "manager"}
_EMPLOYMENT_TYPES = {"full_time", "part_time", "contract", "b2b", "freelance", "internship", "any"}
_EFFORT_TIERS = {"fast", "mid", "high"}
# employment_type token -> candidate.eligibility.employment_models counterpart (§3.1).
# contract (fixed-term) and internship have no eligibility counterpart (mapped to None).
_EMPLOYMENT_TO_ELIGIBILITY = {"full_time": "full_time", "part_time": "part_time",
                              "b2b": "b2b_contractor", "freelance": "freelance",
                              "contract": None, "internship": None}
_TEMPLATE_KEYS = {"schema_version", "template_id", "label", "suggest_also", "extends",
                  "defaults", "scoring_bands", "salary_estimation_heuristics", "interview",
                  # Phase 2 v2 template-only blocks (§3.3):
                  "platform_tiers",     # per-stream tier ordering — seeds profile.platforms.tiers
                                        #   at INTERVIEW time (2.6); NEVER loader-merged (see note below)
                  "seniority_titles"}   # title->band extensions to the base seniority_lexicon (D21)
_US_NAMES = {"united states", "usa", "us", "united states of america"}


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[profile_loader] missing file: {path}")
    except yaml.YAMLError as exc:
        raise SystemExit(f"[profile_loader] invalid YAML in {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"[profile_loader] {path} did not parse to a mapping")
    return data


def load_defaults() -> dict:
    return _load_yaml(paths.DEFAULTS_PATH)


_CATALOG_STATUS = {"verified", "unverified"}


def load_catalog() -> dict:
    cat = _load_yaml(paths.CATALOG_PATH)
    errors = []
    seen_slugs: set[str] = set()
    for p in cat.get("platforms", []):
        slug = p.get("slug")
        if not slug or slug in seen_slugs:
            errors.append(f"catalog platform id={p.get('id')} has missing/duplicate slug {slug!r}")
        seen_slugs.add(slug)
        if p.get("active") and p.get("tier_default") not in (1, 2, 3):
            errors.append(f"catalog platform {slug!r} is active but has no valid tier_default")
        # Phase 2 §3.2 — `status` is the whole-entry researched-but-unverified marker for
        # NEW boards. Its one consistency rule keeps new entries OUT of tier-coverage
        # (invariant #14) until a live smoke test: unverified ⇒ active MUST be false, so a
        # new board can never fail every existing profile's tier-coverage validation. The
        # smoke test flips `status: verified` + `active: true` together; only then does the
        # platform enter tier-coverage. (`categories_verify_at_setup` is unchanged — the
        # per-SLUG marker on already-active boards; `status` is the whole-entry marker.)
        status = p.get("status")
        if status is not None and status not in _CATALOG_STATUS:
            errors.append(f"catalog platform {slug!r} has invalid status {status!r} "
                          f"(one of {sorted(_CATALOG_STATUS)})")
        if status == "unverified" and p.get("active"):
            errors.append(f"catalog platform {slug!r} is status: unverified but active: true — "
                          "unverified entries must ship active: false (§3.2); the live smoke "
                          "test flips status: verified + active: true together")
    if errors:
        raise SystemExit("[profile_loader] catalog validation FAILED:\n  " + "\n  ".join(errors))
    return cat


def load_template(template_id: str) -> dict:
    tpath = paths.TEMPLATES_DIR / f"{template_id}.yaml"
    tpl = _load_yaml(tpath)
    unknown = set(tpl) - _TEMPLATE_KEYS
    if unknown:
        raise SystemExit(f"[profile_loader] template {template_id}: unknown keys {sorted(unknown)}")
    if tpl.get("extends"):
        base = load_template(tpl["extends"])
        tpl["defaults"] = _merge(base.get("defaults", {}), tpl.get("defaults", {}))
        for k in ("scoring_bands", "salary_estimation_heuristics", "interview", "platform_tiers"):
            tpl.setdefault(k, base.get(k))
        # seniority_titles deep-merge along the chain (child titles win on overlap)
        tpl["seniority_titles"] = _merge(base.get("seniority_titles") or {},
                                         tpl.get("seniority_titles") or {})
    return tpl


def load_seniority_lexicon() -> dict:
    """Base title->band lexicon (D21), lowercased keys. Templates extend it via
    `seniority_titles`; load() deep-merges the two into cfg['seniority_lexicon']."""
    data = _load_yaml(paths.SENIORITY_LEXICON_PATH)
    return {str(k).lower(): v for k, v in (data.get("titles") or {}).items()}


def _merge(base, override):
    """Deep merge: dicts recurse; everything else (incl. lists) is replaced by override."""
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for k, v in override.items():
            out[k] = _merge(base.get(k), v) if k in base else v
        return out
    return override if override is not None else base


# ---------------------------------------------------------------- validation

def _validate(merged: dict, profile_id: str, catalog: dict, defaults: dict) -> list[str]:
    e: list[str] = []

    def req(path_: str, cond: bool):
        if not cond:
            e.append(f"missing/invalid: {path_}")

    unknown = set(merged) - _TOP_KEYS
    if unknown:
        e.append(f"unknown top-level keys: {sorted(unknown)}")
    req("schema_version == 1", merged.get("schema_version") == 1)
    req("id matches directory", merged.get("id") == profile_id)

    cand = merged.get("candidate") or {}
    req("candidate.display_name", bool(cand.get("display_name")))
    loc = cand.get("location") or {}
    for f in ("city", "country", "timezone"):
        req(f"candidate.location.{f}", bool(loc.get(f)))
    req("candidate.location_match_terms (non-empty list)",
        isinstance(cand.get("location_match_terms"), list) and cand["location_match_terms"])
    req("candidate.citizenship (non-empty list)",
        isinstance(cand.get("citizenship"), list) and cand["citizenship"])
    elig = cand.get("eligibility") or {}
    models = elig.get("employment_models") or []
    req("candidate.eligibility.employment_models subset",
        bool(models) and set(models) <= {"b2b_contractor", "full_time", "part_time", "freelance"})
    req("candidate.eligibility.needs_visa_sponsorship (bool)",
        isinstance(elig.get("needs_visa_sponsorship"), bool))

    search = merged.get("search") or {}
    stream = search.get("stream")
    req("search.stream", bool(stream))
    req("search.work_model subset of remote/hybrid/on_site",
        isinstance(search.get("work_model"), list)
        and set(search["work_model"]) <= {"remote", "hybrid", "on_site"} and search["work_model"])
    kw = search.get("keywords") or {}
    req("search.keywords.core (non-empty list)", isinstance(kw.get("core"), list) and kw.get("core"))
    req("search.keywords.expanded (list)", isinstance(kw.get("expanded"), list))
    req("search.archetypes (non-empty list)",
        isinstance(search.get("archetypes"), list) and search.get("archetypes"))

    # NEW (Phase 2 §3.1): subvariant(+secondary) — optional strings; the template path
    # remains the fallback subvariant carrier when unset.
    for key in ("subvariant", "subvariant_secondary"):
        v = search.get(key)
        if v is not None and not isinstance(v, str):
            e.append(f"search.{key} must be a string (or omitted)")
    # NEW (D7): target_seniority — optional; soft scoring input unless strict.
    ts = search.get("target_seniority")
    if ts is not None:
        if not isinstance(ts, dict):
            e.append("search.target_seniority must be a mapping {bands, strict}")
        else:
            bands = ts.get("bands")
            req("search.target_seniority.bands (non-empty list)", isinstance(bands, list) and bool(bands))
            if isinstance(bands, list):
                bad = [b for b in bands if b not in _SENIORITY_BANDS]
                if bad:
                    e.append(f"search.target_seniority.bands unknown {sorted(set(bad))} "
                             f"(allowed {sorted(_SENIORITY_BANDS)}; 'medior' is a lexicon title -> mid)")
            if "strict" in ts and not isinstance(ts["strict"], bool):
                e.append("search.target_seniority.strict must be a bool")
            unknown_ts = set(ts) - {"bands", "strict"}
            if unknown_ts:
                e.append(f"search.target_seniority unknown keys: {sorted(unknown_ts)}")
    # NEW (D8): employment_type — optional hard filter; 'any' disables it and is exclusive.
    et = search.get("employment_type")
    if et is not None:
        if not isinstance(et, dict):
            e.append("search.employment_type must be a mapping {accept}")
        else:
            accept = et.get("accept")
            req("search.employment_type.accept (non-empty list)", isinstance(accept, list) and bool(accept))
            if isinstance(accept, list):
                bad = [x for x in accept if x not in _EMPLOYMENT_TYPES]
                if bad:
                    e.append(f"search.employment_type.accept unknown {sorted(set(bad))} "
                             f"(allowed {sorted(_EMPLOYMENT_TYPES)})")
                if "any" in accept and len(set(accept)) > 1:
                    e.append("search.employment_type.accept: 'any' is mutually exclusive "
                             f"with other values, got {accept}")
            unknown_et = set(et) - {"accept"}
            if unknown_et:
                e.append(f"search.employment_type unknown keys: {sorted(unknown_et)}")

    comp = merged.get("compensation") or {}
    fx = (defaults.get("salary") or {}).get("fx_to_eur", {})
    # CHANGED (D20): compensation.floor is now OPTIONAL. When present, its four sub-keys
    # are required exactly as before; when unset, the below-floor first-pass is disabled
    # and salary judgment falls to the template heuristics (see salary.normalize_floor).
    fl = comp.get("floor")
    ratio = comp.get("gross_net_ratio")
    if fl is not None:
        req("compensation.floor.amount > 0", isinstance(fl.get("amount"), (int, float)) and fl.get("amount", 0) > 0)
        req(f"compensation.floor.currency in fx table {sorted(fx)}", fl.get("currency") in fx)
        req("compensation.floor.basis gross|net", fl.get("basis") in ("gross", "net"))
        req("compensation.floor.period hour|day|month|year", fl.get("period") in ("hour", "day", "month", "year"))
        req("compensation.gross_net_ratio in 0.3..1.0 (required with a floor)",
            isinstance(ratio, (int, float)) and 0.3 <= ratio <= 1.0)
    elif ratio is not None:
        # floorless: gross_net_ratio optional but still validated when present
        req("compensation.gross_net_ratio in 0.3..1.0", isinstance(ratio, (int, float)) and 0.3 <= ratio <= 1.0)
    # NEW (D22): fte_fraction pro-rates a set floor for part-time targets.
    fte = comp.get("fte_fraction")
    if fte is not None:
        req("compensation.fte_fraction in (0, 1]", isinstance(fte, (int, float)) and 0 < fte <= 1)

    # NEW (D9/D10): run.effort(+by_run_type) — recorded + documented, not wired yet.
    run = merged.get("run")
    if run is not None:
        if not isinstance(run, dict):
            e.append("run must be a mapping")
        else:
            eff = run.get("effort")
            if eff is not None and eff not in _EFFORT_TIERS:
                e.append(f"run.effort must be one of {sorted(_EFFORT_TIERS)}, got {eff!r}")
            ebt = run.get("effort_by_run_type")
            if ebt is not None:
                if not isinstance(ebt, dict):
                    e.append("run.effort_by_run_type must be a mapping of run_type -> effort")
                else:
                    for rt, v in ebt.items():
                        if v not in _EFFORT_TIERS:
                            e.append(f"run.effort_by_run_type.{rt} must be one of "
                                     f"{sorted(_EFFORT_TIERS)}, got {v!r}")
            unknown_run = set(run) - {"effort", "effort_by_run_type"}
            if unknown_run:
                e.append(f"run unknown keys: {sorted(unknown_run)}")

    # NEW (D6): writeback consent — opt-in gate for the staged suggestion loop (§6).
    wb = merged.get("writeback")
    if wb is not None:
        if not isinstance(wb, dict):
            e.append("writeback must be a mapping {consent}")
        else:
            if "consent" in wb and not isinstance(wb["consent"], bool):
                e.append("writeback.consent must be a bool")
            unknown_wb = set(wb) - {"consent"}
            if unknown_wb:
                e.append(f"writeback unknown keys: {sorted(unknown_wb)}")

    hf = merged.get("hard_filters") or {}
    for key, allowed in (("travel", {"none", "occasional_ok", "any"}),
                         ("clearance", {"drop", "allow"}),
                         ("grind_culture", {"drop", "allow"}),
                         ("closed_location_list", {"drop_if_absent", "off"})):
        if key in hf and hf[key] not in allowed:
            e.append(f"hard_filters.{key} must be one of {sorted(allowed)}, got {hf[key]!r}")
    tw = (hf.get("timezone_window") or {}).get("latest_end_local")
    if tw is not None and not re.fullmatch(r"\d{2}:\d{2}", str(tw)):
        e.append(f'hard_filters.timezone_window.latest_end_local must be "HH:MM", got {tw!r}')

    sc = merged.get("scoring") or {}
    req("scoring.surface_threshold 1.0..10.0",
        isinstance(sc.get("surface_threshold"), (int, float)) and 1.0 <= sc["surface_threshold"] <= 10.0)

    # platforms: tier coverage against the catalog
    plats = merged.get("platforms") or {}
    tiers = plats.get("tiers") or {}
    disabled = set(plats.get("disabled") or [])
    tiered: dict[str, int] = {}
    for t, slugs in tiers.items():
        if t not in (1, 2, 3) or not isinstance(slugs, list):
            e.append(f"platforms.tiers keys must be 1/2/3 with slug lists (got {t!r})")
            continue
        for s in slugs:
            if s in tiered:
                e.append(f"platform {s!r} appears in tier {tiered[s]} AND {t}")
            tiered[s] = t
    cat_slugs = {p["slug"]: p for p in catalog.get("platforms", [])}
    for s in list(tiered) + list(disabled):
        if s not in cat_slugs:
            e.append(f"platforms references unknown catalog slug {s!r}")
    for slug, p in cat_slugs.items():
        if p.get("active") and slug not in disabled and slug not in tiered:
            e.append(f"active platform {slug!r} has no tier and is not disabled "
                     "(tierless = silent skip; invariant #14)")

    # output: dry_run or full notion targets
    out = merged.get("output") or {}
    notion = out.get("notion") or {}
    if not merged.get("dry_run") and not notion.get("dry_run"):
        for block in ("tracker", "passed_seen"):
            ds = (notion.get(block) or {}).get("data_source_id", "")
            if len(str(ds).replace("-", "")) != 32:
                e.append(f"output.notion.{block}.data_source_id missing/malformed")
        if not (notion.get("pinned_pages") or {}).get("job_scout_runs"):
            e.append("output.notion.pinned_pages.job_scout_runs missing")
    return e


def _warnings(merged: dict) -> list[str]:
    """Non-fatal advisories surfaced at load (§3.1). Doctrine: scripts flag, Claude/user
    decides — a plain contradiction between what postings to surface (search.employment_type)
    and how the candidate can legally engage (candidate.eligibility.employment_models) is
    worth naming without refusing the run."""
    w: list[str] = []
    et = (merged.get("search") or {}).get("employment_type") or {}
    accept = et.get("accept") if isinstance(et, dict) else None
    if isinstance(accept, list) and "any" not in accept:
        models = set(((merged.get("candidate") or {}).get("eligibility") or {}).get("employment_models") or [])
        for tok in accept:
            counterpart = _EMPLOYMENT_TO_ELIGIBILITY.get(tok)
            if counterpart is not None and counterpart not in models:
                w.append(f"search.employment_type.accept has {tok!r} but "
                         f"candidate.eligibility.employment_models lacks {counterpart!r} "
                         f"— surfacing a posting type the candidate isn't marked eligible for")
    return w


# ------------------------------------------------------------- filter compile

def _slugify(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")


def _compile_hard_filters(merged: dict, defaults: dict) -> dict:
    lib = defaults.get("filter_library", {})
    hf = merged.get("hard_filters") or {}
    cand = merged["candidate"]
    country = (cand["location"]["country"] or "").lower()

    auto: dict[str, str] = {}
    if country not in _US_NAMES:
        auto["us_only"] = lib["auto_drop_patterns"]["us_only"]
    if hf.get("clearance", "drop") == "drop":
        auto["clearance"] = lib["auto_drop_patterns"]["clearance"]
    if hf.get("travel", "none") == "none":
        auto["travel"] = lib["auto_drop_patterns"]["travel"]
    if hf.get("grind_culture", "drop") == "drop":
        auto["grind_culture"] = lib["auto_drop_patterns"]["grind_culture"]

    flags: dict[str, str] = {}
    if (hf.get("timezone_window") or {}).get("latest_end_local"):
        flags["timezone"] = lib["flag_patterns"]["timezone"]
    eu = set(defaults.get("eu_citizenships", []))
    if not (set(cand.get("citizenship", [])) & eu):
        flags["eu_citizenship"] = lib["flag_patterns"]["eu_citizenship"]
    tools = hf.get("tool_lockin_drop") or []
    if tools:
        multi = [t.lower() for t in tools if " " in t]
        generic = sorted({t.lower().split()[0] for t in tools})
        alt = "|".join(re.escape(t) for t in multi) or "(?!x)x"  # never-match placeholder
        flags["tool_lockin"] = lib["tool_lockin_template"].format(
            tools_alt=alt, tools_generic="|".join(re.escape(t) for t in generic))
    latam = {c.lower() for c in defaults.get("latam_countries", [])}
    if country not in latam:
        flags["latam_payroll"] = lib["flag_patterns"]["latam_payroll"]
    for term in hf.get("role_exclusion_terms") or []:
        flags[f"excl_{_slugify(term)}"] = lib["role_exclusion_template"].format(terms=re.escape(term.lower()))

    compiled = {"auto_drop_patterns": auto, "flag_patterns": flags,
                "salary_floor": salary.normalize_floor(merged.get("compensation") or {}, defaults)}
    if hf.get("closed_location_list", "drop_if_absent") == "drop_if_absent":
        cll = lib.get("closed_location_list", {})
        compiled["eu_country_list_detector"] = {  # legacy key name — engine compat
            "countries": list(cll.get("countries", [])),
            "open_ended_markers": list(cll.get("open_ended_markers", [])),
            "must_include": list(cand["location_match_terms"]),
        }
    for name, pat in list(auto.items()) + list(flags.items()):
        try:
            re.compile(pat)
        except re.error as exc:
            raise SystemExit(f"[profile_loader] compiled filter {name!r} is not a valid regex: {exc}")
    return compiled


# ---------------------------------------------------------- platform resolve

def _expand(patterns: list[str], mapping, params: dict) -> list[str]:
    """Expand {category}/{category_id} patterns; mapping may be a slug or list of slugs."""
    slugs = mapping if isinstance(mapping, list) else ([mapping] if mapping else [])
    out = []
    for pat in patterns or []:
        if "{category}" in pat:
            out += [pat.replace("{category}", s) for s in slugs]
        elif "{category_id}" in pat:
            cid = params.get("category_id")
            if cid:
                out.append(pat.replace("{category_id}", str(cid)))
        else:
            out.append(pat)
    return out


def _resolve_platforms(merged: dict, catalog: dict) -> tuple[list[dict], dict[str, str]]:
    stream = merged["search"]["stream"]
    plats = merged.get("platforms") or {}
    disabled = set(plats.get("disabled") or [])
    overrides = (merged.get("search") or {}).get("platform_slugs") or {}
    ats_boards = plats.get("ats_boards") or {}
    tier_of: dict[str, int] = {}
    for t, slugs in (plats.get("tiers") or {}).items():
        for s in slugs:
            tier_of[s] = int(t)

    resolved, skipped = [], {}
    for cp in catalog.get("platforms", []):
        slug = cp["slug"]
        active = bool(cp.get("active")) and slug not in disabled
        params: dict = {}
        pre = (cp.get("prefilter_phrases") or {}).get(stream)
        if pre:
            params["prefilter_phrases"] = list(pre)

        mapping = overrides.get(slug, (cp.get("categories") or {}).get(stream))
        # category_id resolves by the RESOLVED category slug first (so a subvariant override
        # like backend-java -> justjoin 'java' picks the Java id), then falls back to the
        # stream key (backward-compatible with any stream-keyed category_ids).
        cids = cp.get("category_ids") or {}
        if isinstance(mapping, str) and mapping in cids:
            params["category_id"] = cids[mapping]
        elif stream in cids:
            params["category_id"] = cids[stream]
        urls = _expand(cp.get("url_patterns"), mapping if mapping != "all" else None, params) \
            if mapping != "all" else list(cp.get("url_patterns") or [])
        rss = _expand(cp.get("rss_patterns"), mapping, params) if mapping != "all" \
            else list(cp.get("rss_patterns") or [])
        api = _expand(cp.get("api_patterns"), mapping if mapping != "all" else None, params) \
            if mapping != "all" else list(cp.get("api_patterns") or [])

        needs_category = any("{category}" in p for p in (cp.get("url_patterns") or [])) or \
                         any("{category" in p for p in (cp.get("api_patterns") or []))
        if active and needs_category and mapping is None and not cp.get("api_board_pattern"):
            skipped[cp["name"]] = f"no category mapping for stream {stream!r}"
            active = False

        entry = {
            "id": cp.get("id"), "slug": slug, "name": cp["name"],
            "tier": tier_of.get(slug, cp.get("tier_default")),
            "active": active,
            "fetch_mode": cp.get("fetch_mode"),
            "urls": urls, "mirrors": list(cp.get("mirrors") or []),
            "expired_markers": list(cp.get("expired_markers") or []),
            "quirks": cp.get("quirks", ""),
            "notion_platform_name": dict(cp.get("notion_platform_name") or {}),
            "params": params,
        }
        if rss:
            entry["rss"] = rss
        if api:
            entry["api"] = api
        if cp.get("api_board_pattern"):
            entry["api_pattern"] = cp["api_board_pattern"]
            entry["boards"] = list(ats_boards.get(slug) or [])
        if cp.get("per_job_fetch_mode"):
            entry["per_job_fetch_mode"] = cp["per_job_fetch_mode"]
        if cp.get("recheck_after"):
            entry["recheck_after"] = cp["recheck_after"]
        resolved.append(entry)
    return resolved, skipped


# ------------------------------------------------------------------ assembly

def load(profile_id: str | None = None) -> dict:
    """Load + validate + resolve. Returns the effective config. Refuses invalid profiles."""
    pid = paths.set_profile(profile_id) if profile_id else paths.get_profile()
    defaults = load_defaults()
    catalog = load_catalog()
    prof = _load_yaml(paths.profile_yaml(pid))

    tpl: dict = {}
    if prof.get("template"):
        tpl = load_template(prof["template"])
    merged = _merge(tpl.get("defaults", {}), {k: v for k, v in prof.items() if k != "template"})
    merged["template"] = prof.get("template")
    # rejected platforms concatenate (template evidence + profile's own)
    tpl_rej = ((tpl.get("defaults") or {}).get("platforms") or {}).get("rejected") or []
    prof_rej = ((prof.get("platforms") or {}).get("rejected") or [])
    merged.setdefault("platforms", {})["rejected"] = tpl_rej + prof_rej

    errors = _validate(merged, pid, catalog, defaults)
    if errors:
        raise SystemExit(f"[profile_loader] profile {pid!r} validation FAILED:\n  " + "\n  ".join(errors))
    for warn in _warnings(merged):
        print(f"[profile_loader] warning ({pid}): {warn}", file=sys.stderr)

    platforms, skipped = _resolve_platforms(merged, catalog)

    sched = merged.get("schedule") or {}
    scan_cfg = dict(defaults.get("scan", {}))
    if sched.get("freshness_window_h"):
        scan_cfg["freshness_window_h"] = int(sched["freshness_window_h"])
    if sched.get("full_sweep_dow"):
        scan_cfg["full_sweep_dow"] = sched["full_sweep_dow"]
    sweep_cfg = dict(defaults.get("sweep", {}))
    sweep_cfg.update(merged.get("sweep") or {})

    lt_merged = ((merged.get("platforms") or {}).get("linkedin_tripwire") or {})
    lt_defaults = defaults.get("linkedin_tripwire", {})
    linkedin = {
        "enabled": lt_merged.get("enabled", True),
        "keywords": lt_merged.get("keywords") or merged["search"]["keywords"]["core"][:3],
        "locations": lt_merged.get("locations") or ["Worldwide"],
        "remote_filter": lt_defaults.get("remote_filter", "f_WT=2"),
        "freshness": lt_defaults.get("freshness", "f_TPR=r86400"),
    }

    tiers_by_name: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for p in platforms:
        if p["active"] and p.get("tier") in (1, 2, 3):
            tiers_by_name[p["tier"]].append(p["name"])

    notion = dict((merged.get("output") or {}).get("notion") or {})
    if merged.get("dry_run"):
        notion["dry_run"] = True

    # Resolved seniority lexicon (D21): base + this template's seniority_titles extensions.
    # Consumed by the judgment layer + scan.py's seniority_detected annotation.
    seniority_lexicon = load_seniority_lexicon()
    seniority_lexicon.update({str(k).lower(): v for k, v in (tpl.get("seniority_titles") or {}).items()})

    return {
        "version": ENGINE_VERSION,
        "profile_id": pid,
        "profile": merged,
        "platforms": platforms,
        "skipped_platforms": skipped,
        "linkedin_tripwire": linkedin,
        "tiers": tiers_by_name,
        "rejected_platforms": merged["platforms"]["rejected"],
        "keywords": merged["search"]["keywords"],
        "hard_filters": _compile_hard_filters(merged, defaults),
        "caps": dict(defaults.get("caps", {})),
        "scan": scan_cfg,
        "sweep": sweep_cfg,
        "notion": notion,
        "recompute": dict(defaults.get("recompute", {"due_at_sessions": 5})),
        "scoring": {
            "surface_threshold": (merged.get("scoring") or {}).get("surface_threshold", 7.0),
            "bands": tpl.get("scoring_bands", ""),
            "salary_estimation_heuristics": tpl.get("salary_estimation_heuristics", ""),
        },
        "filter_notes": merged.get("filter_notes", ""),
        "seniority_lexicon": seniority_lexicon,
        "defaults": defaults,
    }


if __name__ == "__main__":
    import json

    pid = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load(pid)
    active = [p for p in cfg["platforms"] if p["active"]]
    print(f"profile {cfg['profile_id']!r} OK: {len(active)} active platforms, "
          f"{len(cfg['keywords']['core'])}+{len(cfg['keywords']['expanded'])} keywords, "
          f"{len(cfg['hard_filters']['auto_drop_patterns'])} auto-drop / "
          f"{len(cfg['hard_filters']['flag_patterns'])} flag patterns")
    for name, why in cfg["skipped_platforms"].items():
        print(f"  skipped: {name} — {why}")
    if "--dump" in sys.argv:
        print(json.dumps(cfg, ensure_ascii=False, indent=1, default=str))
