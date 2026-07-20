#!/usr/bin/env python3
"""dedup.py — seen-log read/write/match (engine core; profile-namespaced since 4.0).

profiles/<id>/state/seen.jsonl is the dedup source of truth (append-only, one JSON
object per line). Update semantics: appending a record whose url/key matches an earlier
one SUPERSEDES it — readers take the LAST occurrence. This keeps the file append-only
while satisfying the 2.6.0 rule that a later scan resolving an `unverified_blocked`
lead updates its reason instead of creating a duplicate.

Matching order (2.3.0 rule, invariant #4):
  1. exact Job URL match
  2. normalized 3-part key company|role_title|loc_or_domain
Company+title alone is NEVER a match (Andersen lesson: two distinct Delivery Manager
reqs, different client/city — differing locdom means DISTINCT opportunity).

Statuses: dropped | shortlisted | applied | passed | unverified_blocked
`unverified_blocked` is first-class (SysMap lesson): blocked leads are logged
immediately, even without resolution, so they never cost a repeat fetch-and-block
cycle. Never log roles still pending the user's own call.

Profiles NEVER share dedup history — the same URL can legitimately be a candidate for
two different profiles. All entry points resolve the active profile via core/paths.py.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

LEGAL_SUFFIXES = re.compile(
    r"\b(gmbh|ltd|inc|llc|s\.?a\.?|s\.?r\.?l\.?|d\.?o\.?o\.?|b\.?v\.?|a\.?g\.?|"
    # Polish forms (JustJoin.it etc.): 'Sp. z o.o.' (LLC) incl. the combined
    # 'Sp. z o.o. Sp. k.' via the stacked-strip loop, plus 'Sp. k.'/'Sp. j.'.
    r"sp\.?\s*z\s*o\.?\s*o\.?|sp\.?\s*[kj]\.?|"
    r"corp(oration)?|co|plc|limited|group|holdings?)\.?$",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def norm_company(company: str) -> str:
    c = _norm(company)
    prev = None
    while prev != c:  # strip stacked suffixes ("Foo Group Ltd")
        prev = c
        c = LEGAL_SUFFIXES.sub("", c).strip(" ,.")
    return c


def norm_url(url: str) -> str:
    u = (url or "").strip().lower()
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)  # tracking params never distinguish postings
    return u.rstrip("/")  # drop the trailing slash AFTER the query, so '/job/?x' == '/job'


def make_key(company: str, role: str, locdom: str) -> str:
    return f"{norm_company(company)}|{_norm(role)}|{_norm(locdom)}"


def role_family(role: str) -> str:
    """Role title with a trailing location/scope qualifier stripped, e.g.
    'Delivery Manager - Belgrade' / 'Delivery Manager (Poland)' -> 'delivery manager'.
    Used for the location-agnostic country-clone cross-check: two applied reqs that
    share a company + role_family but differ only in location are the same opportunity
    (Andersen Belgrade/Skopje/Warszawa lesson — dedup on the 3-part key treats every
    country tag as distinct BY DESIGN, which is the wrong call once 2+ have converted)."""
    return re.split(r"\s[-–—|(/]|,", _norm(role), maxsplit=1)[0].strip()


def load_seen(path: Path | None = None) -> dict:
    """Return {'by_url': {norm_url: rec}, 'by_key': {key: rec}} — last record wins."""
    path = path or paths.seen_path()
    by_url: dict[str, dict] = {}
    by_key: dict[str, dict] = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[dedup] WARNING: bad JSON at seen.jsonl:{lineno}", file=sys.stderr)
                    continue
                if rec.get("url"):
                    by_url[norm_url(rec["url"])] = rec
                if rec.get("key"):
                    by_key[rec["key"]] = rec
    return {"by_url": by_url, "by_key": by_key}


def match(candidate: dict, seen: dict) -> dict | None:
    """Return the seen record this candidate duplicates, else None.

    candidate needs: url, company, role, locdom (any may be empty strings).
    """
    if candidate.get("url"):
        hit = seen["by_url"].get(norm_url(candidate["url"]))
        if hit:
            return hit
    if not norm_company(candidate.get("company", "")):
        return None  # company-less discovery rows would form degenerate keys ("|title|")
                     # that cross-match unrelated postings — URL match only for those
    key = make_key(candidate.get("company", ""), candidate.get("role", ""), candidate.get("locdom", ""))
    return seen["by_key"].get(key)


def append(rec: dict, path: Path | None = None) -> dict:
    """Append one record immediately (real-time logging intent, invariant #9).

    Fills key/first_seen defaults. Returns the record as written.
    """
    path = path or paths.seen_path()
    rec = dict(rec)
    rec.setdefault("key", make_key(rec.get("company", ""), rec.get("role", ""), rec.get("locdom", "")))
    rec.setdefault("first_seen", date.today().isoformat())
    rec.setdefault("synced_to_notion", False)
    if rec.get("status") not in {"dropped", "shortlisted", "applied", "passed", "unverified_blocked"}:
        raise ValueError(f"invalid status: {rec.get('status')!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def update(url_or_key: str, fields: dict, path: Path | None = None) -> dict | None:
    """Supersede an existing record (e.g. unverified_blocked -> resolved reason).

    Appends a merged record; last-wins semantics make it the current one.
    """
    path = path or paths.seen_path()
    seen = load_seen(path)
    rec = seen["by_url"].get(norm_url(url_or_key)) or seen["by_key"].get(url_or_key)
    if rec is None:
        return None
    merged = {**rec, **fields}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(merged, ensure_ascii=False) + "\n")
    return merged


def current_records(path: Path | None = None) -> list[dict]:
    """Deduplicated last-wins view of every record."""
    seen = load_seen(path)
    current: dict[int, dict] = {}
    for rec in list(seen["by_url"].values()) + list(seen["by_key"].values()):
        current[id(rec)] = rec
    return list(current.values())


def unsynced(path: Path | None = None) -> list[dict]:
    """Current (last-wins) records not yet pushed to Notion."""
    return [r for r in current_records(path) if not r.get("synced_to_notion")]


def company_index(path: Path | None = None) -> dict[str, list[dict]]:
    """norm_company -> list of current (last-wins) records for that company.

    One pass so scan.py can, per survivor, surface prior reqs from the same company
    ("Andersen also has: DM-Skopje [Applied], DM-Warszawa [Applied]") without asking
    the user each time, and detect applied-variant saturation (the location-agnostic
    country-clone check). Company-less rows are skipped — they'd bucket together
    meaninglessly.
    """
    idx: dict[str, list[dict]] = {}
    for rec in current_records(path):
        c = norm_company(rec.get("company", ""))
        if c:
            idx.setdefault(c, []).append(rec)
    return idx


if __name__ == "__main__":
    seen = load_seen()
    total_urls, total_keys = len(seen["by_url"]), len(seen["by_key"])
    print(f"[{paths.get_profile()}] seen.jsonl: {total_urls} unique URLs, {total_keys} unique keys")
    if len(sys.argv) == 4:  # dedup.py <company> <role> <locdom> — manual check
        hit = match({"url": "", "company": sys.argv[1], "role": sys.argv[2], "locdom": sys.argv[3]}, seen)
        print(f"match: {json.dumps(hit, ensure_ascii=False) if hit else 'none'}")
