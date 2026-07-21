#!/usr/bin/env python3
"""Offline simulation — the twin-row dedup fix (PROJECT_PLAN §3x, 2026-07-20).

The bug: a posting resolved on an earlier scan can resurface as a fresh unsynced record; the
sync CREATE path blindly created a SECOND Passed/Seen row for the same Job URL (Vazco/TT MS: a
mechanical `Filtered Out` twin next to the user's `User Declined`). `reconcile` then applied
BOTH rows in Notion row-ORDER (last write wins), so which resolution stuck locally was
nondeterministic — a user's decline could be clobbered by a machine drop.

The fix (two halves, both exercised here against a mocked Notion, no token / no network):
  1. sync_scan CREATE path is now idempotent-by-URL: find first, never duplicate; leave a
     resolved row untouched, refresh a still-live row in place.
  2. reconcile ranks reasons per URL (user resolution > mechanical) so it's deterministic even
     when twins already exist — order can't decide the winner.

Run: python3 sims/twin_row_dedup.py    (exit 0 = fix proven)

Dev/acceptance harness — NOT imported by the engine; writes only to a throwaway temp dir.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import dedup
import notion_sync as ns

PS_DS = "p" * 32
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
        self.text = ""

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeNotion:
    """A Passed/Seen Log that can hold MORE THAN ONE row per Job URL — the whole point of the
    bug. Routes the exact REST calls find_page_by_url / _current_reason / reconcile / the
    in-place refresh PATCH make."""

    def __init__(self, rows: list[tuple[str, str]]):   # (url, reason), order-significant
        self.rows = [{"id": f"pg{i}", "url": u, "reason": r} for i, (u, r) in enumerate(rows)]
        self.creates: list[str] = []       # not expected to be hit (typed_create_page is stubbed)
        self.patches: list[tuple[str, str]] = []

    def _by_id(self, pid: str) -> dict | None:
        return next((r for r in self.rows if r["id"] == pid), None)

    def req(self, method: str, url: str, **kw) -> _Resp:
        if method == "POST" and url == f"{API}/data_sources/{PS_DS}/query":
            body = kw.get("json") or {}
            flt = body.get("filter")
            if flt:  # find_page_by_url — first row matching the URL (real Notion returns all; [0] used)
                want = flt["url"]["equals"]
                hits = [{"id": r["id"]} for r in self.rows if r["url"] == want]
                return _Resp(200, {"results": hits, "has_more": False})
            # reconcile full scan — every row with its url + reason
            return _Resp(200, {"results": [
                {"properties": {"Job URL": {"url": r["url"]},
                                "Reason Passed": {"select": {"name": r["reason"]}}}}
                for r in self.rows], "has_more": False})
        if method == "GET" and url.startswith(f"{API}/pages/"):
            row = self._by_id(url.rsplit("/", 1)[-1])
            # _patch_verified (2026-07-21) re-fetches and compares EVERY property it PATCHed,
            # not just Reason Passed — the fake page must actually store+echo back whatever
            # was last written, same as real Notion, or the post-write assertion (correctly)
            # flags a mismatch that was really just an under-modeled fake.
            props = dict(row.get("properties") or {"Reason Passed": {"select": {"name": row["reason"]}}})
            return _Resp(200, {"properties": props})
        if method == "PATCH" and url.startswith(f"{API}/pages/"):
            pid = url.rsplit("/", 1)[-1]
            row = self._by_id(pid)
            sent = kw["json"]["properties"]
            row.setdefault("properties", {"Reason Passed": {"select": {"name": row["reason"]}}}).update(sent)
            new = (sent.get("Reason Passed") or {}).get("select", {}).get("name")
            if new:
                row["reason"] = new
            self.patches.append((pid, new))
            return _Resp(200, {})
        raise AssertionError(f"unexpected Notion call: {method} {url}")


_ORIG_LOAD = dedup.load_seen
_ORIG_UPDATE = dedup.update


def _bind(seen_path: Path) -> None:
    dedup.load_seen = lambda path=None: _ORIG_LOAD(path or seen_path)
    dedup.update = lambda k, fields, path=None: _ORIG_UPDATE(k, fields, path or seen_path)


# --------------------------------------------------------------------------- reconcile ranking
def test_reconcile_ranking(order_label: str, rows: list[tuple[str, str]]) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="twinrow-recon-"))
    seen_path = tmp / "seen.jsonl"
    U = "https://boards.example.com/jobs/twin-role"
    dedup.append({"url": U, "company": "TwinCo", "role": "PM", "status": "shortlisted",
                  "synced_to_notion": True}, seen_path)
    _bind(seen_path)
    fake = FakeNotion(rows)
    ns._req = fake.req
    os.environ["NOTION_TOKEN"] = "sim-token"
    cfg = {"notion": {"passed_seen": {"data_source_id": PS_DS}}}
    res = ns.reconcile_resolutions_from_passed_seen(cfg)
    rec = dedup.load_seen()["by_url"].get(dedup.norm_url(U))
    print(f"\n[reconcile ranking — {order_label}] rows={[r[1] for r in rows]}")
    ok(res["resolved"] == 1, f"resolved exactly 1 local record ({res['resolved']})")
    ok(rec.get("status") == "passed" and rec.get("reason") == "User Declined",
       f"User Declined WINS over the Filtered Out twin -> local {rec.get('status')}/{rec.get('reason')}")


# --------------------------------------------------------------------------- create idempotency
def test_create_idempotency() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="twinrow-create-"))
    seen_path = tmp / "seen.jsonl"
    U_RESOLVED = "https://boards.example.com/jobs/already-declined"   # PS row already User Declined
    U_LIVE = "https://boards.example.com/jobs/still-new"              # PS row still New — Unreviewed
    U_FRESH = "https://boards.example.com/jobs/brand-new"             # no PS row yet
    # three fresh unsynced shortlist records the scan just produced
    for u, role in [(U_RESOLVED, "Resurfaced PM"), (U_LIVE, "Live PM"), (U_FRESH, "New PM")]:
        dedup.append({"url": u, "company": "Co", "role": role, "platform": "JustJoin.it",
                      "status": "shortlisted", "reason": "New — Unreviewed",
                      "synced_to_notion": False}, seen_path)
    _bind(seen_path)
    fake = FakeNotion([(U_RESOLVED, "User Declined"), (U_LIVE, "New — Unreviewed")])
    ns._req = fake.req
    os.environ["NOTION_TOKEN"] = "sim-token"

    created: list[str] = []
    ns._cfg = lambda: {"profile_id": "sim", "notion": {"dry_run": False,
                       "passed_seen": {"data_source_id": PS_DS},
                       "pinned_pages": {"job_scout_runs": "x"}}}
    ns.ensure_select_options = lambda *a, **k: None
    ns._platform_option = lambda *a, **k: "X"
    ns.build_passed_seen_properties = lambda rec, cfg: {
        "Reason Passed": {"select": {"name": rec.get("reason") or "New — Unreviewed"}}}
    ns.typed_create_page = lambda ds, props, body=None: created.append(props["Reason Passed"]["select"]["name"]) or "newpg"
    ns.paths.state_dir = lambda: tmp

    ns.sync_scan(dry_run=False)

    print("\n[create idempotency]")
    ok(len(created) == 1, f"exactly ONE create — only the brand-new URL, never a URL that "
       f"already has a row ({len(created)} creates)")
    ok(not any(p for p in fake.patches if fake._by_id(p[0]) and fake._by_id(p[0])["url"] == U_RESOLVED),
       "already-RESOLVED row left untouched (no clobber)")
    live_row = next(r for r in fake.rows if r["url"] == U_LIVE)
    ok((live_row["id"], "New — Unreviewed") in fake.patches or any(p[0] == live_row["id"] for p in fake.patches),
       "still-LIVE row refreshed in place (PATCH, not duplicate)")
    by_url = dedup.load_seen()["by_url"]
    ok(all(by_url[dedup.norm_url(u)].get("synced_to_notion") for u in (U_RESOLVED, U_LIVE)),
       "both existing-row records marked synced locally")
    # U_FRESH has no existing row -> the create path (stubbed) SHOULD fire once for it
    ok(by_url[dedup.norm_url(U_FRESH)].get("synced_to_notion") is True,
       "brand-new URL still synced (created normally)")


def main() -> int:
    # both Notion row orders must give the same winner — proves order-independence
    U = "https://boards.example.com/jobs/twin-role"
    test_reconcile_ranking("Filtered Out first", [(U, "Filtered Out"), (U, "User Declined")])
    test_reconcile_ranking("User Declined first", [(U, "User Declined"), (U, "Filtered Out")])
    test_create_idempotency()
    print("\n" + ("TWIN-ROW FIX PROVEN — all checks passed" if not _fails
                  else f"FAILED: {len(_fails)} check(s): {_fails}"))
    return 1 if _fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
