#!/usr/bin/env python3
"""arch_review.py — the "architecture review due" cadence counter (CLAUDE.md DoD #5).

DoD #5 (the periodic, whole-codebase architecture-quality pass scoped in
docs/ARCHITECTURE_QUALITY_SCOPE.md) is a JUDGMENT call, never automatic busywork — but
"is one due?" is easy to forget. This rides the exact same rails as the health-review and
tier-recompute counters already in runs.json: scan.py bumps `arch_review.sessions_since`
each run and prints `⚠ architecture review due` once it crosses `due_at_sessions`, which is
Claude's cue to ASSESS whether a full pass is worth running (weighed against cost/benefit —
a quiet, small, or recently-reviewed codebase may not need one). Running the pass, then
`python3 core/arch_review.py --ack`, resets the counter.

Like health_review/recompute, the counter increments per SCAN RUN — an imperfect proxy for
"core/-touching sessions" (a coding-only session that never scans doesn't tick it), but the
same proxy those two use, and the real trigger stays Claude's judgment, not the number. The
counter lives per-profile in each runs.json; a full pass covers the shared engine for every
profile, so `--ack` with no --profile resets EVERY profile's counter (one pass, all acked).

Run: python3 core/arch_review.py [--profile <id>]         # status: how many since last pass
     python3 core/arch_review.py --ack [--profile <id>]   # after running a full pass
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

DEFAULT_DUE_AT_SESSIONS = 10   # ~10 core/-touching sessions since the last full pass (DoD #5)


def bump(runs: dict, due_default: int = DEFAULT_DUE_AT_SESSIONS) -> dict:
    """Increment (create on first run) the arch-review-due counter in a runs.json dict, in
    place. Mirrors scan.py's health_review counter. Returns the counter block."""
    ar = runs.setdefault("arch_review", {"last": date.today().isoformat(), "sessions_since": 0,
                                         "due_at_sessions": due_default})
    ar["sessions_since"] = ar.get("sessions_since", 0) + 1
    return ar


def is_due(ar: dict, due_default: int = DEFAULT_DUE_AT_SESSIONS) -> bool:
    """True once enough scan runs have accrued to prompt a "should I run a full pass?" check."""
    return ar.get("sessions_since", 0) >= ar.get("due_at_sessions", due_default)


def nudge_line(ar: dict) -> str:
    """The ledger nudge (Claude's cue to ASSESS DoD #5 — not an order to run one)."""
    return (f"⚠ architecture review due: {ar.get('sessions_since', 0)} scans since "
            f"{ar.get('last', '?')} — assess whether a full architecture-quality pass is due "
            f"(DoD #5; run it + `python3 core/arch_review.py --ack`, or skip if not worth it)")


def ack(runs: dict, due_default: int = DEFAULT_DUE_AT_SESSIONS) -> dict:
    """Reset the counter after a full pass ran (resets sessions_since, stamps last). Mirrors
    health.py's _ack_counter. Returns the counter block."""
    ar = runs.setdefault("arch_review", {"due_at_sessions": due_default})
    ar["sessions_since"] = 0
    ar["last"] = date.today().isoformat()
    return ar


def _read_runs(pid: str) -> dict | None:
    p = paths.runs_path(pid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"[arch_review] {pid}/runs.json unreadable — skipping", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="architecture-review-due cadence counter (DoD #5)")
    ap.add_argument("--profile", default=None, help="one profile id (default: all profiles)")
    ap.add_argument("--ack", action="store_true",
                    help="reset the counter after running a full architecture-quality pass")
    args = ap.parse_args()

    pids = [args.profile] if args.profile else paths.list_profiles()
    if not pids:
        print("no profiles under profiles/ — nothing to report", file=sys.stderr)
        return 1

    for pid in pids:
        runs = _read_runs(pid)
        if runs is None:
            print(f"  {pid}: no runs.json yet (never scanned)")
            continue
        if args.ack:
            ar = ack(runs)
            paths.runs_path(pid).write_text(json.dumps(runs, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
            print(f"  {pid}: acked — counter reset to 0, last = {ar['last']}")
        else:
            ar = runs.get("arch_review", {"sessions_since": 0, "last": "never",
                                          "due_at_sessions": DEFAULT_DUE_AT_SESSIONS})
            flag = "  ⚠ DUE — assess a full pass (DoD #5)" if is_due(ar) else ""
            print(f"  {pid}: {ar.get('sessions_since', 0)}/{ar.get('due_at_sessions', DEFAULT_DUE_AT_SESSIONS)} "
                  f"scans since {ar.get('last', 'never')}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
