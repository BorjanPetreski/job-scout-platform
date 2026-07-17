#!/usr/bin/env python3
"""writeback.py — opt-in, generic-only, staged write-back suggestions (Phase 2 §6, D6).

The learning loop that lets dogfooding improve the shared template library WITHOUT ever
leaking a person's data. With the profile's explicit consent (`writeback.consent: true`),
GENERIC template enrichments — role-generic keyword/archetype additions, e.g. "kafka" for
backend-java — are STAGED for a human curator to review into the template. Never merged
automatically (D6 option a). Never CV text, names, employers, emails, or any PII.

Staging target: `suggestions/<stream>/<subvariant>.yaml` — a top-level directory that
deliberately mirrors the template tree but sits OUTSIDE `templates/`, because the platform
validator rglobs `templates/**/*.yaml` and strict-validates every hit as a template
(unknown keys = error); a staging file under `templates/` would fail every CI run.

Two public entrypoints:
  - stage_suggestions(...) : consent-gated, PII-guarded append/upsert with provenance.
  - validate_suggestion_file(path) -> [errors] : the light schema/PII check CI runs (2.10).
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

SUGGESTIONS_DIR = paths.REPO_ROOT / "suggestions"

# A suggestion entry may only carry these keys — anything else (name/email/company/...) is a
# PII-shaped key and a hard error.
_ENTRY_KEYS = {"kind", "value", "sources", "first_seen", "last_seen", "frequency"}
_KINDS = {"keyword_core", "keyword_expanded", "archetype"}
# A generic term: letters/digits/spaces + the few tech-token punctuation marks (c++, next.js,
# .net, ci/cd, node.js). Bounded length. Deliberately narrow so a name/sentence/email can't pass.
_GENERIC_TERM = re.compile(r"^[a-z0-9][a-z0-9 .+#/&-]{0,38}$", re.IGNORECASE)
_EMAILISH = re.compile(r"[@]|https?://|\bwww\.")
_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _is_generic_term(v) -> bool:
    return isinstance(v, str) and bool(_GENERIC_TERM.match(v.strip())) and not _EMAILISH.search(v)


def suggestion_path(template_id: str) -> Path:
    """suggestions/<stream>/<subvariant>.yaml mirroring the template id."""
    return SUGGESTIONS_DIR / f"{template_id}.yaml"


def validate_suggestion_file(path: Path) -> list[str]:
    """Light CI check (2.10): parses, matches the suggestion schema, keyword/archetype keys
    only, no PII-shaped keys/values. Returns a list of named errors ([] = OK)."""
    try:
        rel = path.relative_to(paths.REPO_ROOT)
    except ValueError:
        rel = path                      # path outside the repo (e.g. a self-test temp dir)
    errors: list[str] = []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"{rel}: unreadable/invalid YAML: {exc}"]
    if not isinstance(data, dict):
        return [f"{rel}: top level must be a mapping"]
    unknown_top = set(data) - {"target_template", "suggestions"}
    if unknown_top:
        errors.append(f"{rel}: unknown top-level keys {sorted(unknown_top)} "
                      "(only target_template + suggestions allowed — no PII-shaped keys)")
    tid = data.get("target_template")
    if not isinstance(tid, str) or not tid:
        errors.append(f"{rel}: target_template missing/not a string")
    elif not (paths.TEMPLATES_DIR / f"{tid}.yaml").exists():
        errors.append(f"{rel}: target_template {tid!r} has no template under templates/")
    sugg = data.get("suggestions", [])
    if not isinstance(sugg, list):
        errors.append(f"{rel}: suggestions must be a list")
        return errors
    for i, entry in enumerate(sugg):
        loc = f"{rel}: suggestions[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{loc}: not a mapping")
            continue
        unknown = set(entry) - _ENTRY_KEYS
        if unknown:
            errors.append(f"{loc}: unknown keys {sorted(unknown)} (PII-shaped key? only "
                          f"{sorted(_ENTRY_KEYS)} allowed)")
        if entry.get("kind") not in _KINDS:
            errors.append(f"{loc}: kind must be one of {sorted(_KINDS)}, got {entry.get('kind')!r}")
        if not _is_generic_term(entry.get("value")):
            errors.append(f"{loc}: value {entry.get('value')!r} is not a short generic term "
                          "(letters/digits/tech punctuation, <=39 chars, no email/URL) — "
                          "possible PII, refused")
        srcs = entry.get("sources", [])
        if not isinstance(srcs, list) or not all(isinstance(s, str) and _KEBAB.match(s) for s in srcs):
            errors.append(f"{loc}: sources must be a list of kebab-case profile ids (no PII)")
        freq = entry.get("frequency", 1)
        if not isinstance(freq, int) or freq < 1:
            errors.append(f"{loc}: frequency must be a positive int")
        for dkey in ("first_seen", "last_seen"):
            dv = entry.get(dkey)
            if dv is not None and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(dv)):
                errors.append(f"{loc}: {dkey} must be YYYY-MM-DD")
    return errors


def stage_suggestions(template_id: str, additions: dict, source_profile_id: str,
                      consent: bool, today: str | None = None) -> dict:
    """Consent-gated, PII-guarded upsert of GENERIC enrichments into the staging file.

    additions = {"keyword_core": [...], "keyword_expanded": [...], "archetype": [...]}.
    Returns {"staged": [...], "skipped": [...], "path": str|None}. Refuses entirely without
    consent (D6) and silently drops any value that isn't a short generic term (PII guard).
    Never writes a template; only appends to suggestions/<template_id>.yaml.
    """
    if not consent:
        return {"staged": [], "skipped": [], "path": None,
                "note": "no consent recorded (writeback.consent != true) — nothing staged (D6)"}
    if not (paths.TEMPLATES_DIR / f"{template_id}.yaml").exists():
        raise SystemExit(f"[writeback] unknown target template {template_id!r}")
    today = today or date.today().isoformat()
    path = suggestion_path(template_id)
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {"target_template": template_id, "suggestions": []}
    data.setdefault("target_template", template_id)
    entries = data.setdefault("suggestions", [])
    index = {(e.get("kind"), str(e.get("value", "")).lower()): e for e in entries}

    staged, skipped = [], []
    kind_map = {"keyword_core": "keyword_core", "keyword_expanded": "keyword_expanded",
                "archetype": "archetype"}
    for akey, kind in kind_map.items():
        for raw in additions.get(akey, []) or []:
            value = str(raw).strip()
            if not _is_generic_term(value):
                skipped.append({"kind": kind, "value": value, "why": "not a generic term / possible PII"})
                continue
            key = (kind, value.lower())
            if key in index:                       # upsert: bump frequency + provenance
                e = index[key]
                if source_profile_id not in (e.get("sources") or []):
                    e.setdefault("sources", []).append(source_profile_id)
                e["frequency"] = int(e.get("frequency", 1)) + 1
                e["last_seen"] = today
            else:
                e = {"kind": kind, "value": value, "sources": [source_profile_id],
                     "first_seen": today, "last_seen": today, "frequency": 1}
                entries.append(e)
                index[key] = e
            staged.append({"kind": kind, "value": value})

    if staged:
        path.parent.mkdir(parents=True, exist_ok=True)
        header = (f"# suggestions/{template_id}.yaml — STAGED write-back suggestions (§6, D6).\n"
                  "# Generic, non-PII keyword/archetype additions surfaced by consenting profiles,\n"
                  "# awaiting a curator's review into the template. NOT auto-merged. See\n"
                  "# suggestions/README.md. Edit only via core/writeback.py or a curator merge.\n")
        path.write_text(header + yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                        encoding="utf-8")
    return {"staged": staged, "skipped": skipped, "path": str(path) if staged else None}


if __name__ == "__main__":
    import json
    import tempfile

    # Self-test: stage generic terms + PII, confirm PII is refused and the file validates.
    with tempfile.TemporaryDirectory() as tmp:
        orig = SUGGESTIONS_DIR
        SUGGESTIONS_DIR = Path(tmp) / "suggestions"  # type: ignore[assignment]
        res = stage_suggestions(
            "software-engineering/backend-java",
            {"keyword_expanded": ["kafka", "spring boot", "john@acme.com", "a really long sentence that is clearly not a keyword term"],
             "archetype": ["Event-Driven Specialist"]},
            source_profile_id="demo-backend-java", consent=True, today="2026-07-16")
        print("stage result:", json.dumps(res, indent=1))
        errs = validate_suggestion_file(Path(res["path"]))
        print("validate:", errs or "OK")
        no_consent = stage_suggestions("software-engineering/backend-java", {"archetype": ["X"]},
                                       "demo-backend-java", consent=False)
        print("no-consent:", no_consent["note"])
        SUGGESTIONS_DIR = orig  # type: ignore[assignment]
