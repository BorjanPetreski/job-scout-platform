#!/usr/bin/env python3
"""validate.py — the platform-wide validator (CI entrypoint). The validator lives in
core (PROJECT_PLAN.md Phase 1 scope #4): identical checks for every profile.

Validates:
  1. every core/*.py compiles
  2. catalog/platforms.yaml parses + structural rules (slug uniqueness, tier_defaults)
  3. every template under templates/ parses, resolves its extends chain, and carries
     only known keys
  4. every profile under profiles/ loads through profile_loader (strict schema,
     tier coverage, filter compilation, platform resolution) and passes scan.py's
     config validation
  5. every profile's state files are structurally valid (JSON / JSONL line integrity)
  6. skills/*/SKILL.md frontmatter (kebab-case name, description length, version)

Exit 0 = pass. Run: python3 core/validate.py
"""

from __future__ import annotations

import json
import py_compile
import re
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

errors: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


# 1 — compilation
with tempfile.TemporaryDirectory() as tmp:
    for py in sorted(paths.CORE_DIR.glob("*.py")):
        try:
            py_compile.compile(str(py), cfile=str(Path(tmp) / (py.name + "c")), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"core/{py.name} does not compile: {exc}")

# 2/3/4 — catalog, templates, profiles (loader raises SystemExit with named errors)
import profile_loader  # noqa: E402  (after compile check on purpose)

try:
    catalog = profile_loader.load_catalog()
except SystemExit as exc:
    errors.append(str(exc))
    catalog = {"platforms": []}

for tpath in sorted(paths.TEMPLATES_DIR.rglob("*.yaml")):
    tid = str(tpath.relative_to(paths.TEMPLATES_DIR)).removesuffix(".yaml")
    try:
        profile_loader.load_template(tid)
    except SystemExit as exc:
        errors.append(f"template {tid}: {exc}")

profile_ids = paths.list_profiles()
check(bool(profile_ids), "no profiles found under profiles/")
configs: dict[str, dict] = {}
for pid in profile_ids:
    try:
        cfg = profile_loader.load(pid)
        configs[pid] = cfg
        import scan

        scan.validate_config(cfg)
    except SystemExit as exc:
        errors.append(f"profile {pid}: {exc}")

# 5 — per-profile state integrity
JSON_FILES = ["runs.json", "last_run_candidates.json", "notion_sync.json", "sweep.json"]
JSONL_FILES = ["seen.jsonl", "fetch_evidence.jsonl"]
for pid in profile_ids:
    sdir = paths.PROFILES_DIR / pid / "state"
    for name in JSON_FILES:
        p = sdir / name
        if not p.exists():
            continue  # optional on fresh checkouts
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{pid}/state/{name}: invalid JSON: {exc}")
    for name in JSONL_FILES:
        p = sdir / name
        if not p.exists():
            continue
        for lineno, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"{pid}/state/{name}:{lineno}: invalid JSON line: {exc}")

# 6 — skill frontmatter
for skill_md in sorted((paths.REPO_ROOT / "skills").glob("*/SKILL.md")):
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    label = skill_md.relative_to(paths.REPO_ROOT)
    check(bool(m), f"{label}: no frontmatter block")
    if m:
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError as exc:
            errors.append(f"{label}: frontmatter not valid YAML: {exc}")
            fm = {}
        name = fm.get("name", "")
        check(bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)), f"{label}: name {name!r} not kebab-case")
        desc = fm.get("description", "")
        check(0 < len(desc) <= 1024, f"{label}: description length {len(desc)} not in 1..1024")
        check(bool((fm.get("metadata") or {}).get("version")), f"{label}: metadata.version missing")

if errors:
    print("PLATFORM VALIDATION FAILED:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
print(f"PLATFORM VALIDATION PASSED: core compiles; catalog + "
      f"{len(list(paths.TEMPLATES_DIR.rglob('*.yaml')))} templates + "
      f"{len(profile_ids)} profiles ({', '.join(profile_ids)}) resolve and validate; "
      f"state files structurally sound; skill frontmatter OK")
