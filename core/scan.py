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

What gets auto-logged to seen.jsonl by a scan (everything else is Claude's call):
  dropped/Filtered Out    auto_drop_patterns or the closed-location-list detector matched
  dropped/Stale-Expired   liveness check said stale (mechanical) — incl. the sweep's
                          post-shortlist retirements (ARCHITECTURE.md §6)
  unverified_blocked      no JD obtainable AND liveness unverifiable — confirmed dead end
                          (SysMap rule; suppressed on future scans, reason updated if later resolved)
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


def hard_filter(cand: dict, hf: dict) -> tuple[str | None, list[str]]:
    """Returns (drop_reason, flags). Drop only on the machine-certain patterns."""
    hay = " ".join(str(cand.get(k) or "") for k in ("title", "loc", "salary", "jd_text"))
    flags = []
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


def print_plan(cfg: dict) -> None:
    """--plan: the resolved scan plan, zero network. The dry-run acceptance surface."""
    prof = cfg["profile"]
    print(f"## Scan plan — profile {cfg['profile_id']!r} "
          f"(template {prof.get('template') or 'none'}, stream {prof['search']['stream']})")
    print(f"keywords core: {', '.join(cfg['keywords']['core'])}")
    print(f"keywords expanded: {', '.join(cfg['keywords']['expanded'])}")
    hf = cfg["hard_filters"]
    print(f"auto-drop filters: {', '.join(hf['auto_drop_patterns'])}")
    print(f"flag filters: {', '.join(hf['flag_patterns'])}")
    det = hf.get("eu_country_list_detector")
    if det:
        print(f"closed-location-list detector: must_include {det['must_include']}")
    sf = hf["salary_floor"]
    print(f"salary floor: {sf['floor']['amount']} {sf['floor']['currency']} "
          f"{sf['floor']['basis']}/{sf['floor']['period']} "
          f"(canonical ≈{sf['canonical_gross_month']} {sf['currency']} gross/month)")
    active = [p for p in cfg["platforms"] if p.get("active")]
    active.sort(key=lambda p: (p.get("tier", 9), p.get("id", 99)))
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
             run_shortlist_sweep: bool = True) -> dict:
    validate_config(cfg)
    seen = dedup.load_seen()
    keywords = [k.lower() for k in (cfg["keywords"]["core"] + cfg["keywords"]["expanded"])]
    caps = cfg.get("caps", {})
    window_h = int(cfg.get("scan", {}).get("freshness_window_h", 48))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_h)
    today = date.today().isoformat()
    label = "AM" if datetime.now().hour < 12 else "PM"

    platforms = [p for p in cfg["platforms"] if p.get("active")]
    platforms.sort(key=lambda p: (p.get("tier", 9), p.get("id", 99)))
    if half:  # degraded/manual mode only — the r2 default is the full rotation
        mid = (len(platforms) + 1) // 2
        platforms = platforms[:mid] if half == "AM" else platforms[mid:]

    results = [fetch_boards.fetch_platform(p, cfg) for p in platforms]
    if cfg["linkedin_tripwire"].get("enabled", True):
        results.append(linkedin_tripwire.fetch_tripwire(cfg))

    sources_down = [r["platform"] for r in results if r["source_down"]]
    notes = {r["platform"]: r["note"] for r in results if r["note"]}

    # ---- triage: keyword filter → freshness → dedup → hard filters
    new_cands, dropped, link_dead = [], 0, 0
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
            reason, flags = hard_filter(c, cfg.get("hard_filters", {}))
            c["flags"] = sorted(set((c.get("flags") or []) + flags))
            if reason:
                dedup.append({"company": c["company"], "role": c["title"], "locdom": c.get("loc", ""),
                              "url": c["url"], "platform": c["platform"], "status": "dropped",
                              "reason": "Filtered Out", "fit": "N/A", "archetype": "",
                              "keyword_source": c["title"], "notes": reason})
                dropped += 1
                continue
            new_cands.append(c)

    # ---- full JD reads for survivors lacking one (local parses; cap is politeness)
    max_reads = int(caps.get("max_full_reads_per_run", 15))
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
            dedup.append({"company": c["company"], "role": c["title"], "locdom": c.get("loc", ""),
                          "url": c["url"], "platform": c["platform"], "status": "dropped",
                          "reason": "Stale/Expired", "fit": "N/A", "archetype": "",
                          "keyword_source": c["title"],
                          "notes": f"link check: {v.get('note', '')} (source URL {c.get('source_url') or 'n/a'})"})
            link_dead += 1
            continue
        if v["verdict"] == "unverifiable_direct" and not c.get("jd_text"):
            # nothing to evaluate and no way to verify: confirmed dead end (2.6.0 / SysMap)
            dedup.append({"company": c["company"], "role": c["title"], "locdom": c.get("loc", ""),
                          "url": c["url"], "platform": c["platform"], "status": "unverified_blocked",
                          "reason": "Unverified/Blocked", "fit": "N/A", "archetype": "",
                          "keyword_source": c["title"], "notes": f"blocked: {v.get('note', '')}"})
            dropped += 1
            continue
        c["link_status"] = {"live": "✅ live", "unverifiable_direct": "❓ unverified"}[v["verdict"]]
        survivors.append(c)

    # ---- salary assessment (4.0, ADDITIVE metadata for the judgment layer — never a
    # machine drop; unstated salary applies the template's estimation heuristics)
    floor_norm = cfg["hard_filters"]["salary_floor"]
    defaults = cfg.get("defaults", {})
    for c in survivors:
        text = " ".join(str(c.get(k) or "") for k in ("salary", "jd_text"))
        c["salary_assessment"] = salary.assess(text, floor_norm, defaults)

    # ---- shortlist liveness sweep (4.0, step 8 — ARCHITECTURE.md §6)
    sweep_counts = {"scope": 0, "checked": 0, "stale": 0, "unverifiable": 0,
                    "escalated": 0, "live": 0, "deferred": 0}
    if run_shortlist_sweep:
        sweep_counts = sweep.run_sweep(cfg, use_headless=use_headless)

    # ---- cache JDs, emit candidates JSON
    jd_cache = paths.jd_cache_dir()
    jd_cache.mkdir(parents=True, exist_ok=True)
    for c in survivors:
        if c.get("jd_text"):
            h = hashlib.sha256(c["url"].encode()).hexdigest()[:16]
            (jd_cache / f"{h}.txt").write_text(c["jd_text"], encoding="utf-8")
            c["jd_cache"] = f"state/jd_cache/{h}.txt"
            c["jd_text"] = c["jd_text"][:1500]  # candidates JSON stays skimmable; full text in cache

    out_path = paths.candidates_path()
    out_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "profile": cfg["profile_id"],
        "run": f"{today} {label}", "half": half, "full_sweep": full_sweep,
        "candidates": survivors,
        "sources_down": sources_down, "platform_notes": notes,
        "skipped_platforms": cfg.get("skipped_platforms", {}),
        "shortlist_sweep": sweep_counts,
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
        "new": len(survivors), "dropped": dropped, "link_dead": link_dead,
        "sweep": sweep_counts,
        "half": half, "full_sweep": full_sweep,
    }
    runs["recompute"]["sessions_since"] = runs["recompute"].get("sessions_since", 0) + 1
    runs_path.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- ledger print (replaces the 20-item chat checklist; partial-labeled-partial)
    print(f"## Job Scout scan — {cfg['profile_id']} — {today} {label}"
          + (f" (half={half})" if half else " (full rotation)")
          + (" [full sweep]" if full_sweep else f" [fresh window {window_h}h]"))
    print(f"{len(survivors)} new candidates / {dropped} auto-dropped / {link_dead} link-dead")
    covered = [r["platform"] for r in results if not r["source_down"]]
    print(f"covered ({len(covered)}): {', '.join(covered)}")
    print(f"sources down: {', '.join(sources_down) if sources_down else 'none'}")
    for name, why in (cfg.get("skipped_platforms") or {}).items():
        print(f"  ⏭ skipped[{name}]: {why}")
    for plat, note in notes.items():
        if any(k in note for k in ("DEGRADED", "REGRESSED", "no boards")):
            print(f"  note[{plat}]: {note[:110]}")
    print(f"shortlist sweep: {sweep_counts['scope']} unreviewed in scope, "
          f"{sweep_counts['checked']} rechecked, {sweep_counts['stale']} went stale, "
          f"{sweep_counts['unverifiable']} unverifiable"
          + (f" ({sweep_counts['escalated']} escalated — check manually)" if sweep_counts["escalated"] else ""))
    rc = runs["recompute"]
    if rc["sessions_since"] >= rc.get("due_at_sessions", 5):
        print(f"⚠ tier recompute due: {rc['sessions_since']} sessions since {rc['last']} "
              "(data session with the user — not automated)")
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
    ap.add_argument("--no-headless", action="store_true", help="skip headless escalation")
    ap.add_argument("--no-sweep", action="store_true",
                    help="skip the shortlist liveness sweep (parity/debug only)")
    args = ap.parse_args()
    config = profile_loader.load(args.profile or paths.get_profile())
    if args.plan:
        validate_config(config)
        print_plan(config)
    else:
        run_scan(config, args.half, args.full_sweep, use_headless=not args.no_headless,
                 run_shortlist_sweep=not args.no_sweep)
