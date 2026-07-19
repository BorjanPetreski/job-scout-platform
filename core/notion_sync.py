#!/usr/bin/env python3
"""notion_sync.py — one-way push: local state → Notion. Direct REST, typed writes.
Profile-parameterized since 4.0: all targets come from the profile's output.notion.

Data flow (2.7.0 invariant #5, enforced structurally):
  * Scan-driven writes go to the PASSED/SEEN LOG ONLY.
      shortlisted        → Reason Passed = "New — Unreviewed" (+ role notes in page body)
      dropped            → the real reason (Stale/Expired, Filtered Out, Duplicate Listing, …)
      unverified_blocked → "Unverified/Blocked"
  * SWEEP UPDATES (4.0): a record carrying `notion_update` was already synced as a row;
    the sweep flipped it locally (e.g. shortlisted → Stale/Expired). The sync UPDATES
    the existing row in place (found by Job URL) — flip, never delete, never duplicate.
  * The Applications Tracker is NEVER a scan-write target. Tracker rows are created only
    by the interactive "I applied" flow (`notion_sync.py --applied <url>`), after Claude
    marks the seen.jsonl row `applied` on the user's explicit confirmation.
    sync_scan() cannot reach the Tracker: the write wrapper takes its data-source id from
    the flow, and the scan flow only ever passes the Passed/Seen id (delta rows 12/13 —
    the 2026-07-10 violation is uncompilable, not a rule to remember).

Auth: NOTION_TOKEN env var. No token → nothing is written; pending rows/updates are
exported to profiles/<id>/state/notion_pending.json with full property payloads so a
Claude session can push them via the Notion MCP verbatim.

Dry-run profiles (output.notion.dry_run) have no targets — every sync call refuses
loudly instead of writing anywhere.

Writes: exponential backoff on 429/5xx; parent data_source_id from the profile;
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dedup
import paths
import profile_loader

API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"

REASON_BY_STATUS = {
    "shortlisted": "New — Unreviewed",
    "unverified_blocked": "Unverified/Blocked",
    # dropped/passed carry their own reason field (must be a live select option)
}
VALID_REASONS = {"Stale/Expired", "User Applied Elsewhere", "Filtered Out",
                 "Duplicate Listing", "User Declined", "New — Unreviewed", "Unverified/Blocked"}


def _cfg() -> dict:
    cfg = profile_loader.load(paths.get_profile())
    if cfg["notion"].get("dry_run"):
        raise SystemExit(f"[notion_sync] profile {cfg['profile_id']!r} is a dry-run profile — "
                         "no Notion targets configured; refusing to sync")
    return cfg


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
    """Per-DB platform-name map: the two DBs may spell options differently."""
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
    archetypes = set((cfg["profile"].get("search") or {}).get("archetypes") or [])
    if rec.get("archetype") in archetypes:
        props["Archetype"] = {"select": {"name": rec["archetype"]}}
    return props


def build_tracker_properties(rec: dict, cfg: dict) -> dict:
    """Interactive "I applied" flow ONLY. Status always starts Applied (never Interviewing —
    live options come from the profile's tracker_status_options)."""
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
    """THE write wrapper: parent is always a validated data_source_id (parentless
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


def find_page_by_url(ds_id: str, url: str) -> str | None:
    """Locate an existing Passed/Seen row by its Job URL (the sweep-update path)."""
    r = _req("POST", f"{API}/data_sources/{ds_id}/query",
             json={"filter": {"property": "Job URL", "url": {"equals": url}}, "page_size": 2})
    if r.status_code != 200:
        return None
    results = r.json().get("results", [])
    return results[0]["id"] if results else None


def _current_reason(page_id: str) -> str | None:
    """Read a Passed/Seen row's current `Reason Passed` select (the sweep read-before-write
    guard). None if the page can't be read or carries no select value."""
    r = _req("GET", f"{API}/pages/{page_id}")
    if r.status_code != 200:
        return None
    sel = (r.json().get("properties", {}).get("Reason Passed", {}) or {}).get("select") or {}
    return sel.get("name")


def flip_passed_seen_to_applied(ps_ds_id: str, url: str) -> str:
    """Close the applied-lingering gap (tasks #8/#11): when a role is applied to, its
    Applications-Tracker row is created but the ORIGINATING shortlist row would otherwise sit in
    `📥 New — Unreviewed` forever (nothing flips it). Flip it → `User Applied Elsewhere`.

    This writes the PASSED/SEEN LOG — the scanner's OWN write target — NOT the Tracker, so the
    firewall (never write the Tracker) is untouched. Read-before-write guard, identical to
    apply_sweep_update: only a row STILL `New — Unreviewed` is flipped, so a companion/user-
    resolved reason is never clobbered and a re-run is a no-op (idempotent).

    Returns one of: 'flipped' | 'missing' (no row for this URL) | f'skip:{current!r}' (already
    resolved) | f'error:{code}'."""
    page_id = find_page_by_url(ps_ds_id, url)
    if not page_id:
        return "missing"
    current = _current_reason(page_id)
    if current != "New — Unreviewed":
        return f"skip:{current!r}"
    r = _req("PATCH", f"{API}/pages/{page_id}",
             json={"properties": {"Reason Passed": {"select": {"name": "User Applied Elsewhere"}}}})
    if r.status_code != 200:
        return f"error:{r.status_code}"
    return "flipped"


def apply_sweep_update(ds_id: str, rec: dict, cfg: dict) -> bool:
    """Flip an existing row per the record's notion_update: Reason Passed and/or a
    dated sweep note appended to Notes. Falls back to create if the row never synced.

    Read-before-write guard (3a.4, write-ownership by row STATE / D7): the sweep only owns
    the `New — Unreviewed` → `Stale/Expired` transition. A row the companion or the user has
    already resolved (`User Applied Elsewhere`, `User Declined`, or any non-`New — Unreviewed`
    reason) is left untouched — a blind PATCH would clobber it back to `Stale/Expired` when the
    posting later dies (a `User Declined` flip has no Tracker row to reconcile the local
    `seen.jsonl` from, so its record is still `shortlisted` and stays in sweep scope). The
    guard checks the LIVE Notion reason before writing, never the stale local record."""
    upd = rec.get("notion_update") or {}
    page_id = find_page_by_url(ds_id, rec.get("url") or "")
    if not page_id:
        # row never made it to Notion (e.g. sweep ran before a failed sync) — create it
        typed_create_page(ds_id, build_passed_seen_properties(rec, cfg),
                          [rec.get("notes") or ""])
        return True
    current = _current_reason(page_id)
    if current != "New — Unreviewed":
        # resolved by the companion/user (or unreadable) — do NOT clobber. Treated as handled
        # so the record is marked synced and the sweep won't retry the write forever.
        print(f"[sweep-guard] {rec.get('url')}: Notion row is {current!r} (companion/user-resolved) "
              f"— skipping sweep flip, no clobber", file=sys.stderr)
        return True
    props: dict = {}
    if upd.get("reason"):
        reason = upd["reason"] if upd["reason"] in VALID_REASONS else "Stale/Expired"
        props["Reason Passed"] = {"select": {"name": reason}}
    if upd.get("note") or upd.get("reason"):
        props["Notes"] = {"rich_text": _rt(rec.get("notes") or upd.get("note") or "")}
    r = _req("PATCH", f"{API}/pages/{page_id}", json={"properties": props})
    if r.status_code != 200:
        raise RuntimeError(f"sweep update failed {r.status_code}: {r.text[:300]}")
    return True


def append_digest(line: str, cfg: dict) -> str:
    """One line per run on the pinned Runs page, newest on top.
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
            raise RuntimeError("Runs page unreachable by pinned ID and title search — "
                               "NOT creating a duplicate; check integration page access")
    block = {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(line)}}
    kids = _req("GET", f"{API}/blocks/{page_id}/children?page_size=1")
    first = (kids.json().get("results") or [None])[0] if kids.status_code == 200 else None
    payload: dict = {"children": [block]}
    if first:
        # The REST API can only insert AFTER a block (no prepend). The page carries a
        # heading anchor at the top ("Run digest — newest on top", added 2026-07-12);
        # inserting after block 1 keeps newest-on-top. Works even if the anchor is
        # replaced by a digest line — position 2 still beats the bottom of the page.
        payload["after"] = first["id"]
    ar = _req("PATCH", f"{API}/blocks/{page_id}/children", json=payload)
    if ar.status_code != 200:
        raise RuntimeError(f"digest append failed {ar.status_code}: {ar.text[:200]}")
    return page_id


def _unsynced_records() -> list[dict]:
    return [r for r in dedup.current_records() if not r.get("synced_to_notion")]


def sync_scan(dry_run: bool = False, digest_line: str | None = None) -> None:
    """Push unsynced seen.jsonl records to the PASSED/SEEN LOG (never the Tracker).
    Records carrying notion_update are UPDATED in place; the rest are created."""
    cfg = _cfg()
    ds_id = cfg["notion"]["passed_seen"]["data_source_id"]
    records = [r for r in _unsynced_records()
               if r.get("status") in ("shortlisted", "dropped", "passed", "unverified_blocked")]
    creates = [r for r in records if not r.get("notion_update")]
    updates = [r for r in records if r.get("notion_update")]
    if not records and not digest_line:
        print("nothing to sync")
        return
    pending_path = paths.state_dir() / "notion_pending.json"
    if not os.environ.get("NOTION_TOKEN"):
        pending = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "profile": cfg["profile_id"],
            "instructions": (
                "No NOTION_TOKEN configured. Push each row below via the Notion MCP: "
                "create pages with parent data_source_id "
                f"{ds_id} (Passed/Seen Log) using these exact property values. Rows under "
                "'updates' are EXISTING pages — find each by its Job URL in the same data "
                "source and PATCH Reason Passed/Notes as given; NEVER create duplicates for "
                "them and NEVER write anything to the Applications Tracker. After pushing, "
                "mark each seen.jsonl record synced via core/dedup.py "
                "update(url, {'synced_to_notion': True})."),
            "rows": [{"url": r.get("url"), "properties": build_passed_seen_properties(r, cfg),
                      "body": [r.get("notes") or ""]} for r in creates],
            "updates": [{"url": r.get("url"), "notion_update": r.get("notion_update"),
                         "notes": r.get("notes")} for r in updates],
            "digest_line": digest_line,
            "digest_page": cfg["notion"]["pinned_pages"]["job_scout_runs"],
        }
        pending_path.write_text(json.dumps(pending, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"NOTION_TOKEN missing — exported {len(creates)} pending rows + {len(updates)} "
              f"updates to {pending_path.name} for MCP push by the session")
        return
    needed = {_platform_option(r.get("platform", ""), "passed_seen", cfg) for r in records}
    ensure_select_options(ds_id, needed, dry_run=dry_run)
    ok = failed = 0
    for r in creates:
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
    for r in updates:
        if dry_run:
            print(f"DRY: would update Passed/Seen row {r.get('role')!r} -> {r.get('notion_update')}")
            continue
        try:
            apply_sweep_update(ds_id, r, cfg)
            dedup.update(r.get("url") or r.get("key"),
                         {"synced_to_notion": True, "notion_update": None})
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"FAILED update {r.get('url')}: {exc}", file=sys.stderr)
    if digest_line and not dry_run:
        append_digest(digest_line, cfg)
    (paths.state_dir() / "notion_sync.json").write_text(json.dumps({
        "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pushed": ok, "failed": failed}, indent=1), encoding="utf-8")
    print(f"synced {ok} rows to Passed/Seen Log ({len(updates)} as in-place updates), "
          f"{failed} failed" + (", digest appended" if digest_line else ""))


def sync_applied(url: str, dry_run: bool = False) -> None:
    """Interactive "I applied" flow: the ONLY path that writes the Tracker."""
    cfg = _cfg()
    seen = dedup.load_seen()
    rec = seen["by_url"].get(dedup.norm_url(url))
    if rec is None:
        raise SystemExit(f"no seen.jsonl record for {url} — log the applied role first (dedup.append)")
    if rec.get("status") != "applied":
        raise SystemExit(f"record status is {rec.get('status')!r}, not 'applied' — Tracker rows exist "
                         "only for applications the user explicitly confirmed (invariant #5)")
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
    # #8/#11: flip the originating shortlist row out of `New — Unreviewed` so the applied role
    # doesn't linger in the queue. Guarded (only if still New) → never clobbers a resolved row.
    ps_ds = (cfg["notion"].get("passed_seen") or {}).get("data_source_id")
    if ps_ds:
        print(f"Passed/Seen shortlist row: {flip_passed_seen_to_applied(ps_ds, url)}")


def reconcile_applied_from_tracker(cfg: dict) -> dict:
    """Scan-start cross-process dedup handoff (3a.4, D8). READ the Applications Tracker and
    back-fill any matching `seen.jsonl` record to `status: applied`, so a role the companion
    recorded as applied (Tracker row created on claude.ai) dedups on the next scan AND leaves
    the shortlist sweep's scope (which is `shortlisted`-only) the same run.

    It ALSO heals the applied-lingering gap (tasks #8/#11): for each matched Tracker row it
    flips the originating Passed/Seen shortlist row out of `New — Unreviewed` →
    `User Applied Elsewhere` (via `flip_passed_seen_to_applied`), so an applied role stops
    sitting in the `📥 New — Unreviewed` queue. This is the catch-all net — it covers a
    companion apply whose own flip was missed AND back-heals rows applied before this fix,
    regardless of which apply path created the Tracker row.

    This is the ONE additive scanner-side reconciliation step. It is:
      * READ-ONLY on the Tracker — the firewall (the scanner never WRITES the Tracker) is
        intact; the Tracker access is a query, nothing more. The flip writes the PASSED/SEEN
        LOG — the scanner's OWN write target — not the Tracker;
      * token-gated — no `NOTION_TOKEN` → honest skip, reported in the ledger, no behavior
        change; dry-run profiles skip too (no Tracker);
      * idempotent — a record already `applied` is left alone in `seen.jsonl` (no redundant
        append), and the flip is read-before-write guarded (only a row STILL `New — Unreviewed`
        is touched), so re-running the scan neither grows `seen.jsonl` nor re-writes Notion.

    Never fetches boards, filters, scores, or writes shortlist rows.
    Returns counters for the ledger:
    {tokenless, tracker_rows, backfilled, already, unmatched, passed_seen_flipped}.
    """
    result = {"tokenless": False, "tracker_rows": 0, "backfilled": 0, "already": 0,
              "unmatched": 0, "passed_seen_flipped": 0, "skipped": None}
    if cfg["notion"].get("dry_run"):
        result["skipped"] = "dry-run profile"
        return result
    ds_id = (cfg["notion"].get("tracker") or {}).get("data_source_id")
    if not ds_id:
        result["skipped"] = "no tracker data_source_id"
        return result
    if not os.environ.get("NOTION_TOKEN"):
        result["tokenless"] = True
        return result

    urls: list[str] = []
    cursor = None
    while True:
        body: dict = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = _req("POST", f"{API}/data_sources/{ds_id}/query", json=body)
        if r.status_code != 200:
            result["skipped"] = f"tracker query {r.status_code}"
            return result
        data = r.json()
        for row in data.get("results", []):
            u = (row.get("properties", {}).get("Job URL", {}) or {}).get("url")
            if u:
                urls.append(u)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    result["tracker_rows"] = len(urls)
    ps_ds = (cfg["notion"].get("passed_seen") or {}).get("data_source_id")

    seen = dedup.load_seen()
    for u in urls:
        rec = seen["by_url"].get(dedup.norm_url(u))
        if rec is None:
            result["unmatched"] += 1          # Manual-Entry role the scanner never saw — nothing to reconcile
            continue
        if rec.get("status") == "applied":
            result["already"] += 1            # idempotent: already reconciled locally
        else:
            note = ((rec.get("notes") or "") + " | reconciled applied from Applications Tracker "
                    "(companion/chat apply)").strip(" |")
            dedup.update(u, {"status": "applied", "reason": "User Applied Elsewhere", "notes": note})
            result["backfilled"] += 1
        # #8/#11 heal: flip the lingering shortlist row (guarded — no-op if already resolved).
        if ps_ds and flip_passed_seen_to_applied(ps_ds, u) == "flipped":
            result["passed_seen_flipped"] += 1
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--applied", metavar="URL", help="interactive applied flow (Tracker write)")
    ap.add_argument("--reconcile", action="store_true",
                    help="scan-start dedup handoff: back-fill seen.jsonl 'applied' from the Tracker")
    ap.add_argument("--digest", metavar="LINE", help="digest line for the Runs page")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--profile", default=None)
    args = ap.parse_args()
    if args.profile:
        paths.set_profile(args.profile)
    if args.applied:
        sync_applied(args.applied, dry_run=args.dry_run)
    elif args.reconcile:
        print(json.dumps(reconcile_applied_from_tracker(_cfg()), ensure_ascii=False))
    else:
        sync_scan(dry_run=args.dry_run, digest_line=args.digest)
