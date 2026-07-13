#!/usr/bin/env python3
"""paths.py — profile-namespaced path resolution for the engine.

Every run operates on exactly ONE profile; all state lives under
profiles/<id>/state/. The active profile comes from (in order):
  1. an explicit set_profile() call (entry scripts pass --profile through here)
  2. the JOB_SCOUT_PROFILE environment variable
  3. auto-pick, if exactly one profile directory exists
Anything else is a hard error — the engine never guesses whose state to touch.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = REPO_ROOT / "core"
CATALOG_PATH = REPO_ROOT / "catalog" / "platforms.yaml"
DEFAULTS_PATH = CORE_DIR / "defaults.yaml"
TEMPLATES_DIR = REPO_ROOT / "templates"
PROFILES_DIR = REPO_ROOT / "profiles"

_active: str | None = None


def list_profiles() -> list[str]:
    if not PROFILES_DIR.is_dir():
        return []
    return sorted(p.parent.name for p in PROFILES_DIR.glob("*/profile.yaml"))


def set_profile(profile_id: str) -> str:
    global _active
    if not (PROFILES_DIR / profile_id / "profile.yaml").exists():
        raise SystemExit(f"[paths] unknown profile {profile_id!r} — expected "
                         f"profiles/{profile_id}/profile.yaml (have: {', '.join(list_profiles()) or 'none'})")
    _active = profile_id
    return profile_id


def get_profile() -> str:
    global _active
    if _active:
        return _active
    env = os.environ.get("JOB_SCOUT_PROFILE")
    if env:
        return set_profile(env)
    profiles = list_profiles()
    if len(profiles) == 1:
        return set_profile(profiles[0])
    raise SystemExit("[paths] no active profile: pass --profile <id>, set JOB_SCOUT_PROFILE, "
                     f"or keep exactly one profile (have: {', '.join(profiles) or 'none'})")


def profile_dir(profile_id: str | None = None) -> Path:
    return PROFILES_DIR / (profile_id or get_profile())


def profile_yaml(profile_id: str | None = None) -> Path:
    return profile_dir(profile_id) / "profile.yaml"


def state_dir(profile_id: str | None = None) -> Path:
    return profile_dir(profile_id) / "state"


def seen_path(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "seen.jsonl"


def evidence_path(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "fetch_evidence.jsonl"


def jd_cache_dir(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "jd_cache"


def runs_path(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "runs.json"


def candidates_path(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "last_run_candidates.json"


def sweep_state_path(profile_id: str | None = None) -> Path:
    return state_dir(profile_id) / "sweep.json"
