#!/usr/bin/env python3
"""audit_skill.py — skill-tools validator replica (spec §9 acceptance criterion 7).

Checks: valid quoted frontmatter, description ≤1024 chars, kebab-case name, version
present, referenced files exist, scripts compile, valid JSON/YAML, no __pycache__/.pyc,
changelog/version match. Exit 0 = pass.
"""

from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
errors: list[str] = []
warnings: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
m = re.match(r"^---\n(.*?)\n---\n", skill, re.S)
check(bool(m), "SKILL.md has no frontmatter block")
if m:
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        errors.append(f"frontmatter is not valid YAML: {exc}")
        fm = {}
    name = fm.get("name", "")
    check(bool(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)), f"name {name!r} is not kebab-case")
    desc = fm.get("description", "")
    check(0 < len(desc) <= 1024, f"description length {len(desc)} not in 1..1024")
    version = (fm.get("metadata") or {}).get("version", "")
    check(bool(version), "metadata.version missing")
    check(bool(re.search(r'version:\s*"', m.group(1))), "version value is not quoted (colon-space trap)")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    check(f"## {version}" in changelog, f"CHANGELOG.md has no entry for version {version}")
    check(f"**{version}**" in skill.split("## Changelog")[-1], "SKILL.md changelog pointer doesn't name the current version")

for ref in re.findall(r"`(references/[\w.-]+|scripts/[\w.-]+|config\.yaml|CHANGELOG\.md)`", skill):
    check((ROOT / ref).exists(), f"SKILL.md references missing file: {ref}")

import tempfile

with tempfile.TemporaryDirectory() as tmp:
    for py in sorted((ROOT / "scripts").glob("*.py")):
        try:
            py_compile.compile(str(py), cfile=str(Path(tmp) / (py.name + "c")), doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"{py.name} does not compile: {exc}")

try:
    yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
except Exception as exc:
    errors.append(f"config.yaml invalid: {exc}")
for jf in ROOT.glob("*.json"):
    try:
        json.loads(jf.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{jf.name} invalid JSON: {exc}")

junk = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
        if p.name == "__pycache__" or p.suffix == ".pyc"]
check(not junk, f"compiled-python junk present (exclude from zip): {junk[:5]}")

for w in warnings:
    print(f"WARN: {w}")
if errors:
    print("AUDIT FAILED:")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
print("AUDIT PASSED: frontmatter, description, name, version, referenced files, "
      "script compilation, JSON/YAML validity, changelog/version match")
