#!/usr/bin/env python3
"""state_sync.py — git round-trip for scan state (Cloud lane, v3.1.0).

Cloud Claude Code sessions run in ephemeral containers: local disk is wiped between
sessions, so git is the state's home. Every cloud scan MUST:
    python3 scripts/state_sync.py pull     # FIRST action, before scan.py
    ... scan / score / log decisions ...
    python3 scripts/state_sync.py push     # LAST action, after notion_sync

Laptop runs may also use it (optional but recommended once the cloud lane is active —
it keeps both lanes' dedup history converged; dedup makes overlapping runs harmless).

Conflict policy (two runs racing on push):
  *.jsonl  → union merge: both sides' lines kept, duplicates dropped, remote-first
             order (files are append-only; dedup.load_seen is last-wins by key, so a
             slightly reordered union is safe).
  runs.json → deep merge of day/label entries; recompute.sessions_since takes the max.
  anything else → local version wins, warning printed (never lose this run's decisions).

jd_cache/ is NOT synced — bulky and regenerable; each session refetches what it scores.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATHS = ["state/seen.jsonl", "state/runs.json", "state/fetch_evidence.jsonl",
               "state/last_run_candidates.json", "state/notion_sync.json"]


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=check)


def _branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _stage_version(path: str, stage: int) -> str:
    """Return the staged version of a conflicted file (2=ours, 3=theirs)."""
    r = _git("show", f":{stage}:{path}", check=False)
    return r.stdout if r.returncode == 0 else ""


def _merge_jsonl(ours: str, theirs: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for chunk in (theirs, ours):  # remote history first, then local additions
        for line in chunk.splitlines():
            if line.strip() and line not in seen:
                seen.add(line)
                out.append(line)
    return "\n".join(out) + "\n"


def _merge_runs(ours: str, theirs: str) -> str:
    try:
        a, b = json.loads(ours or "{}"), json.loads(theirs or "{}")
    except json.JSONDecodeError:
        return ours or theirs
    merged = dict(b)
    for day, runs in a.items():
        if day == "recompute":
            continue
        merged.setdefault(day, {})
        if isinstance(runs, dict):
            merged[day] = {**merged.get(day, {}), **runs}
    ra, rb = a.get("recompute", {}), b.get("recompute", {})
    merged["recompute"] = {
        "last": max(ra.get("last", ""), rb.get("last", "")),
        "sessions_since": max(ra.get("sessions_since", 0), rb.get("sessions_since", 0)),
        "due_at_sessions": ra.get("due_at_sessions") or rb.get("due_at_sessions") or 5,
    }
    return json.dumps(merged, ensure_ascii=False, indent=1)


def _resolve_conflicts() -> bool:
    """Merge conflicted state files during a rebase. True if everything was handled."""
    r = _git("diff", "--name-only", "--diff-filter=U", check=False)
    conflicted = [f for f in r.stdout.splitlines() if f.strip()]
    ok = True
    for f in conflicted:
        ours, theirs = _stage_version(f, 2), _stage_version(f, 3)
        p = ROOT / f
        if f.endswith(".jsonl"):
            p.write_text(_merge_jsonl(ours, theirs), encoding="utf-8")
        elif f.endswith("runs.json"):
            p.write_text(_merge_runs(ours, theirs), encoding="utf-8")
        elif f.startswith("state/"):
            p.write_text(ours or theirs, encoding="utf-8")  # local wins on misc state
            print(f"[state_sync] WARN: kept local {f} over remote", file=sys.stderr)
        else:
            ok = False  # non-state conflict — not ours to resolve
            continue
        _git("add", f)
    return ok


def pull() -> None:
    branch = _branch()
    _git("fetch", "origin", branch, check=False)
    r = _git("pull", "--rebase", "--autostash", "origin", branch, check=False)
    if r.returncode == 0:
        print(f"[state_sync] pulled {branch} clean")
        return
    if _resolve_conflicts():
        c = _git("rebase", "--continue", check=False)
        if c.returncode == 0:
            print(f"[state_sync] pulled {branch} with state merge")
            return
    _git("rebase", "--abort", check=False)
    print("[state_sync] WARN: rebase failed on non-state files — keeping local tree; "
          "push will retry the merge", file=sys.stderr)


def push(message: str | None = None) -> None:
    branch = _branch()
    _git("add", "--", *STATE_PATHS, check=False)
    diff = _git("diff", "--cached", "--quiet", check=False)
    if diff.returncode == 0:
        print("[state_sync] no state changes to push")
        return
    msg = message or f"scan state: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}"
    _git("commit", "-q", "-m", msg)
    for attempt in range(4):
        r = _git("push", "origin", branch, check=False)
        if r.returncode == 0:
            print(f"[state_sync] pushed state to {branch}")
            return
        time.sleep(2 ** attempt)
        pull()  # someone else pushed — merge their state and retry
    raise SystemExit(f"[state_sync] push failed after retries: {r.stderr[-300:]}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("pull", "push"):
        print("usage: state_sync.py pull | push ['commit message']", file=sys.stderr)
        sys.exit(2)
    if sys.argv[1] == "pull":
        pull()
    else:
        push(sys.argv[2] if len(sys.argv) > 2 else None)
