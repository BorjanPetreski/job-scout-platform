#!/usr/bin/env python3
"""Offline simulation — the PATCH post-write assertion fix (2026-07-21 architecture audit).

The bug: typed_create_page (the CREATE path) re-fetches and asserts a write actually landed
before counting it as synced ("silently-accepted ≠ verified" — its own docstring). All THREE
PATCH paths (sweep updates, the sync-scan in-place refresh, the applied-flip) trusted a bare
200 status with no re-fetch — a PATCH that returns 200 but Notion silently drops/ignores a
property (schema drift, a renamed/stale select option) would get marked `synced_to_notion:
True` and never retried, with no error anywhere.

The fix: _patch_verified() (core/notion_sync.py) generalizes typed_create_page's doctrine to
any PATCH — re-fetches and compares each sent select's name / rich_text's joined text against
what actually landed, raising on mismatch. This proves it against a mocked Notion (no token,
no network): a normal PATCH passes silently; a PATCH Notion "accepts" (200) but doesn't
actually apply (simulating a stale select option) is CAUGHT, not silently trusted.

Run: python3 sims/patch_write_verification.py    (exit 0 = fix proven)

Dev/acceptance harness — NOT imported by the engine.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import notion_sync as ns

API = ns.API
_fails: list[str] = []


def ok(cond: bool, label: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        _fails.append(label)


class _Resp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeNotion:
    """A page whose stored properties may diverge from what a PATCH claims to have set —
    the exact shape of the bug (Notion returns 200, but the value didn't actually change)."""

    def __init__(self):
        self.page = {"properties": {
            "Reason Passed": {"select": {"name": "New — Unreviewed"}},
            "Notes": {"rich_text": [{"plain_text": "original note"}]},
        }}
        self.apply_patch = True  # flip False to simulate a PATCH that 200s but doesn't stick

    def req(self, method: str, url: str, **kw):
        if method == "PATCH":
            if self.apply_patch:
                self.page["properties"].update(kw.get("json", {}).get("properties", {}))
            return _Resp(200)
        if method == "GET":
            return _Resp(200, self.page)
        raise AssertionError(f"unexpected {method} {url}")


def main() -> int:
    print("=" * 70)
    print("SIM: PATCH post-write verification (2026-07-21)")
    print("=" * 70)

    fake = FakeNotion()
    ns._req = fake.req

    print("\n[normal PATCH — value actually lands]")
    try:
        ns._patch_verified("pg1", {"Reason Passed": {"select": {"name": "User Declined"}}},
                           "test PATCH")
        ok(True, "verified PATCH with a real value change does not raise")
    except RuntimeError as exc:
        ok(False, f"unexpected raise: {exc}")

    print("\n[silently-dropped PATCH — Notion 200s but the value never actually changed]")
    fake.apply_patch = False
    try:
        ns._patch_verified("pg1", {"Reason Passed": {"select": {"name": "Stale/Expired"}}},
                           "test PATCH")
        ok(False, "should have raised — a 200 that didn't actually apply must fail loud")
    except RuntimeError as exc:
        ok("post-write assertion FAILED" in str(exc), f"correctly caught the silent drop: {exc}")

    print("\n[rich_text field, same drop-detection]")
    fake.apply_patch = False
    try:
        ns._patch_verified("pg1", {"Notes": {"rich_text": [{"type": "text", "text": {"content": "new note"}}]}},
                           "test PATCH")
        ok(False, "should have raised for a silently-dropped rich_text update too")
    except RuntimeError as exc:
        ok("Notes" in str(exc), f"correctly caught the rich_text drop: {exc}")

    print("\n[empty properties — nothing to verify, no false failure]")
    try:
        ns._patch_verified("pg1", {}, "no-op PATCH")
        ok(True, "an empty properties dict is a legitimate no-op, never raises")
    except RuntimeError as exc:
        ok(False, f"unexpected raise on empty properties: {exc}")

    print()
    if _fails:
        print(f"SIM FAILED — {len(_fails)} check(s): {_fails}")
        return 1
    print("PATCH VERIFICATION FIX PROVEN — all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
