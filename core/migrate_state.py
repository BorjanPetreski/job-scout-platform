#!/usr/bin/env python3
"""migrate_state.py — copy job-scout-pm v3 state into profiles/borjan-pm/state/ verbatim.

History is the most valuable asset and is never regenerated. Idempotent and safe to
re-run: append-only .jsonl files are UNION-merged (remote-first order, same policy as
state_sync), runs.json is deep-merged, plain files are overwritten from the source
only when the source is newer content (differs).

Run it twice by design:
  1. During the Phase 1 build — so parity runs dedup against real history.
  2. At CUTOVER (step 1.12) — the legacy scanner keeps producing state until the
     schedules are re-pointed, so the final copy happens at the moment of cutover,
     immediately before freezing job-scout-pm/.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
import state_sync

LEGACY_STATE = paths.REPO_ROOT / "job-scout-pm" / "state"
TARGET_PROFILE = "borjan-pm"

JSONL = ["seen.jsonl", "fetch_evidence.jsonl"]
MERGE_RUNS = ["runs.json"]
PLAIN = ["last_run_candidates.json", "notion_sync.json"]


def migrate() -> None:
    paths.set_profile(TARGET_PROFILE)
    target = paths.state_dir()
    target.mkdir(parents=True, exist_ok=True)
    (target / "jd_cache").mkdir(exist_ok=True)

    for name in JSONL:
        src = LEGACY_STATE / name
        if not src.exists():
            print(f"  skip {name}: no legacy file")
            continue
        dst = target / name
        legacy = src.read_text(encoding="utf-8")
        local = dst.read_text(encoding="utf-8") if dst.exists() else ""
        merged = state_sync._merge_jsonl(local, legacy)  # legacy-first order, local additions kept
        dst.write_text(merged, encoding="utf-8")
        print(f"  merged {name}: {len(merged.splitlines())} lines "
              f"(legacy {len(legacy.splitlines())}, local {len(local.splitlines())})")

    for name in MERGE_RUNS:
        src = LEGACY_STATE / name
        if not src.exists():
            print(f"  skip {name}: no legacy file")
            continue
        dst = target / name
        legacy = src.read_text(encoding="utf-8")
        local = dst.read_text(encoding="utf-8") if dst.exists() else "{}"
        dst.write_text(state_sync._merge_runs(local, legacy), encoding="utf-8")
        print(f"  merged {name}")

    for name in PLAIN:
        src = LEGACY_STATE / name
        if not src.exists():
            continue
        dst = target / name
        if not dst.exists() or dst.read_text(encoding="utf-8") != src.read_text(encoding="utf-8"):
            shutil.copyfile(src, dst)
            print(f"  copied {name}")

    seen = target / "seen.jsonl"
    if seen.exists():
        n = sum(1 for line in seen.read_text(encoding="utf-8").splitlines() if line.strip())
        print(f"migration done: {n} seen.jsonl records under profiles/{TARGET_PROFILE}/state/")
    # sanity: every line must still parse
    bad = 0
    for name in JSONL:
        p = target / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
    if bad:
        raise SystemExit(f"migration produced {bad} unparseable lines — investigate before committing")


if __name__ == "__main__":
    migrate()
