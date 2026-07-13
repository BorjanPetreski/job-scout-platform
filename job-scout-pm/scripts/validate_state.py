#!/usr/bin/env python3
"""validate_state.py — structural integrity check for state/ (CI gate).

Every scan-state PR (state_sync.py push) modifies these files directly, so a
malformed write here is exactly the kind of regression CI should catch before
merge. Checks JSON validity only (schema varies legitimately by record type,
e.g. shortlisted vs dropped) — not semantic/field validation. Exit 0 = pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state"

JSON_FILES = ["runs.json", "last_run_candidates.json", "notion_sync.json"]
JSONL_FILES = ["seen.jsonl", "fetch_evidence.jsonl"]

errors: list[str] = []

for name in JSON_FILES:
    p = STATE / name
    if not p.exists():
        continue  # optional (e.g. notion_sync.json absent on a fresh checkout)
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{name}: invalid JSON: {exc}")

for name in JSONL_FILES:
    p = STATE / name
    if not p.exists():
        continue
    for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{name}:{lineno}: invalid JSON line: {exc}")

if errors:
    print("STATE VALIDATION FAILED:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
print(f"STATE VALIDATION PASSED: {', '.join(JSON_FILES)} valid JSON; "
      f"{', '.join(JSONL_FILES)} valid line-delimited JSON")
