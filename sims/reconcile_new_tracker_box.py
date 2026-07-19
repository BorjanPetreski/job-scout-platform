#!/usr/bin/env python3
"""Offline simulation — the one un-live-tested 3a box (PHASE_3A_ACCEPTANCE §4):

    companion drafts + creates a NEW Applications Tracker row
      → the NEXT scan's reconcile READS the Tracker and back-fills THAT row's
        seen.jsonl record to `applied` (D8 cross-process dedup handoff)
      → and (tasks #8/#11) flips the lingering Passed/Seen shortlist row
        `New — Unreviewed` → `User Applied Elsewhere`.

Why a sim: the live acceptance (3a.7) proved back-fill against an already-existing
Tracker row (OSF), but never against a row the companion FRESHLY creates on a first
real apply. This drives the REAL `reconcile_applied_from_tracker` + the REAL dedup
layer against a mocked Notion (a fake Tracker + a fake Passed/Seen Log), so the whole
box is exercised end-to-end with no token and no network. It asserts and self-reports.

Run: python3 sims/reconcile_new_tracker_box.py   (exit 0 = box proven)

This is a dev/acceptance harness — it is NOT imported by the engine and writes only to
a throwaway temp dir. No profile state is touched.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
import dedup
import notion_sync as ns

TRACKER_DS = "t" * 32
PASSED_SEEN_DS = "p" * 32
API = ns.API

# URLs in play
U_NEW = "https://boards.example.com/jobs/new-delivery-lead"   # companion just applied → NEW Tracker row
U_CTRL = "https://boards.example.com/jobs/still-open-pm"       # unrelated shortlist row — must stay untouched
U_PREV = "https://boards.example.com/jobs/prev-applied"        # applied earlier, PS row already resolved
U_MANUAL = "https://manual.example.com/jobs/typed-by-hand"     # Tracker-only row the scanner never saw

_fails: list[str] = []


def ok(cond: bool, label: str) -> None:
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        _fails.append(label)


# --------------------------------------------------------------------------- Notion mock
class _Resp:
    def __init__(self, status: int, payload: dict | None = None):
        self.status_code = status
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


class FakeNotion:
    """A fake Tracker (list of Job URLs) + a fake Passed/Seen Log (url → row).
    Routes the exact REST calls reconcile/find_page_by_url/_current_reason/flip make."""

    def __init__(self, tracker_urls: list[str], passed_seen: dict[str, str]):
        self.tracker_urls = tracker_urls
        # passed_seen: url → current "Reason Passed". Opaque, slash-free page ids (like real
        # Notion) so _current_reason's GET /pages/{id} parse is faithful.
        self.page_by_url = {u: f"pg{i}" for i, u in enumerate(passed_seen)}
        self.reason_by_page = {self.page_by_url[u]: r for u, r in passed_seen.items()}
        self.patches: list[tuple[str, str]] = []  # (page_id, new_reason) — write audit trail

    def req(self, method: str, url: str, **kw) -> _Resp:
        if method == "POST" and url == f"{API}/data_sources/{TRACKER_DS}/query":
            return _Resp(200, {"results": [{"properties": {"Job URL": {"url": u}}}
                                           for u in self.tracker_urls], "has_more": False})
        if method == "POST" and url == f"{API}/data_sources/{PASSED_SEEN_DS}/query":
            want = kw["json"]["filter"]["url"]["equals"]
            pid = self.page_by_url.get(want)
            return _Resp(200, {"results": [{"id": pid}] if pid else []})
        if method == "GET" and url.startswith(f"{API}/pages/"):
            pid = url.rsplit("/", 1)[-1]
            reason = self.reason_by_page.get(pid)
            return _Resp(200, {"properties": {"Reason Passed": {"select": {"name": reason}}}})
        if method == "PATCH" and url.startswith(f"{API}/pages/"):
            pid = url.rsplit("/", 1)[-1]
            new = kw["json"]["properties"]["Reason Passed"]["select"]["name"]
            self.reason_by_page[pid] = new
            self.patches.append((pid, new))
            return _Resp(200, {})
        raise AssertionError(f"unexpected Notion call: {method} {url}")


# --------------------------------------------------------------------------- harness
def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="reconcile-sim-"))
    seen_path = tmp / "seen.jsonl"

    # Seed seen.jsonl: the just-applied NEW role is still `shortlisted` locally (the companion
    # created the Tracker row on the claude.ai side; the scanner hasn't reconciled yet); a control
    # shortlist row; and a prior application already reconciled + resolved.
    dedup.append({"url": U_NEW, "company": "NewCo", "role": "Delivery Lead",
                  "status": "shortlisted", "synced_to_notion": True}, seen_path)
    dedup.append({"url": U_CTRL, "company": "OtherCo", "role": "Senior PM",
                  "status": "shortlisted", "synced_to_notion": True}, seen_path)
    dedup.append({"url": U_PREV, "company": "PrevCo", "role": "Program Manager",
                  "status": "applied", "reason": "User Applied Elsewhere",
                  "synced_to_notion": True}, seen_path)

    # Bind the module-level dedup calls reconcile makes (no path arg) to the temp file, so the
    # sim drives the REAL reconcile/dedup logic without touching any profile's seen.jsonl.
    dedup.load_seen = lambda path=None: _ORIG_LOAD(path or seen_path)
    dedup.update = lambda k, fields, path=None: _ORIG_UPDATE(k, fields, path or seen_path)

    # Notion: Tracker has the NEW row (companion-created), the prior applied row, and a
    # manual-entry row the scanner never saw. Passed/Seen Log has the two shortlist rows still
    # `New — Unreviewed` + the prior row already `User Applied Elsewhere`.
    fake = FakeNotion(
        tracker_urls=[U_NEW, U_PREV, U_MANUAL],
        passed_seen={U_NEW: "New — Unreviewed",
                     U_CTRL: "New — Unreviewed",
                     U_PREV: "User Applied Elsewhere"},
    )
    ns._req = fake.req
    cfg = {"notion": {"tracker": {"data_source_id": TRACKER_DS},
                      "passed_seen": {"data_source_id": PASSED_SEEN_DS}}}

    # --- token-gated: no token → honest skip, zero writes -------------------------------------
    print("\n[0] Token gate (no NOTION_TOKEN):")
    os.environ.pop("NOTION_TOKEN", None)
    r0 = ns.reconcile_applied_from_tracker(cfg)
    ok(r0["tokenless"] is True, "tokenless run reports tokenless=True")
    ok(not fake.patches, "tokenless run writes nothing to Notion")

    os.environ["NOTION_TOKEN"] = "sim-token"

    # --- run 1: the box ------------------------------------------------------------------------
    print("\n[1] First scan after the companion created the NEW Tracker row:")
    r1 = ns.reconcile_applied_from_tracker(cfg)
    ok(r1["tracker_rows"] == 3, f"read 3 Tracker rows (got {r1['tracker_rows']})")
    ok(r1["backfilled"] == 1, f"NEW role back-filled to applied (backfilled={r1['backfilled']})")
    ok(r1["already"] == 1, f"prior-applied row idempotent-skipped (already={r1['already']})")
    ok(r1["unmatched"] == 1, f"manual-entry Tracker row unmatched (unmatched={r1['unmatched']})")
    ok(r1["passed_seen_flipped"] == 1, f"one shortlist row flipped (flipped={r1['passed_seen_flipped']})")

    seen = _ORIG_LOAD(seen_path)
    new_rec = seen["by_url"][dedup.norm_url(U_NEW)]
    ok(new_rec["status"] == "applied", "NEW role seen.jsonl status → applied")
    ok(new_rec.get("reason") == "User Applied Elsewhere", "NEW role reason → User Applied Elsewhere")
    ok(fake.reason_by_page[fake.page_by_url[U_NEW]] == "User Applied Elsewhere",
       "NEW role Passed/Seen row flipped out of New — Unreviewed")

    # control invariants
    ctrl = seen["by_url"][dedup.norm_url(U_CTRL)]
    ok(ctrl["status"] == "shortlisted", "unrelated shortlist row untouched (still shortlisted)")
    ok(fake.reason_by_page[fake.page_by_url[U_CTRL]] == "New — Unreviewed",
       "unrelated Passed/Seen row untouched (never in the Tracker)")
    ok(fake.page_by_url[U_PREV] not in {p for p, _ in fake.patches},
       "already-resolved row NOT re-patched (read-before-write guard held)")

    # --- dedup proof: the applied role will not re-shortlist on the next scan -------------------
    print("\n[2] Dedup handoff — the applied role is now suppressed:")
    hit = dedup.match({"url": U_NEW, "company": "NewCo", "role": "Delivery Lead"}, seen)
    ok(hit is not None and hit["status"] == "applied",
       "a re-discovery of the NEW role dedups against the applied record (no re-shortlist)")

    # --- run 2: idempotency --------------------------------------------------------------------
    print("\n[3] Re-run (idempotency — a second scan changes nothing):")
    patches_before = len(fake.patches)
    lines_before = seen_path.read_text().count("\n")
    r2 = ns.reconcile_applied_from_tracker(cfg)
    ok(r2["backfilled"] == 0, f"no re-backfill (backfilled={r2['backfilled']})")
    ok(r2["passed_seen_flipped"] == 0, f"no re-flip (flipped={r2['passed_seen_flipped']})")
    ok(len(fake.patches) == patches_before, "no new Notion writes on re-run")
    ok(seen_path.read_text().count("\n") == lines_before,
       "seen.jsonl not grown by redundant applied appends")

    print("\n" + ("PASS — the NEW-Tracker-create → back-fill box is proven end-to-end."
                  if not _fails else f"FAIL — {len(_fails)} assertion(s) failed:"))
    for f in _fails:
        print(f"  - {f}")
    return 1 if _fails else 0


# capture the real dedup fns before we re-point them
_ORIG_LOAD = dedup.load_seen
_ORIG_UPDATE = dedup.update

if __name__ == "__main__":
    raise SystemExit(main())
