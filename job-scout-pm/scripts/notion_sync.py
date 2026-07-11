#!/usr/bin/env python3
"""notion_sync.py — one-way push: local state → Notion. Direct REST, typed writes.

Data flow (2.7.0 invariant #5, enforced structurally):
  * Scan-driven writes go to the PASSED/SEEN LOG ONLY.
      shortlisted        → Reason Passed = "New — Unreviewed" (+ role notes in page body)
      dropped            → the real reason (Stale/Expired, Filtered Out, Duplicate Listing, …)
      unverified_blocked → "Unverified/Blocked"
  * The Applications Tracker is NEVER a scan-write target. Tracker rows are created only
    by the interactive "I applied" flow (`notion_sync.py --applied <url>`), after Claude
    marks the seen.jsonl row `applied` on Borjan's explicit confirmation.
    sync_scan() cannot reach the Tracker: the write wrapper takes its data-source id from
    the flow, and the scan flow only ever passes the Passed/Seen id (delta rows 12/13 —
    the 2026-07-10 violation is uncompilable now, not a rule to remember).

Auth: NOTION_TOKEN env var (integration token with access to both DBs + pinned pages).
No token → nothing is written; pending rows are exported to state/notion_pending.json
with full property payloads so a Claude session can push them via the Notion MCP
verbatim. (One-time reverse backfill was done 2026-07-11 via MCP — see BUILD_PROGRESS.)

Writes: exponential backoff on 429/5xx; parent data_source_id hard-coded from config;
post-write property assertion (re-fetch) before a row counts as synced (delta row 12 —
silently-accepted ≠ verified; Notion accepted 27 parentless blank pages without error).
Select pre-check: missing Platform options are patched into the select before first
write (2026-07-07 mid-session write-failure lesson).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dedup

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
PENDING_PATH = STATE / "notion_pending.json"
SYNC_STATE_PATH = STATE / "notion_sync.json"

API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

REASON_BY_STATUS = {
    "shortlisted": "New — Unreviewed",
    "unverified_blocked": "Unverified/Blocked",
    # dropped/passed carry their own reason field (must be a live select option)
}
VALID_REASONS = {"Stale/Expired", "User Applied Elsewhere", "Filtered Out",
                 "Duplicate Listing", "User Declined", "New — Unreviewed", "Unverified/Blocked"}
VALID_ARCHETYPES = {"Delivery Manager", "Scrum Master", "Technical PM", "BA-leaning"}


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _headers() -> dict:
    token = os.environ.get("NOTION_TOKEN", "")
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"}


def _req(method: str, url: str, **kw) -> requests.Response:
    """REST call with exponential backoff on 429/5xx (delta row 11)."""
    delay = 1.0
    for attempt in range(6):
        r = requests.request(method, url, headers=_headers(), timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("Retry-After", delay)))
            delay = min(delay * 2, 30)
            continue
        return r
    return r


def _platform_option(platform: str, target: str, cfg: dict) -> str:
    """Per-DB platform-name map (§4): the two DBs spell options differently."""
    for p in cfg["platforms"]:
        if p["name"] == platform or platform in (p.get("notion_platform_name") or {}).values():
            return (p.get("notion_platform_name") or {}).get(target, platform)
    if platform == "LinkedIn (tripwire)":
        return "LinkedIn" if target == "tracker" else "Other"
    return platform


def ensure_select_options(ds_id: str, needed: set[str], dry_run: bool = False) -> set[str]:
    """Pre-check the Platform select; PATCH missing options in. Returns available names."""
    r = _req("GET", f"{API}/data_sources/{ds_id}")
    r.raise_for_status()
    schema = r.json().get("properties", {})
    plat = schema.get("Platform", {})
    options = plat.get("select", {}).get("options", [])
    have = {o["name"] for o in options}
    missing = {n for n in needed if n and n not in have}
    if missing and not dry_run:
        payload = {"properties": {"Platform": {"select": {
            "options": [{"name": o["name"], "color": o.get("color", "default")} for o in options]
                       + [{"name": n} for n in sorted(missing)]}}}}
        pr = _req("PATCH", f"{API}/data_sources/{ds_id}", json=payload)
        pr.raise_for_status()
        have |= missing
    return have


def _rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text[:1990]}}] if text else []


def build_passed_seen_properties(rec: dict, cfg: dict) -> dict:
    reason = REASON_BY_STATUS.get(rec["status"]) or rec.get("reason", "Filtered Out")
    if reason not in VALID_REASONS:
        reason = "Filtered Out"
    props = {
        "Role": {"title": _rt(rec.get("role") or "(untitled)")},
        "Company": {"rich_text": _rt(rec.get("company") or "")},
        "Job URL": {"url": rec.get("url") or None},   # raw URL — never markdown (invariant #10)
        "Platform": {"select": {"name": _platform_option(rec.get("platform", ""), "passed_seen", cfg)}},
        "Reason Passed": {"select": {"name": reason}},
        "Date First Seen": {"date": {"start": rec.get("first_seen") or date.today().isoformat()}},
        "Fit Score": {"rich_text": _rt(str(rec.get("fit") or ""))},
        "Keyword Source": {"rich_text": _rt(rec.get("keyword_source") or "")},
        "Notes": {"rich_text": _rt(rec.get("notes") or "")},
    }
    if rec.get("archetype") in VALID_ARCHETYPES:
        props["Archetype"] = {"select": {"name": rec["archetype"]}}
    return props


def build_tracker_properties(rec: dict, cfg: dict) -> dict:
    """Interactive "I applied" flow ONLY. Status always starts Applied (never Interviewing —
    live options: Applied/Screening/Interview/Offer/Rejected/Withdrawn)."""
    return {
        "Role": {"title": _rt(rec.get("role") or "(untitled)")},
        "Company": {"rich_text": _rt(rec.get("company") or "")},
        "Job URL": {"url": rec.get("url") or None},
        "Platform": {"select": {"name": _platform_option(rec.get("platform", ""), "tracker", cfg)}},
        "Status": {"select": {"name": "Applied"}},
        "Source": {"select": {"name": "Claude Skill Scan"}},
        "Date Applied": {"date": {"start": date.today().isoformat()}},  # date-only (is_datetime 0)
        "Fit Score": {"rich_text": _rt(str(rec.get("fit") or ""))},
        "Keyword Source": {"rich_text": _rt(rec.get("keyword_source") or "")},
        "Notes": {"rich_text": _rt((rec.get("notes") or "")[:1900])},
    }


def typed_create_page(ds_id: str, properties: dict, body_lines: list[str] | None = None) -> str:
    """THE write wrapper: parent is always a hard-coded data_source_id (parentless
    create-pages is unrepresentable here), and the row is re-fetched and asserted
    before it counts as written."""
    if not ds_id or len(ds_id.replace("-", "")) != 32:
        raise ValueError(f"refusing write: invalid data_source parent {ds_id!r}")
    payload: dict = {"parent": {"type": "data_source_id", "data_source_id": ds_id},
                     "properties": properties}
    if body_lines:
        payload["children"] = [
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(line)}}
            for line in body_lines if line
        ]
    r = _req("POST", f"{API}/pages", json=payload)
    if r.status_code != 200:
        raise RuntimeError(f"create failed {r.status_code}: {r.text[:300]}")
    page = r.json()
    page_id = page["id"]
    # post-write assertion: silently-accepted ≠ verified
    chk = _req("GET", f"{API}/pages/{page_id}")
    chk.raise_for_status()
    got = chk.json().get("properties", {})
    want_title = properties["Role"]["title"][0]["text"]["content"] if properties["Role"]["title"] else ""
    got_title = "".join(t.get("plain_text", "") for t in got.get("Role", {}).get("title", []))
    parent = chk.json().get("parent", {})
    if got_title != want_title or parent.get("data_source_id", "").replace("-", "") != ds_id.replace("-", ""):
        raise RuntimeError(f"post-write assertion FAILED for {page_id}: "
                           f"title {got_title!r} vs {want_title!r}, parent {parent}")
    return page_id


def append_digest(line: str, cfg: dict) -> str:
    """One line per run on the pinned Job Scout Runs page, newest on top.
    Pinned-ID first; title-search fallback; create only if both miss (2.5.1 anti-race)."""
    page_id = cfg["notion"]["pinned_pages"]["job_scout_runs"]
    r = _req("GET", f"{API}/pages/{page_id}")
    if r.status_code != 200:
        s = _req("POST", f"{API}/search", json={"query": "Job Scout Runs",
                                                "filter": {"property": "object", "value": "page"}})
        hits = [p for p in s.json().get("results", []) if s.status_code == 200]
        if hits:
            page_id = hits[0]["id"]
        else:
            raise RuntimeError("Job Scout Runs page unreachable by pinned ID and title search — "
                               "NOT creating a duplicate; check integration page access")
    block = {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(line)}}
    kids = _req("GET", f"{API}/blocks/{page_id}/children?page_size=1")
    first = (kids.json().get("results") or [None])[0] if kids.status_code == 200 else None
    payload: dict = {"children": [block]}
    if first and first["type"].startswith("heading"):
        payload["after"] = first["id"]  # newest directly under the heading
    ar = _req("PATCH", f"{API}/blocks/{page_id}/children", json=payload)
    if ar.status_code != 200:
        raise RuntimeError(f"digest append failed {ar.status_code}: {ar.text[:200]}")
    return page_id


def _unsynced_records() -> list[dict]:
    seen = dedup.load_seen()
    current: dict[str, dict] = {}
    for rec in list(seen["by_key"].values()) + list(seen["by_url"].values()):
        current[rec.get("url") or rec.get("key")] = rec
    return [r for r in current.values() if not r.get("synced_to_notion")]


def sync_scan(dry_run: bool = False, digest_line: str | None = None) -> None:
    """Push unsynced seen.jsonl records to the PASSED/SEEN LOG (never the Tracker)."""
    cfg = _cfg()
    ds_id = cfg["notion"]["passed_seen"]["data_source_id"]
    records = [r for r in _unsynced_records()
               if r.get("status") in ("shortlisted", "dropped", "passed", "unverified_blocked")]
    if not records and not digest_line:
        print("nothing to sync")
        return
    if not os.environ.get("NOTION_TOKEN"):
        pending = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "instructions": (
                "No NOTION_TOKEN configured. Push each row below via the Notion MCP: "
                "create pages with parent data_source_id "
                f"{ds_id} (Passed/Seen Log) using these exact property values. "
                "NEVER write these to the Applications Tracker. After pushing, mark each "
                "seen.jsonl record synced via scripts/dedup.py update(url, {'synced_to_notion': True})."),
            "rows": [{"url": r.get("url"), "properties": build_passed_seen_properties(r, cfg),
                      "body": [r.get("notes") or ""]} for r in records],
            "digest_line": digest_line,
            "digest_page": cfg["notion"]["pinned_pages"]["job_scout_runs"],
        }
        PENDING_PATH.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"NOTION_TOKEN missing — exported {len(records)} pending rows to {PENDING_PATH.name} "
              "for MCP push by the session")
        return
    needed = {_platform_option(r.get("platform", ""), "passed_seen", cfg) for r in records}
    ensure_select_options(ds_id, needed, dry_run=dry_run)
    ok = failed = 0
    for r in records:
        props = build_passed_seen_properties(r, cfg)
        if dry_run:
            print(f"DRY: would create Passed/Seen row {r.get('role')!r} ({r.get('status')})")
            continue
        try:
            body = [r["notes"]] if r.get("status") == "shortlisted" and r.get("notes") else None
            typed_create_page(ds_id, props, body)
            dedup.update(r.get("url") or r.get("key"), {"synced_to_notion": True})
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"FAILED {r.get('url')}: {exc}", file=sys.stderr)
    if digest_line and not dry_run:
        append_digest(digest_line, cfg)
    SYNC_STATE_PATH.write_text(json.dumps({
        "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pushed": ok, "failed": failed}, indent=1), encoding="utf-8")
    print(f"synced {ok} rows to Passed/Seen Log, {failed} failed"
          + (", digest appended" if digest_line else ""))


def sync_applied(url: str, dry_run: bool = False) -> None:
    """Interactive "I applied" flow: the ONLY path that writes the Tracker."""
    cfg = _cfg()
    seen = dedup.load_seen()
    rec = seen["by_url"].get(dedup.norm_url(url))
    if rec is None:
        raise SystemExit(f"no seen.jsonl record for {url} — log the applied role first (dedup.append)")
    if rec.get("status") != "applied":
        raise SystemExit(f"record status is {rec.get('status')!r}, not 'applied' — Tracker rows exist "
                         "only for applications Borjan explicitly confirmed (invariant #5)")
    ds_id = cfg["notion"]["tracker"]["data_source_id"]
    if not os.environ.get("NOTION_TOKEN"):
        print(json.dumps({"push_via_mcp": {"data_source_id": ds_id,
                                           "properties": build_tracker_properties(rec, cfg)}},
                         ensure_ascii=False, indent=1))
        return
    ensure_select_options(ds_id, {_platform_option(rec.get("platform", ""), "tracker", cfg)},
                          dry_run=dry_run)
    if dry_run:
        print(f"DRY: would create Tracker row {rec.get('role')!r}")
        return
    page_id = typed_create_page(ds_id, build_tracker_properties(rec, cfg))
    dedup.update(url, {"synced_to_notion": True})
    print(f"Tracker row created: {page_id}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--applied", metavar="URL", help="interactive applied flow (Tracker write)")
    ap.add_argument("--digest", metavar="LINE", help="digest line for the Runs page")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.applied:
        sync_applied(args.applied, dry_run=args.dry_run)
    else:
        sync_scan(dry_run=args.dry_run, digest_line=args.digest)
