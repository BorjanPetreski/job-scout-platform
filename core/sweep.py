#!/usr/bin/env python3
"""sweep.py — shortlist liveness sweep (NEW in 4.0; ARCHITECTURE.md §6).

Problem solved: the user may collect shortlisted roles for days before applying;
postings die in the meantime, and before 4.0 nothing re-checked a row after it landed
in "New — Unreviewed". The sweep runs inside every scan (step 8 of the pipeline) and
keeps the accumulated queue honest.

Rules:
  * Scope: seen.jsonl records with status=shortlisted (i.e. still awaiting the user's
    call). Applied/passed/dropped rows are never touched.
  * Recheck policy: SAME liveness definition and SAME checker as scan-time (2.7.0:
    direct/rendered fetch of the source URL only; mirrors never confer liveness).
    Rate-aware: a row is re-checked at most once per sweep.recheck_interval_h
    (default 24h) so a big backlog doesn't multiply fetch load; per-host politeness
    is shared with the main scan via check_links.
  * On CONFIDENT stale (404/410/expired marker/generic-feed redirect): supersede the
    seen record (status=dropped, reason "Stale/Expired", dated sweep note) and queue a
    Notion UPDATE — the existing "New — Unreviewed" row is flipped to Stale/Expired,
    never deleted and never duplicated (flag, not delete: the user sees what expired,
    dedup history stays intact).
  * On unverifiable (bot-wall/JS-shell): mark the sweep state, do NOT retire — same
    honesty rule as scan-time liveness. After sweep.escalate_after_unverifiable
    consecutive unverifiable sweeps, the record's notes get a manual-check flag
    (queued as a Notion notes update).
  * Evidence: every check appends to fetch_evidence.jsonl like any other check.

State: profiles/<id>/state/sweep.json — {norm_url: {last_checked, unverifiable_streak}}.
Synced through git with the rest of the state (state_sync).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_links
import dedup
import paths


def _load_state() -> dict:
    p = paths.sweep_state_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[sweep] WARNING: sweep.json unreadable — starting fresh", file=sys.stderr)
    return {}


def _save_state(state: dict) -> None:
    p = paths.sweep_state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def run_sweep(cfg: dict, use_headless: bool = True) -> dict:
    """Re-check accumulated shortlisted-but-unreviewed rows. Returns counters for the
    ledger/digest: {scope, checked, stale, live, unverifiable, escalated, deferred}."""
    interval_h = int(cfg.get("sweep", {}).get("recheck_interval_h", 24))
    escalate_at = int(cfg.get("sweep", {}).get("escalate_after_unverifiable", 2))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=interval_h)
    today = now.date().isoformat()

    shortlisted = [r for r in dedup.current_records()
                   if r.get("status") == "shortlisted" and r.get("url")]
    state = _load_state()

    due: list[dict] = []
    deferred = 0
    for rec in shortlisted:
        key = dedup.norm_url(rec["url"])
        last = state.get(key, {}).get("last_checked")
        if last:
            try:
                if datetime.fromisoformat(last) > cutoff:
                    deferred += 1
                    continue
            except ValueError:
                pass
        due.append(rec)

    counters = {"scope": len(shortlisted), "checked": len(due), "deferred": deferred,
                "stale": 0, "live": 0, "unverifiable": 0, "escalated": 0}
    if not due:
        return counters

    # The recorded url is the row's Job URL; source_url (when the scan resolved an ATS
    # authority) is stored in notes-level data only, so the sweep checks the Job URL —
    # for ATS-resolved rows that IS the source URL (scan stores it as the row url).
    verdicts = {v["url"]: v for v in check_links.check_urls([r["url"] for r in due], cfg,
                                                            use_headless=use_headless)}
    for rec in due:
        url = rec["url"]
        key = dedup.norm_url(url)
        entry = state.setdefault(key, {"unverifiable_streak": 0})
        entry["last_checked"] = now.isoformat(timespec="seconds")
        v = verdicts.get(url, {"verdict": "unverifiable_direct", "note": "no verdict returned"})

        if v["verdict"] == "stale":
            counters["stale"] += 1
            entry["unverifiable_streak"] = 0
            note = (f"post-shortlist sweep {today}: went stale ({v.get('note', '')}); "
                    f"was shortlisted {rec.get('first_seen', '?')}")
            dedup.update(url, {
                "status": "dropped", "reason": "Stale/Expired",
                "notes": ((rec.get("notes") or "") + " | " + note).strip(" |"),
                "synced_to_notion": False,
                "notion_update": {"reason": "Stale/Expired", "note": note},
            })
        elif v["verdict"] == "live":
            counters["live"] += 1
            entry["unverifiable_streak"] = 0
        else:
            counters["unverifiable"] += 1
            entry["unverifiable_streak"] = int(entry.get("unverifiable_streak", 0)) + 1
            if entry["unverifiable_streak"] == escalate_at:
                counters["escalated"] += 1
                note = (f"❓ sweep could not verify liveness {escalate_at}x in a row "
                        f"(last: {v.get('note', '')}) — check manually before applying")
                dedup.update(url, {
                    "notes": ((rec.get("notes") or "") + " | " + note).strip(" |"),
                    "synced_to_notion": False,
                    "notion_update": {"note": note},
                })

    _save_state(state)
    return counters


if __name__ == "__main__":
    import argparse

    import profile_loader

    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=None)
    ap.add_argument("--no-headless", action="store_true")
    cli = ap.parse_args()
    cfg = profile_loader.load(cli.profile or paths.get_profile())
    c = run_sweep(cfg, use_headless=not cli.no_headless)
    print(f"[sweep] scope={c['scope']} checked={c['checked']} deferred={c['deferred']} "
          f"stale={c['stale']} live={c['live']} unverifiable={c['unverifiable']} "
          f"escalated={c['escalated']}")
