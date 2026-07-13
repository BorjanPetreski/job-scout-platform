#!/usr/bin/env python3
"""linkedin_tripwire.py — guest-endpoint discovery tripwire. Polite and small by design.

Policy (§0): NO login, NO cookies, NO authenticated sessions of any kind. LinkedIn
participates at discovery level only; auth-walled JDs get flagged
"login-walled — open manually", never browsed.

Hard caps (config): ≤10 requests/run, ≥3s delay, generic desktop UA. Stop IMMEDIATELY
on 429/999 and mark the source down for the run. Endpoint verified live 2026-07-11;
it changes without notice — on breakage degrade gracefully ("LinkedIn source down"),
never crash the run.
"""

from __future__ import annotations

import html as htmllib
import re
import time

import requests

ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

TITLE_RE = re.compile(r'base-search-card__title[^>]*>\s*([^<]+)')
COMPANY_RE = re.compile(r'base-search-card__subtitle[^>]*>\s*(?:<a[^>]*>)?\s*([^<]+)', re.S)
LOC_RE = re.compile(r'job-search-card__location[^>]*>\s*([^<]+)')
LINK_RE = re.compile(r'href="(https://[^"]*linkedin\.com/jobs/view/[^"?]+)')
TIME_RE = re.compile(r'datetime="([\d-]+)"')


def _clean(s: str | None) -> str:
    return htmllib.unescape(re.sub(r"\s+", " ", s or "")).strip()


def fetch_tripwire(cfg: dict) -> dict:
    """Returns {"platform": "LinkedIn (tripwire)", "candidates": [...], "source_down": bool, "note": str}."""
    lt = cfg.get("linkedin_tripwire", {})
    caps = cfg.get("caps", {})
    if not lt.get("enabled", True):
        return {"platform": "LinkedIn (tripwire)", "candidates": [], "source_down": False,
                "note": "disabled in config"}
    max_req = int(caps.get("linkedin_requests_per_run", 10))
    delay = float(caps.get("linkedin_min_delay_s", 3))
    keywords = lt.get("keywords", ["Project Manager"])
    locations = lt.get("locations", ["European Union", "Worldwide"])

    candidates: dict[str, dict] = {}
    requests_made = 0
    note = ""
    for kw in keywords:
        for loc in locations:
            if requests_made >= max_req:
                note = f"request cap {max_req} reached"
                break
            params = {
                "keywords": kw, "location": loc, "start": "0",
                "f_WT": lt.get("remote_filter", "f_WT=2").split("=")[-1],
                "f_TPR": lt.get("freshness", "f_TPR=r86400").split("=")[-1],
            }
            try:
                r = requests.get(ENDPOINT, params=params, headers={"User-Agent": UA}, timeout=20)
                requests_made += 1
            except requests.RequestException as exc:
                return {"platform": "LinkedIn (tripwire)", "candidates": list(candidates.values()),
                        "source_down": True, "note": f"network error: {type(exc).__name__}"}
            if r.status_code in (429, 999):
                return {"platform": "LinkedIn (tripwire)", "candidates": list(candidates.values()),
                        "source_down": True,
                        "note": f"HTTP {r.status_code} — rate-limited, stopped immediately"}
            if r.status_code != 200:
                note = f"HTTP {r.status_code} on ({kw!r}, {loc!r})"
                time.sleep(delay)
                continue
            # split into per-card chunks (each card is a <li> holding one job link)
            chunks = re.split(r'(?=<li\b)', r.text)
            for chunk in chunks:
                link_m = LINK_RE.search(chunk)
                if not link_m:
                    continue
                title_m, company_m, loc_m = TITLE_RE.search(chunk), COMPANY_RE.search(chunk), LOC_RE.search(chunk)
                title = _clean(title_m.group(1)) if title_m else ""
                company = _clean(company_m.group(1)) if company_m else ""
                locname = _clean(loc_m.group(1)) if loc_m else ""
                posted = TIME_RE.search(chunk)
                url = link_m.group(1)
                if not url:
                    continue
                candidates.setdefault(url, {
                    "title": title, "company": company, "loc": locname, "url": url,
                    "platform": "LinkedIn (tripwire)",
                    "posted_at": posted.group(1) if posted else None,
                    "salary": None, "jd_text": None,
                    "flags": ["LinkedIn guest card — full JD via public job page where it "
                              "renders; auth-wall → login-walled, open manually"],
                })
            time.sleep(delay)
        if requests_made >= max_req:
            break
    return {"platform": "LinkedIn (tripwire)", "candidates": list(candidates.values()),
            "source_down": False,
            "note": note or f"{requests_made} guest requests, {len(candidates)} unique cards"}


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import paths
    import profile_loader

    cfg = profile_loader.load(sys.argv[1] if len(sys.argv) > 1 else paths.get_profile())
    res = fetch_tripwire(cfg)
    print(f"{res['platform']}: down={res['source_down']} n={len(res['candidates'])} note={res['note']}")
    for c in res["candidates"][:5]:
        print(f"  - {c['title'][:50]!r} @ {c['company'][:25]!r} [{c['loc'][:28]}] {c['posted_at']}")
