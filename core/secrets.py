#!/usr/bin/env python3
"""secrets.py — the secret-storage SEAM (Phase 2, D18).

Phase 2 builds the minimal seam, not the full store: a profile REFERENCES a secret by key
(e.g. the Notion token) and the value is resolved at runtime — **never committed to the
repo**. For the supervised trial the value lives in the `NOTION_TOKEN` environment variable
(the documented fallback). The end goal (Phase 4/5 app layer) is a per-user encrypted-at-rest
store keyed to the account, captured once in a one-time setup; this resolver is the interface
that store plugs into, so nothing here precludes it.

Resolution order (first hit wins):
  1. explicit override passed by the caller (e.g. a --token CLI arg)
  2. the `NOTION_TOKEN` environment variable (trial fallback)
  3. an encrypted per-user store (NOT built in Phase 2 — the seam returns None here)

Design note: real encryption (Fernet/age/OS keychain) plugs in at step 3 behind
`_resolve_from_store`. It is deliberately a stub in Phase 2 so the trial runs on the env
var and the repo never holds a token.
"""

from __future__ import annotations

import os

NOTION_TOKEN_KEY = "notion_token"


def _resolve_from_store(key: str, profile_id: str | None) -> str | None:
    """Seam for the future encrypted per-user store (D18). Not implemented in Phase 2 —
    the trial uses the env fallback. Returns None so callers fall through cleanly."""
    return None


def resolve_secret(key: str, *, profile_id: str | None = None, override: str | None = None,
                   env_var: str | None = None) -> str | None:
    if override:
        return override
    env_name = env_var or {NOTION_TOKEN_KEY: "NOTION_TOKEN"}.get(key, key.upper())
    val = os.environ.get(env_name)
    if val:
        return val
    return _resolve_from_store(key, profile_id)


def resolve_notion_token(override: str | None = None, profile_id: str | None = None) -> str | None:
    """The Notion integration token for provisioning + sync. Env (`NOTION_TOKEN`) is the
    trial fallback; the value never enters the repo (the profile references it by key)."""
    return resolve_secret(NOTION_TOKEN_KEY, profile_id=profile_id, override=override,
                          env_var="NOTION_TOKEN")
