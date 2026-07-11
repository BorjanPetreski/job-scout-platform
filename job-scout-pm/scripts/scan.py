#!/usr/bin/env python3
"""scan.py — orchestrator. Runs the rotation, emits candidates JSON. DOES NOT SCORE.

Scoring, archetype tagging, judgment-layer filter reads, and the shortlist table are
Claude's job in the session, reading state/last_run_candidates.json + the JD cache.
Regexes here are a FIRST PASS (Spiralyze lesson: scripts flag, Claude decides) —
only unambiguous mechanical drops are auto-logged.

Usage:
  scan.py                 full active rotation (r2 default)
  scan.py --half AM|PM    retained for degraded/manual use only
  scan.py --full-sweep    ignore the freshness window (scheduler runs this on Mondays)
  scan.py --no-headless   skip headless escalations (fast smoke run)

What gets auto-logged to seen.jsonl by a scan (everything else is Claude's call):
  dropped/Filtered Out    auto_drop_patterns or the EU-country-list detector matched
  dropped/Stale-Expired   liveness check said stale (mechanical)
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

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_links
import dedup
import fetch_boards
import linkedin_tripwire

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
JD_CACHE = STATE / "jd_cache"
RUNS_PATH = STATE / "runs.json"
OUT_PATH = STATE / "last_run_candidates.json"


def validate_config(cfg: dict) -> None:
    """Invariant #14 (Pinpoint lesson): every active platform must have a tier, and every
    platform must be reachable by a run selector — a config error, not a silent skip."""
    errors = []
    for p in cfg["platforms"]:
        if p.get("active") and p.get("tier") not in (1, 2, 3):
            errors.append(f"platform {p.get('name')!r} is active but has no valid tier")
        if p.get("active") and not (p.get("urls") or p.get("api") or p.get("api_pattern")
                                    or p["name"] in fetch_boards.HANDLERS):
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
    # EU-country-list enumeration detector (filter #13, 2.10.0)
    det = hf.get("eu_country_list_detector") or {}
    countries = det.get("countries", [])
    found = [c for c in countries if re.search(rf"\b{re.escape(c)}\b", hay)]
    if len(found) >= 4:
        open_ended = any(m.lower() in hay.lower() for m in det.get("open_ended_markers", []))
        named = any(m.lower() in hay.lower() for m in det.get("must_include", []))
        if not open_ended and not named:
            return "auto-drop: eu_country_list (closed list, N. Macedonia absent)", flags
    return None, flags


def run_scan(half: str | None, full_sweep: bool, use_headless: bool = True) -> dict:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
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

    # ---- cache JDs, emit candidates JSON
    JD_CACHE.mkdir(parents=True, exist_ok=True)
    for c in survivors:
        if c.get("jd_text"):
            h = hashlib.sha256(c["url"].encode()).hexdigest()[:16]
            (JD_CACHE / f"{h}.txt").write_text(c["jd_text"], encoding="utf-8")
            c["jd_cache"] = f"state/jd_cache/{h}.txt"
            c["jd_text"] = c["jd_text"][:1500]  # candidates JSON stays skimmable; full text in cache

    OUT_PATH.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run": f"{today} {label}", "half": half, "full_sweep": full_sweep,
        "candidates": survivors,
        "sources_down": sources_down, "platform_notes": notes,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- runs.json ledger + recompute counter
    runs = json.loads(RUNS_PATH.read_text()) if RUNS_PATH.exists() else {"recompute": {
        "last": "2026-07-10", "sessions_since": 0, "due_at_sessions": 5}}
    day = runs.setdefault(today, {})
    day[label] = {
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platforms_covered": [r["platform"] for r in results if not r["source_down"]],
        "sources_down": sources_down,
        "new": len(survivors), "dropped": dropped, "link_dead": link_dead,
        "half": half, "full_sweep": full_sweep,
    }
    runs["recompute"]["sessions_since"] = runs["recompute"].get("sessions_since", 0) + 1
    RUNS_PATH.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- ledger print (replaces the 20-item chat checklist; partial-labeled-partial)
    print(f"## Job Scout scan — {today} {label}" + (f" (half={half})" if half else " (full rotation)")
          + (" [full sweep]" if full_sweep else f" [fresh window {window_h}h]"))
    print(f"{len(survivors)} new candidates / {dropped} auto-dropped / {link_dead} link-dead")
    covered = [r["platform"] for r in results if not r["source_down"]]
    print(f"covered ({len(covered)}): {', '.join(covered)}")
    print(f"sources down: {', '.join(sources_down) if sources_down else 'none'}")
    for plat, note in notes.items():
        if any(k in note for k in ("DEGRADED", "REGRESSED", "no boards")):
            print(f"  note[{plat}]: {note[:110]}")
    rc = runs["recompute"]
    if rc["sessions_since"] >= rc.get("due_at_sessions", 5):
        print(f"⚠ tier recompute due: {rc['sessions_since']} sessions since {rc['last']} "
              "(data session with Borjan — not automated)")
    print(f"candidates JSON: {OUT_PATH.relative_to(ROOT)}")
    return {"new": len(survivors), "dropped": dropped, "link_dead": link_dead,
            "sources_down": sources_down}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--half", choices=["AM", "PM"], default=None,
                    help="degraded/manual half rotation (r2 default is full)")
    ap.add_argument("--full-sweep", action="store_true", help="ignore freshness window")
    ap.add_argument("--no-headless", action="store_true", help="skip headless escalation")
    args = ap.parse_args()
    run_scan(args.half, args.full_sweep, use_headless=not args.no_headless)
