#!/usr/bin/env python3
"""provision_notion.py — provision (or adopt) a profile's Notion databases (Phase 2 §5).

Creates the three artifacts the engine's Notion contract assumes, under a caller-supplied
parent page, then writes the resulting IDs into the profile's `output.notion`:
  * Applications Tracker  — status/Source/Date Applied/Fit/Keyword Source/Notes (+ the six
                            canonical Status options). NEVER a scan-write target.
  * Passed/Seen Log       — the scanner's only write target (Reason Passed incl. "New —
                            Unreviewed"/"Stale/Expired", Platform, Archetype, …).
  * Runs page             — the pinned digest page (a heading anchor so newest-on-top works).

Design contract (D11/D17/D18/D19):
  - token + parent-page are PARAMETERS, never hardcoded (--token / NOTION_TOKEN via the
    core/secrets seam; --parent-page-id). D11.
  - instruct -> verify-by-probe (D17): database + page creation are solidly in the REST
    API; creating the saved "📥 New — Unreviewed" VIEW is NOT (probed 2026-07-16:
    /v1/database_views 400s) — provision prints the exact manual step and a probe-confirm,
    an honest instruct->verify, never a silent skip.
  - idempotent via a marker (D19): re-running detects existing Tracker/Passed-Seen databases
    by title under the parent and ADOPTS them (verify schema, report gaps) — never duplicates.
  - secret seam (D18): the token is resolved via core/secrets (env fallback for the trial)
    and never written to the profile/repo.

Modes:
  provision  create missing DBs/page under the parent (adopting any that already exist), then
             write output.notion into the profile.
  adopt      point at existing DBs by title under the parent; verify schema compatibility and
             report gaps; write output.notion. Never mutates beyond additive select options.

Usage:
  provision_notion.py --profile <id> --parent-page-id <uuid> [--token <tok>] [--mode provision|adopt]
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
import profile_loader
import secrets as secret_seam

API = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"          # MUST match notion_sync.py (data-sources model)

TRACKER_TITLE = "Applications Tracker"
PASSED_SEEN_TITLE = "Passed/Seen Log"
RUNS_TITLE = "Job Scout Runs"
RUNS_ANCHOR = "Run digest — newest on top"

TRACKER_STATUS_OPTIONS = ["Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"]
SOURCE_OPTIONS = ["Claude Skill Scan", "Manual Entry"]
REASON_OPTIONS = ["New — Unreviewed", "Stale/Expired", "Filtered Out", "Duplicate Listing",
                  "User Declined", "User Applied Elsewhere", "Unverified/Blocked"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json"}


def _req(method: str, url: str, token: str, **kw) -> requests.Response:
    delay = 1.0
    r = None
    for _ in range(6):
        r = requests.request(method, url, headers=_headers(token), timeout=30, **kw)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(float(r.headers.get("Retry-After", delay)))
            delay = min(delay * 2, 30)
            continue
        return r
    return r


def _select(options: list[str]) -> dict:
    return {"select": {"options": [{"name": o} for o in options]}}


def _tracker_schema() -> dict:
    return {
        "Role": {"title": {}},
        "Company": {"rich_text": {}},
        "Job URL": {"url": {}},
        "Platform": {"select": {"options": []}},          # patched lazily before first write
        "Status": _select(TRACKER_STATUS_OPTIONS),
        "Source": _select(SOURCE_OPTIONS),
        "Date Applied": {"date": {}},
        "Fit Score": {"rich_text": {}},
        "Keyword Source": {"rich_text": {}},
        "Notes": {"rich_text": {}},
    }


def _passed_seen_schema(archetypes: list[str]) -> dict:
    return {
        "Role": {"title": {}},
        "Company": {"rich_text": {}},
        "Job URL": {"url": {}},
        "Platform": {"select": {"options": []}},
        "Reason Passed": _select(REASON_OPTIONS),
        "Date First Seen": {"date": {}},
        "Fit Score": {"rich_text": {}},
        "Keyword Source": {"rich_text": {}},
        "Notes": {"rich_text": {}},
        "Archetype": _select(list(archetypes)),
    }


def _title_rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


# --------------------------------------------------------------- discovery (idempotency)

def _child_databases(parent_page_id: str, token: str) -> dict[str, dict]:
    """Map {title: {database_id, data_source_id}} for child databases under the parent
    page — the idempotency marker (D19). Paginates the parent's block children."""
    out: dict[str, dict] = {}
    cursor = None
    while True:
        url = f"{API}/blocks/{parent_page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = _req("GET", url, token)
        r.raise_for_status()
        data = r.json()
        for blk in data.get("results", []):
            if blk.get("type") != "child_database":
                continue
            title = blk["child_database"].get("title", "")
            db_id = blk["id"]
            ds_id = _first_data_source_id(db_id, token)
            out[title] = {"database_id": db_id, "data_source_id": ds_id}
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return out


def _first_data_source_id(database_id: str, token: str) -> str | None:
    r = _req("GET", f"{API}/databases/{database_id}", token)
    if r.status_code != 200:
        return None
    ds = r.json().get("data_sources") or []
    return ds[0]["id"] if ds else None


def _data_source_properties(ds_id: str, token: str) -> dict:
    r = _req("GET", f"{API}/data_sources/{ds_id}", token)
    r.raise_for_status()
    return r.json().get("properties", {})


# --------------------------------------------------------------------- creation

def _create_database(parent_page_id: str, title: str, schema: dict, token: str) -> dict:
    body = {"parent": {"type": "page_id", "page_id": parent_page_id},
            "title": _title_rt(title),
            "initial_data_source": {"properties": schema}}
    r = _req("POST", f"{API}/databases", token, json=body)
    if r.status_code != 200:
        raise SystemExit(f"[provision] create database {title!r} FAILED {r.status_code}: {r.text[:300]}")
    b = r.json()
    ds = (b.get("data_sources") or [{}])[0]
    return {"database_id": b["id"], "data_source_id": ds.get("id")}


def _create_runs_page(parent_page_id: str, title: str, token: str) -> str:
    body = {"parent": {"type": "page_id", "page_id": parent_page_id},
            "properties": {"title": {"title": _title_rt(title)}},
            "children": [{"object": "block", "type": "heading_2",
                          "heading_2": {"rich_text": _title_rt(RUNS_ANCHOR)}}]}
    r = _req("POST", f"{API}/pages", token, json=body)
    if r.status_code != 200:
        raise SystemExit(f"[provision] create Runs page FAILED {r.status_code}: {r.text[:300]}")
    return r.json()["id"]


def _find_runs_page(parent_page_id: str, token: str) -> str | None:
    """Child pages titled like the Runs page (idempotency for the digest page)."""
    cursor = None
    while True:
        url = f"{API}/blocks/{parent_page_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = _req("GET", url, token)
        r.raise_for_status()
        data = r.json()
        for blk in data.get("results", []):
            if blk.get("type") == "child_page" and RUNS_TITLE.lower() in blk["child_page"].get("title", "").lower():
                return blk["id"]
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return None


# ------------------------------------------------------------- schema verification (adopt)

def _verify_schema(ds_id: str, expected: dict, token: str, label: str) -> list[str]:
    """Report missing properties / select-option gaps without mutating (adopt safety)."""
    have = _data_source_properties(ds_id, token)
    gaps: list[str] = []
    for name, spec in expected.items():
        if name not in have:
            gaps.append(f"{label}: missing property {name!r}")
            continue
        want_type = next(iter(spec))
        got_type = have[name].get("type")
        if got_type != want_type:
            gaps.append(f"{label}: property {name!r} is {got_type!r}, expected {want_type!r}")
            continue
        if want_type == "select":
            want_opts = {o["name"] for o in spec["select"]["options"]}
            got_opts = {o["name"] for o in have[name].get("select", {}).get("options", [])}
            missing = want_opts - got_opts
            if missing:            # additive only — select options are lazily patchable, not fatal
                gaps.append(f"{label}: select {name!r} missing options {sorted(missing)} "
                            "(auto-added lazily before first write; not fatal)")
    return gaps


# -------------------------------------------------------------------- profile write

def _write_profile_notion(profile_id: str, notion_block: dict) -> None:
    """Write output.notion into the profile.yaml and drop any dry_run flag. Freshly
    generated profiles carry no precious comments, so a safe_dump round-trip is fine.
    NEVER touches any profile but the one named."""
    path = paths.profile_yaml(profile_id)
    prof = yaml.safe_load(path.read_text(encoding="utf-8"))
    prof.pop("dry_run", None)
    prof.setdefault("output", {})["notion"] = notion_block
    path.write_text(yaml.safe_dump(prof, sort_keys=False, allow_unicode=True), encoding="utf-8")


# ------------------------------------------------------------------------- driver

def provision(profile_id: str, parent_page_id: str, token: str, mode: str = "provision") -> dict:
    prof = yaml.safe_load(paths.profile_yaml(profile_id).read_text(encoding="utf-8"))
    archetypes = ((prof.get("search") or {}).get("archetypes")
                  or ((prof.get("template") and profile_loader.load_template(prof["template"])
                       .get("defaults", {}).get("search", {}).get("archetypes")) or []))
    existing = _child_databases(parent_page_id, token)
    report: list[str] = []
    result: dict = {}

    def get_or_create(title, schema, adopt_expected):
        if title in existing and existing[title].get("data_source_id"):
            report.append(f"adopted existing {title!r} (data_source {existing[title]['data_source_id']})")
            gaps = _verify_schema(existing[title]["data_source_id"], adopt_expected, token, title)
            report.extend(gaps)
            return existing[title]
        if mode == "adopt":
            raise SystemExit(f"[provision] adopt mode: no existing {title!r} under the parent to adopt")
        made = _create_database(parent_page_id, title, schema, token)
        report.append(f"created {title!r} (database {made['database_id']}, data_source {made['data_source_id']})")
        return made

    tracker = get_or_create(TRACKER_TITLE, _tracker_schema(), _tracker_schema())
    passed_seen = get_or_create(PASSED_SEEN_TITLE, _passed_seen_schema(archetypes),
                                _passed_seen_schema(archetypes))

    runs_id = _find_runs_page(parent_page_id, token)
    if runs_id:
        report.append(f"adopted existing Runs page ({runs_id})")
    elif mode == "adopt":
        raise SystemExit("[provision] adopt mode: no existing Runs page under the parent")
    else:
        runs_id = _create_runs_page(parent_page_id, f"{RUNS_TITLE}", token)
        report.append(f"created Runs page ({runs_id})")

    notion_block = {
        "tracker": {"data_source_id": tracker["data_source_id"], "parent_page_id": parent_page_id},
        "passed_seen": {"data_source_id": passed_seen["data_source_id"], "parent_page_id": parent_page_id},
        "pinned_pages": {"job_scout_runs": runs_id},
        "tracker_status_options": TRACKER_STATUS_OPTIONS,
    }
    _write_profile_notion(profile_id, notion_block)
    result["notion"] = notion_block
    result["report"] = report
    # D17 instruct->verify for the saved view (not creatable via REST — probed 2026-07-16)
    result["view_instruction"] = (
        "MANUAL (D17 instruct→verify — the Notion REST API cannot create a saved view): under "
        f"the Passed/Seen Log, add a board/filtered view named '📥 New — Unreviewed' filtered to "
        "Reason Passed = 'New — Unreviewed'. The interactive setup can do this via the Notion MCP "
        "notion-create-view tool; then confirm it exists. This does not block provisioning.")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Provision/adopt a profile's Notion databases.")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--parent-page-id", required=True)
    ap.add_argument("--token", default=None, help="Notion token (else core/secrets → NOTION_TOKEN env)")
    ap.add_argument("--mode", choices=["provision", "adopt"], default="provision")
    args = ap.parse_args()

    paths.set_profile(args.profile)
    token = secret_seam.resolve_notion_token(override=args.token, profile_id=args.profile)
    if not token:
        raise SystemExit("[provision] no Notion token — pass --token or set NOTION_TOKEN (D11/D18)")

    # instruct→verify-by-probe (D17): confirm the integration can reach the parent before work.
    probe = _req("GET", f"{API}/pages/{args.parent_page_id.replace('-', '')}", token)
    if probe.status_code != 200:
        raise SystemExit(
            f"[provision] the integration cannot access parent page {args.parent_page_id} "
            f"({probe.status_code}). In Notion, open the parent page → ••• → Connections → add "
            f"your integration, then re-run. (D17: this click cannot be scripted.)")

    result = provision(args.profile, args.parent_page_id, token, mode=args.mode)
    print(f"[provision] {args.mode} complete for profile {args.profile!r}:")
    for line in result["report"]:
        print(f"  • {line}")
    print(f"  output.notion written to {paths.profile_yaml(args.profile)}")
    print("\n" + result["view_instruction"])


if __name__ == "__main__":
    main()
