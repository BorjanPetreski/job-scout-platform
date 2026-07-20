#!/usr/bin/env python3
"""fetch_boards.py — per-platform fetchers: API-first, deterministic HTML parse,
headless render, mirror pipeline. No free-text summarization anywhere (delta row 10).

Every fetcher returns either candidates or a structured source_down marker —
NO silent empty results. Fallback chain on failure: api/direct → headless render
→ mirrors → unresolved leads emitted as `unverified_blocked` candidates for
immediate seen.jsonl logging (SysMap lesson).

Profile-agnostic since 4.0: dispatch and harvest specs are keyed by CATALOG SLUG, and
everything stream-specific (search URLs, JustJoin.it category id, Himalayas pre-filter
phrases) arrives resolved on the platform entry (urls/api/params) by profile_loader.

Endpoint state as verified live 2026-07-11 (endpoints drift — see BUILD findings):
  Remotive api/remote-jobs        → REGRESSED: 41-job stub, params ignored;
                                    anonymous category HTML has masked companies and NO
                                    per-job links (headless render identical). Platform
                                    marked degraded; per-job pages remain public.
  Working Nomads exposed_jobs     → 33-job sample, category param ignored (still useful)
  Remote OK /api                  → full list, first element is a legal notice
  JustJoin.it                     → /v2/user-panel/offers/by-cursor, categories[]={id},
                                    perPage caps at 20, `from` cursor pages (PM id 15)
  Greenhouse boards-api           → works (content=true)
  Lever api.lever.co/v0/postings  → works
  Workable apply.workable.com/api/v3/accounts/{slug}/jobs (POST) → works, nextPage token
  Pinpoint {board}.pinpointhq.com/postings.json → works
  Ashby posting-api               → works generally; Deel DISABLED it (board hidden) —
                                    Deel jobs parsed from careers-page embedded JSON instead
  WWR category RSS                → 301s to nothing; /remote-jobs.rss (all jobs) works and
                                    doubles as the cross-category pass
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_host_last: dict[str, float] = {}
_host_lock = threading.Lock()


def _polite(url: str, min_delay: float = 1.0) -> None:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    with _host_lock:
        wait = min_delay - (time.time() - _host_last.get(host, 0.0))
        _host_last[host] = time.time() + max(wait, 0)
    if wait > 0:  # sleep OUTSIDE the lock — other hosts must not stall behind it
        time.sleep(wait)


# Self-healing (HEALTH_MONITORING.md Layer 1.5): retry-with-backoff on *transient*
# failures only — connection resets, timeouts, and 429/5xx (a busy or flaky server).
# Bounded and polite (each retry re-enters _polite), so it recovers a blip without
# reading as scraping. A 4xx other than 429 is NOT transient (the board answered — a
# real endpoint/auth/selector problem for Layer 2), so we never retry those.
_TRANSIENT_EXC = (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
_RETRY_STATUS = {429, 500, 502, 503, 504}


def _get(url: str, timeout: int = 25, retries: int = 2, **kw) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        _polite(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, **kw)
        except _TRANSIENT_EXC as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))  # 2s, 4s — bounded backoff
                continue
            raise
        if r.status_code in _RETRY_STATUS and attempt < retries:
            time.sleep(2 * (attempt + 1))
            continue
        return r
    raise last_exc  # unreachable, but keeps the type checker honest


def _cand(title, company, loc, url, platform, posted_at=None, salary=None, jd=None) -> dict:
    return {
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "loc": (loc or "").strip(),
        "url": url,
        "platform": platform,
        "posted_at": posted_at,
        "salary": salary,
        "jd_text": jd,  # full JD text when the enumeration already carries it
    }


# `http_ok` — did the board actually answer (HTTP 200 with a real body)? This is the
# axis health.py needs to separate the SILENT SELECTOR BREAK from a plain outage:
#   source_down=True,  http_ok=False → couldn't reach it (DOWN_STREAK territory)
#   source_down=True,  http_ok=True  → reached 200 but parsed 0 rows (SELECTOR_SUSPECT)
#   source_down=False                → produced candidates / clean API response
# `healed` — human-readable notes on what Layer-1.5 self-healing recovered this fetch
# ("recovered via headless", …), so a heal is always REPORTED, never a silent paper-over.
def _ok(platform: str, candidates: list[dict], note: str = "",
        http_ok: bool = True, healed: list[str] | None = None) -> dict:
    return {"platform": platform, "candidates": candidates, "source_down": False,
            "note": note, "http_ok": http_ok, "healed": healed or []}


def _down(platform: str, note: str, http_ok: bool = False,
          healed: list[str] | None = None) -> dict:
    return {"platform": platform, "candidates": [], "source_down": True,
            "note": note, "http_ok": http_ok, "healed": healed or []}


def _text_of(html_fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html_fragment)).strip()


# ---------------------------------------------------------------- API fetchers

def fetch_remotive(p: dict, cfg: dict) -> dict:
    """Degraded platform (2026-07-11 regression): API is a ~41-job stub. We still take
    what it gives — title filter happens in scan.py — and surface the degradation."""
    api = (p.get("api") or ["https://remotive.com/api/remote-jobs"])[0]
    try:
        r = _get(api)
        jobs = r.json().get("jobs", [])
    except Exception as exc:
        return _down(p["name"], f"API error: {type(exc).__name__}")
    cands = [
        _cand(j.get("title"), j.get("company_name"), j.get("candidate_required_location"),
              j.get("url"), p["name"], j.get("publication_date"), j.get("salary"),
              _text_of(j.get("description", "")) or None)
        for j in jobs
    ]
    return _ok(p["name"], cands,
               "DEGRADED: anonymous API is a stub (~41 jobs, params ignored); "
               "category HTML masks companies and carries no job links")


def fetch_workingnomads(p: dict, cfg: dict) -> dict:
    api = (p.get("api") or ["https://www.workingnomads.com/api/exposed_jobs/"])[0]
    try:
        jobs = _get(api).json()
    except Exception as exc:
        return _down(p["name"], f"API error: {type(exc).__name__}")
    cands = [
        _cand(j.get("title"), j.get("company_name"), j.get("location"), j.get("url"),
              p["name"], j.get("pub_date"), None, _text_of(j.get("description", "")) or None)
        for j in jobs
    ]
    return _ok(p["name"], cands, "exposed_jobs sample (~33 rows; category param ignored)")


def fetch_remoteok(p: dict, cfg: dict) -> dict:
    api = (p.get("api") or ["https://remoteok.com/api"])[0]
    try:
        data = _get(api).json()
    except Exception as exc:
        return _down(p["name"], f"API error: {type(exc).__name__}")
    cands = []
    for j in data:
        if not isinstance(j, dict) or not j.get("position"):
            continue  # first element is a legal notice
        cands.append(_cand(j.get("position"), j.get("company"), j.get("location"),
                           j.get("url"), p["name"], j.get("date"),
                           f"{j.get('salary_min') or ''}-{j.get('salary_max') or ''}".strip("-") or None,
                           _text_of(j.get("description", "")) or None))
    return _ok(p["name"], cands)


def fetch_justjoinit(p: dict, cfg: dict) -> dict:
    """Cursor-paginated category feed. Category id comes from the catalog per stream
    (params.category_id — PM=15 verified 2026-07-11). List data is for DISCOVERY ONLY —
    liveness comes exclusively from the offer page (invariant #6; chips lie)."""
    cid = (p.get("params") or {}).get("category_id")
    if not cid:
        return _down(p["name"], "no category_id resolved for this profile's stream")
    base = f"https://api.justjoin.it/v2/user-panel/offers/by-cursor?categories[]={cid}&perPage=20"
    cands, cursor, pages = [], None, 0
    seen_slugs: set[str] = set()
    try:
        while pages < 60:
            # pagination param is `from` (the meta.next.cursor VALUE, verified 2026-07-11;
            # a `cursor=` param is silently ignored and loops page 1 forever)
            url = base + (f"&from={cursor}" if cursor is not None else "")
            d = _get(url).json()
            for o in d.get("data", []):
                if o["slug"] in seen_slugs:
                    continue
                seen_slugs.add(o["slug"])
                city = o.get("city") or ""
                wp = o.get("workplaceType") or ""
                loc = f"{city} ({wp})".strip()
                sal = None
                for et in o.get("employmentTypes") or []:
                    if et.get("from") or et.get("to"):
                        sal = f"{et.get('from')}-{et.get('to')} {et.get('currency', '')} ({et.get('type', '')})"
                        break
                cands.append(_cand(o.get("title"), o.get("companyName"), loc,
                                   f"https://justjoin.it/job-offer/{o['slug']}", p["name"],
                                   o.get("publishedAt"), sal))
            nxt = (d.get("meta") or {}).get("next") or {}
            cursor = nxt.get("cursor")
            pages += 1
            if cursor is None or not nxt.get("itemsCount"):
                break
    except Exception as exc:
        if not cands:
            return _down(p["name"], f"API error: {type(exc).__name__}")
        return _ok(p["name"], cands, f"partial: cursor pagination broke after {pages} pages")
    return _ok(p["name"], cands, f"{pages} cursor pages (category {cid})")


def fetch_himalayas(p: dict, cfg: dict) -> dict:
    """Public API at /jobs/api (verified 2026-07-11: offset/limit, totalCount ~100k,
    newest-first). HTML listing 403s on direct fetch now — API replaces it. We take the
    newest pages and pre-filter to the profile's keywords + the catalog's per-stream
    prefilter phrases so a high-volume platform doesn't flood the pipeline with 100k
    rows; scan.py still applies the real keyword filter.

    REGRESSED 2026-07-20 (platform-health investigation, borjan-pm raw dropped to 4):
    `limit` is now silently capped at 20 server-side regardless of the value requested —
    verified live (limit=20/50/100/200 all return exactly 20 jobs; totalCount still ~99.7k,
    so only the per-page cap changed). The old `offset={page*100}` loop assumed 100/page,
    so it was actually SKIPPING 80 real jobs between every request (fetching ranks 0-19,
    then jumping to 100-119, missing 20-99 entirely) — a sparse, gap-filled sample instead
    of a true newest-1000 sweep. Fixed to `offset={page*20}` over 50 pages (still 1000
    newest jobs total, just with the real page size). Verified live: recovers 18 keyword
    matches vs. the buggy 4 for borjan-pm's PM stream (4.5x)."""
    kw = [k.lower() for k in (cfg.get("keywords", {}).get("core", []) + cfg.get("keywords", {}).get("expanded", []))]
    phrases = [s.lower() for s in (p.get("params") or {}).get("prefilter_phrases", [])]
    cands = []
    try:
        for page in range(50):
            d = _get(f"https://himalayas.app/jobs/api?limit=20&offset={page * 20}", timeout=30).json()
            jobs = d.get("jobs", [])
            for j in jobs:
                hay = (j.get("title", "") + " " + " ".join(j.get("categories") or [])
                       + " " + " ".join(j.get("parentCategories") or [])).lower()
                if not any(k in hay for k in kw) and not any(s in hay for s in phrases):
                    continue
                sal = None
                if j.get("minSalary") or j.get("maxSalary"):
                    sal = f"{j.get('minSalary')}-{j.get('maxSalary')} {j.get('currency', '')}/{j.get('salaryPeriod', '')}"
                loc = ", ".join((j.get("locationRestrictions") or [])[:4]) or "Worldwide"
                posted = j.get("pubDate")
                if isinstance(posted, (int, float)):
                    posted = datetime.fromtimestamp(posted, tz=timezone.utc).isoformat()
                url = j.get("guid") or f"https://himalayas.app/companies/{j.get('companySlug')}/jobs"
                cands.append(_cand(j.get("title"), j.get("companyName"), loc, url, p["name"],
                                   posted, sal, _text_of(j.get("description", ""))[:5000] or None))
            if not jobs:
                break
    except Exception as exc:
        if not cands:
            return _down(p["name"], f"API error: {type(exc).__name__}")
    return _ok(p["name"], cands, "jobs/api newest 1000, stream-prefiltered (HTML listing 403s)")


def fetch_greenhouse(p: dict, cfg: dict) -> dict:
    boards = p.get("boards") or []
    if not boards:
        return _ok(p["name"], [], "no boards configured yet (profile ats_boards empty)")
    cands, down = [], []
    for b in boards:
        try:
            d = _get(f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs?content=true").json()
            for j in d.get("jobs", []):
                cands.append(_cand(j.get("title"), b, (j.get("location") or {}).get("name"),
                                   j.get("absolute_url"), p["name"], j.get("updated_at"),
                                   None, _text_of(j.get("content", "")) or None))
        except Exception as exc:
            down.append(f"{b}:{type(exc).__name__}")
    note = f"boards down: {down}" if down else ""
    if down and not cands:
        return _down(p["name"], note)
    return _ok(p["name"], cands, note)


def fetch_lever(p: dict, cfg: dict) -> dict:
    boards = p.get("boards") or []
    if not boards:
        return _ok(p["name"], [], "no boards configured yet (profile ats_boards empty)")
    cands, down = [], []
    for b in boards:
        try:
            jobs = _get(f"https://api.lever.co/v0/postings/{b}?mode=json").json()
            for j in jobs:
                cat = j.get("categories") or {}
                posted = j.get("createdAt")
                if isinstance(posted, (int, float)):
                    posted = datetime.fromtimestamp(posted / 1000, tz=timezone.utc).isoformat()
                cands.append(_cand(j.get("text"), b, cat.get("location"), j.get("hostedUrl"),
                                   p["name"], posted, None, j.get("descriptionPlain")))
        except Exception as exc:
            down.append(f"{b}:{type(exc).__name__}")
    note = f"boards down: {down}" if down else ""
    if down and not cands:
        return _down(p["name"], note)
    return _ok(p["name"], cands, note)


def fetch_workable(p: dict, cfg: dict) -> dict:
    boards = p.get("boards") or []
    if not boards:
        return _ok(p["name"], [], "no boards configured yet (profile ats_boards empty)")
    cands, down = [], []
    for b in boards:
        try:
            token, pages = None, 0
            while pages < 20:
                body = {"query": "", "location": [], "department": [], "worktype": [], "remote": []}
                if token:
                    body["token"] = token
                _polite(f"https://apply.workable.com/{b}")
                r = requests.post(f"https://apply.workable.com/api/v3/accounts/{b}/jobs",
                                  json=body, headers=HEADERS, timeout=25)
                d = r.json()
                for j in d.get("results", []):
                    loc = (j.get("location") or {}).get("city") or ""
                    country = (j.get("location") or {}).get("country") or ""
                    remote = "remote" if j.get("remote") else ""
                    cands.append(_cand(j.get("title"), b, " ".join(x for x in (loc, country, remote) if x),
                                       f"https://apply.workable.com/{b}/j/{j['shortcode']}/",
                                       p["name"], j.get("published")))
                token = d.get("nextPage")
                pages += 1
                if not token:
                    break
        except Exception as exc:
            down.append(f"{b}:{type(exc).__name__}")
    note = f"boards down: {down}" if down else ""
    if down and not cands:
        return _down(p["name"], note)
    return _ok(p["name"], cands, note)


def fetch_pinpoint(p: dict, cfg: dict) -> dict:
    boards = p.get("boards") or []
    if not boards:
        return _ok(p["name"], [], "no boards configured yet (profile ats_boards empty)")
    cands, down = [], []
    for b in boards:
        try:
            d = _get(f"https://{b}.pinpointhq.com/postings.json").json()
            for j in d.get("data", []):
                loc = j.get("location")
                if isinstance(loc, dict):
                    loc = loc.get("name") or loc.get("city") or ""
                cands.append(_cand(j.get("title"), b, f"{loc} ({j.get('workplace_type', '')})",
                                   j.get("url"), p["name"], j.get("published_at") or j.get("created_at"),
                                   None, _text_of(j.get("description", "")) or None))
        except Exception as exc:
            down.append(f"{b}:{type(exc).__name__}")
    note = f"boards down: {down}" if down else ""
    if down and not cands:
        return _down(p["name"], note)
    return _ok(p["name"], cands, note)


def fetch_deel(p: dict, cfg: dict) -> dict:
    """Deel disabled Ashby's public posting API (verified empty via REST and GraphQL,
    2026-07-11). Their careers page embeds the full job set as escaped Strapi JSON —
    parse that. Fallback order: Ashby API (in case they re-enable) → careers JSON."""
    try:
        d = _get("https://api.ashbyhq.com/posting-api/job-board/deel").json()
        jobs = d.get("jobs") or []
        if jobs:
            cands = [_cand(j.get("title"), "Deel", j.get("location"), j.get("jobUrl") or j.get("applyUrl"),
                           p["name"], j.get("publishedAt")) for j in jobs]
            return _ok(p["name"], cands, "ashby posting API (re-enabled)")
    except Exception:
        pass
    try:
        html = _get("https://www.deel.com/careers/", timeout=40).text
    except Exception as exc:
        return _down(p["name"], f"careers page error: {type(exc).__name__}")
    # Escaped-JSON job objects: {"id":N,"attributes":{"ashby_id":"...", ... "slug":"/careers/position/?ashby_jid=..."}}
    cands = []
    for m in re.finditer(r'\{\\"id\\":\d+,\\"attributes\\":\{\\"ashby_id\\":\\"([\w-]+)\\"(.{0,4000}?)\\"slug\\":\\"([^"\\]+)\\"', html):
        jid, blob, slug = m.groups()
        title_m = re.search(r'\\"(?:job_title|title)\\":\\"([^"\\]{3,90})\\"', blob)
        locs = re.findall(r'\\"location\\":\\"([^"\\]{2,60})\\"', blob)
        updated = re.search(r'\\"ashby_updated_at\\":\\"([^"\\]+)\\"', blob)
        comp = re.search(r'\\"compensation_tier_summary\\":\\"([^"\\]+)\\"', blob)
        if not title_m:
            seo = re.search(r'\\"SEO\\":\{\\"title\\":\\"([^"\\|]{3,90})', blob)
            title_m = seo
        if title_m:
            cands.append(_cand(title_m.group(1).strip(), "Deel", ", ".join(locs[:4]),
                               urljoin("https://www.deel.com", slug.replace("\\", "")),
                               p["name"], updated.group(1) if updated else None,
                               comp.group(1) if comp else None))
    if not cands:
        # careers page loaded (200) but the embedded-JSON parse found nothing — selector drift
        return _down(p["name"], "careers-page JSON parse yielded 0 jobs (layout drifted?)",
                     http_ok=True)
    return _ok(p["name"], cands, "careers-page embedded JSON (Ashby API disabled by Deel)")


# ------------------------------------------------------- RSS / HTML fetchers

def fetch_wwr(p: dict, cfg: dict) -> dict:
    """All-jobs RSS (category RSS 301s to nowhere). All categories = the v2.10.0
    cross-category pass is inherent. Title format: 'Company: Role'."""
    try:
        xml = _get("https://weworkremotely.com/remote-jobs.rss", timeout=30).text
    except Exception as exc:
        return _down(p["name"], f"RSS error: {type(exc).__name__}")
    cands = []
    for item in re.findall(r"<item>(.*?)</item>", xml, re.S):
        def tag(name):
            m = re.search(rf"<{name}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{name}>", item, re.S)
            return (m.group(1).strip() if m else "")
        raw_title = tag("title")
        company, _, role = raw_title.partition(":")
        if not role:
            role, company = raw_title, ""
        region = tag("region") or tag("category")
        cands.append(_cand(role.strip(), company.strip(), region, tag("link"), p["name"],
                           tag("pubDate"), None, _text_of(tag("description"))[:5000] or None))
    if not cands:
        # reached the feed (200) but parsed nothing — the silent-break shape, not an outage
        return _down(p["name"], "RSS parsed to 0 items", http_ok=True)
    return _ok(p["name"], cands, "all-jobs RSS (cross-category inherent)")


# Per-platform link-harvest specs for listing pages (deterministic, testable),
# keyed by CATALOG SLUG.
# href: full-match regex on the anchor's href (path or absolute)
# company_idx: path segment carrying the company slug (None = unknown from URL)
# min_hyphens: minimum hyphens in the final slug — separates postings from category links
HARVEST_SPECS: dict[str, dict] = {
    "himalayas": {"href": r"/companies/[^/]+/jobs/[^/]+/?", "base": "https://himalayas.app", "company_idx": 2},
    "jobgether": {"href": r"/offer/[\w-]{10,}", "base": "https://jobgether.com"},
    "arc": {"href": r"/remote-jobs/details/[\w-]+", "base": "https://arc.dev"},
    "remote-rocketship-worldwide": {"href": r"/company/[^/]+/jobs/[^/]+/?", "base": "https://www.remoterocketship.com", "company_idx": 2},
    "remote-rocketship-europe": {"href": r"/company/[^/]+/jobs/[^/]+/?", "base": "https://www.remoterocketship.com", "company_idx": 2},
    "wttj": {"href": r"/en/companies/[^/]+/jobs/[^/]+", "base": "https://www.welcometothejungle.com", "company_idx": 3},
    "nodesk": {"href": r"/remote-jobs/[a-z0-9-]+/?", "base": "https://nodesk.co", "min_hyphens": 3},
    "dynamite": {"href": r"(?:https://dynamitejobs\.com)?/company/[^/]+/remote-job/[\w-]+/?", "base": "https://dynamitejobs.com", "company_idx": 2},
    # 2026-07-20: site redesign — postings now render client-side (headless already handles
    # that) under a RELATIVE href (no leading slash, no "/remote-jobs/" prefix):
    # "remote-manager-exec-jobs/product-owner-d365-finance-operations-nutrafol-8ab854..."
    # instead of the old absolute "/remote-jobs/{category}/{slug}". min_hyphens=2 keeps out
    # nav noise like "remote-jobs/new" (the "post a job" link, slug "new" has 0 hyphens).
    "justremote": {"href": r"[a-z]+(?:-[a-z]+)*-jobs/[\w-]+", "base": "https://justremote.co",
                   "min_hyphens": 2},
    "landing-jobs": {"href": r"(?:https://landing\.jobs)?/at/[^/]+/[\w-]+", "base": "https://landing.jobs", "company_idx": 2},
    "crossover": {"href": r"/jobs/\d+/[\w-]+/[\w-]+", "base": "https://www.crossover.com", "company_idx": 3},
    # Phase 2 niche boards — smoke-tested live 2026-07-17 (SSR HTML, harvestable):
    "ai-jobs-net": {"href": r"/job/[a-z0-9-]+-\d{4,}/?", "base": "https://ai-jobs.net"},
    "icrunchdata": {"href": r"/jobs/[a-z0-9-]+", "base": "https://icrunchdata.com", "min_hyphens": 1},
    "dribbble": {"href": r"/jobs/\d+-[\w-]+", "base": "https://dribbble.com"},
    "problogger": {"href": r"/jobs/job/[a-z0-9-]+/?", "base": "https://problogger.com"},  # headless (WPJobBoard)
}


def _slug_title(url: str) -> str:
    slug = url.rstrip("/").split("/")[-1]
    return re.sub(r"[-_]+", " ", re.sub(r"\b[0-9a-f]{6,}\b", "", slug)).strip()


def _harvest_links(html: str, platform_slug: str, platform_name: str) -> list[dict]:
    spec = HARVEST_SPECS[platform_slug]
    href_re = re.compile(rf"^{spec['href']}$")
    cands: dict[str, dict] = {}
    try:
        from selectolax.parser import HTMLParser

        # `[href]` — ANY element carrying an href, not just <a> (2026-07-20 finding: Dynamite
        # Jobs renders most cards as `<h2 href="...">`, not a real anchor; tree.css("a") alone
        # silently missed 15/16 real postings on that platform). The per-platform regex below
        # already filters out noise this widening could pick up (stylesheet/base hrefs, etc.)
        # since those never match a job-posting-shaped pattern.
        anchors = [(el.attributes.get("href") or "", re.sub(r"\s+", " ", el.text()).strip())
                   for el in HTMLParser(html).css("[href]")]
    except Exception:
        anchors = [(h, "") for h in re.findall(r'href="([^"]+)"', html)]
    for href, text in anchors:
        path = re.sub(r"^https?://[^/]+", "", href.split("?")[0])
        if not href_re.match(path) and not href_re.match(href.split("?")[0]):
            continue
        slug = path.rstrip("/").split("/")[-1]
        if slug.count("-") < spec.get("min_hyphens", 0):
            continue  # category/nav link, not a posting
        url = href if href.startswith("http") else urljoin(spec["base"], path)
        company = ""
        if spec.get("company_idx") is not None:
            parts = [s for s in path.split("/") if s]
            if len(parts) > spec["company_idx"] - 1:
                company = parts[spec["company_idx"] - 1].replace("-", " ")
        # anchor text is the title when it looks like one; slug otherwise
        title = text if 3 < len(text) < 90 and not re.match(r"(?i)(view|apply|read|see) ", text) else _slug_title(url)
        prev = cands.get(url)
        if prev is None or (prev["title"] == _slug_title(url) and title != prev["title"]):
            cands[url] = _cand(title, company, "", url, platform_name)
    return list(cands.values())


def fetch_html_listing(p: dict, cfg: dict, headless: bool = False, scroll_rounds: int = 0) -> dict:
    urls = p.get("urls") or []
    slug = p.get("slug", "")
    if not urls:
        return _down(p["name"], "no listing urls configured")
    all_cands: dict[str, dict] = {}
    notes: list[str] = []
    healed: list[str] = []
    reached_200 = False  # any URL returned a 200 body (direct or headless) → http_ok
    for u in urls:
        html = ""
        direct_ok = False
        if not headless:
            try:
                r = _get(u)
                if r.status_code == 200:
                    html, direct_ok, reached_200 = r.text, True, True
                else:
                    notes.append(f"HTTP {r.status_code} on {u}")
            except Exception as exc:
                notes.append(f"{type(exc).__name__} on {u}")
        if not html or slug not in HARVEST_SPECS or not _harvest_links(html, slug, p["name"]):
            # direct failed or produced nothing harvestable → headless render (Layer-1.5 heal:
            # escalate direct→headless when a board blocks or JS-gates the plain request)
            try:
                import render

                rendered = render.render(u, scroll_rounds=scroll_rounds)
                if rendered:
                    reached_200 = True
                    # a heal claim requires the escalation to ACTUALLY recover candidates — a
                    # render that comes back empty/blocked (e.g. a bot-wall page that still
                    # returns a body) proved reachability, not recovery, and must not be reported
                    # as a heal (2026-07-20 QA finding: Remote Rocketship healed=[recovered] but
                    # still harvested 0 — a false "heal" claim the honest-failure floor forbids).
                    escalation = not headless and not direct_ok
                    harvested_from_render = (slug in HARVEST_SPECS
                                             and bool(_harvest_links(rendered, slug, p["name"])))
                    if escalation and harvested_from_render:
                        healed.append(f"recovered via headless: {u}")
                    elif escalation:
                        notes.append(f"escalated to headless for {u}, still 0 harvested")
                    html = rendered
                elif not html:
                    notes.append(f"headless render empty for {u}")
            except Exception as exc:
                notes.append(f"render {type(exc).__name__} on {u}")
        if html and slug in HARVEST_SPECS:
            for c in _harvest_links(html, slug, p["name"]):
                all_cands.setdefault(c["url"], c)
    if healed:
        notes.append("healed: " + "; ".join(healed))
    if not all_cands:
        # reached_200 with 0 harvested is the SILENT SELECTOR BREAK (http_ok=True); a pure
        # connectivity failure (never got a body) is a plain outage (http_ok=False).
        return _down(p["name"], "; ".join(notes) or "no candidates harvested",
                     http_ok=reached_200, healed=healed)
    return _ok(p["name"], list(all_cands.values()), "; ".join(notes), healed=healed)


# ----------------------------------------------------------- JD fetch + mirrors

ATS_URL_PATTERNS = re.compile(
    r"https?://(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/[^\s\"']+|"
    r"https?://jobs\.lever\.co/[^\s\"']+|"
    r"https?://apply\.workable\.com/[^\s\"']+|"
    r"https?://[\w-]+\.pinpointhq\.com/[^\s\"']+|"
    r"https?://jobs\.ashbyhq\.com/[^\s\"']+"
)


def resolve_source_url(html_or_text: str) -> str | None:
    """Detect the source ATS URL inside a mirror/aggregator page (2.7.0: the source
    ATS URL is the liveness authority)."""
    m = ATS_URL_PATTERNS.search(html_or_text)
    return m.group(0).rstrip('\\"\'>).,') if m else None


def fetch_jd(url: str) -> tuple[str, str, str]:
    """Fetch full JD for one posting. Returns (jd_text, raw_html, method).
    Chain: direct → headless. Mirror resolution is the caller's job
    (resolve_source_url on the raw html + config mirrors[])."""
    try:
        r = _get(url, timeout=30)
        if r.status_code == 200:
            text = _visible_text(r.text)
            if len(text) > 600:
                return text, r.text, "direct"
    except Exception:
        pass
    try:
        import render

        html = render.render(url)
        text = _visible_text(html)
        if len(text) > 600:
            return text, html, "headless"
    except Exception:
        pass
    return "", "", "failed"


_SCRIPT_STYLE_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.I | re.S)


def _visible_text(html: str) -> str:
    """Strip HTML down to visible body text. selectolax does this properly (DOM-aware,
    strips script/style/nav/footer/header ENTIRELY incl. their content). The regex
    fallback (selectolax unavailable — missing package, import failure, etc.) MUST also
    strip script/style block content first, not just tag markers — a naive `<[^>]+>` ->
    " " strip leaves inline CSS/JS text sitting in the body as if it were content (found
    2026-07-20: an environment without selectolax silently fed ~700KB of raw CSS to every
    downstream text detector — language, salary, stack-keyword — as "JD text", corrupting
    them all with no visible signal). Honest-failure: the fallback still degrades (loses
    DOM-aware nav/footer/header stripping) but must never leak script/style CONTENT."""
    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        for tag in ("script", "style", "noscript", "nav", "footer", "header"):
            for node in tree.css(tag):
                node.decompose()
        return re.sub(r"\s+", " ", tree.body.text(separator=" ")).strip() if tree.body else ""
    except Exception as exc:
        print(f"[fetch_boards] _visible_text: selectolax unavailable ({exc}), "
              "using degraded regex fallback", file=sys.stderr)
        stripped = _SCRIPT_STYLE_BLOCK.sub(" ", html)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", stripped)).strip()


# ----------------------------------------------------------------- dispatcher
# Keyed by catalog SLUG (4.0) — platform display names are cosmetic now.

HANDLERS = {
    "wwr": fetch_wwr,
    "himalayas": fetch_himalayas,
    "remotive": fetch_remotive,
    "working-nomads": fetch_workingnomads,
    "remote-ok": fetch_remoteok,
    "justjoin-it": fetch_justjoinit,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "workable": fetch_workable,
    "pinpoint": fetch_pinpoint,
    "deel": fetch_deel,
}


def fetch_platform(p: dict, cfg: dict) -> dict:
    slug = p.get("slug", "")
    try:
        if slug in HANDLERS:
            return HANDLERS[slug](p, cfg)
        if p.get("fetch_mode") == "headless_scroll":
            return fetch_html_listing(p, cfg, headless=True, scroll_rounds=3)
        if p.get("fetch_mode") == "headless":
            return fetch_html_listing(p, cfg, headless=True)
        return fetch_html_listing(p, cfg, headless=False)
    except Exception as exc:  # a fetcher bug must never take down the whole run
        return _down(p["name"], f"handler crashed: {type(exc).__name__}: {exc}")


def fetch_all(cfg: dict) -> list[dict]:
    """Fetch every active platform in tier order. Returns one result dict per platform."""
    platforms = [p for p in cfg["platforms"] if p.get("active")]
    platforms.sort(key=lambda p: (p.get("tier", 9), p.get("id", 99)))
    return [fetch_platform(p, cfg) for p in platforms]


if __name__ == "__main__":
    import argparse

    import paths
    import profile_loader

    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default=None, help="substring filter on platform name/slug")
    ap.add_argument("--profile", default=None)
    cli = ap.parse_args()
    cfg = profile_loader.load(cli.profile or paths.get_profile())
    for p in cfg["platforms"]:
        if not p.get("active") or (cli.only and cli.only.lower() not in (p["name"] + p["slug"]).lower()):
            continue
        res = fetch_platform(p, cfg)
        flag = "DOWN" if res["source_down"] else "ok"
        print(f"{res['platform']:36} {flag:5} {len(res['candidates']):4} candidates  {res['note'][:90]}")
        for c in res["candidates"][:3]:
            print(f"    - {c['title'][:60]!r} @ {c['company'][:25]!r} [{c['loc'][:30]}]")
