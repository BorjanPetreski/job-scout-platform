#!/usr/bin/env python3
"""check_links.py — parallel liveness checker implementing the 2.7.0 definition in code.

LIVENESS = a direct fetch of the SOURCE URL returning actual JD content. Nothing else:
not search snippets, not mirrors, not crawl caches, not list-view chips (JustJoin.it's
own "New" badges contradicted its own expired offer pages, 2026-07-10). Mirror liveness
never equals source liveness (Superside: 3 live mirrors, source Lever URL 404).

Verdicts:
  live               HTTP success AND JD-content signal AND no platform expired-marker
  stale              404/410, expired-marker body, or redirect to a generic feed
  unverifiable_direct  app-shell 200 whose headless render also fails/yields no JD
                       (maps to "❓ Unverified" in output — NEVER silently upgraded)

A 200 returning app-shell chrome is NOT live: it escalates to a headless render
(render.py) and the RENDERED body is evaluated against the same criteria, so JS
platforms can earn a real ✅. Himalayas company-URL bounce is a config-special-cased
quirk, not staleness.

Every check appends evidence to profiles/<id>/state/fetch_evidence.jsonl (url, status,
content hash, timestamp) — verification survives session breaks (delta row 1).

Standalone: `python3 check_links.py urls.txt [--profile ID]` — the same-session
URL-handoff recheck (Blexr/CloudLinux lesson) at zero token cost.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

GENERIC_EXPIRED_MARKERS = [
    "no longer accepting applications",
    "this position has been filled",
    "job is no longer available",
    "this job has expired",
    "offer expired",
    "posting has closed",
    "this vacancy is now closed",
]

# Minimal signals that a body is a JD, not app-shell chrome or a listing feed.
JD_SIGNALS = re.compile(
    r"(?i)\b(responsibilit|requirements?|qualifications?|what you.ll do|about (the|this) role|"
    r"apply (now|for this)|we are looking for|job description)\b"
)

_evidence_lock = threading.Lock()
_host_locks: dict[str, threading.Lock] = {}
_host_last: dict[str, float] = {}
_registry_lock = threading.Lock()


def _load_config() -> dict:
    import profile_loader

    return profile_loader.load(paths.get_profile())


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url).split("/")[0].lower()


def _polite_wait(host: str, min_delay: float) -> None:
    with _registry_lock:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        elapsed = time.time() - _host_last.get(host, 0.0)
        if elapsed < min_delay:
            time.sleep(min_delay - elapsed)
        _host_last[host] = time.time()


def _log_evidence(url: str, status: int | str, body: str, verdict: str, via: str) -> None:
    rec = {
        "url": url,
        "status": status,
        "content_hash": hashlib.sha256(body.encode("utf-8", "replace")).hexdigest()[:16] if body else None,
        "bytes": len(body),
        "verdict": verdict,
        "via": via,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    evidence_path = paths.evidence_path()
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    with _evidence_lock, evidence_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _visible_text(html: str) -> str:
    try:
        from selectolax.parser import HTMLParser

        tree = HTMLParser(html)
        for tag in ("script", "style", "noscript"):
            for node in tree.css(tag):
                node.decompose()
        return tree.body.text(separator=" ") if tree.body else ""
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)


def _markers_for(url: str, platforms: list[dict]) -> list[str]:
    markers = list(GENERIC_EXPIRED_MARKERS)
    host = _host(url)
    for p in platforms:
        for u in (p.get("urls") or []) + (p.get("api") or []):
            if _host(u) in host or host in _host(u):
                markers += [m.lower() for m in (p.get("expired_markers") or [])]
    return markers


def _evaluate_body(html: str, markers: list[str]) -> str | None:
    """Return 'live'/'stale' from a body, or None if it looks like app-shell chrome."""
    text = _visible_text(html)
    lowered = text.lower()
    for m in markers:
        if m.lower() in lowered:
            return "stale"
    if len(text.strip()) > 400 and JD_SIGNALS.search(text):
        return "live"
    return None  # app-shell / not enough signal — caller escalates


def check_url(url: str, cfg: dict | None = None, use_headless: bool = True,
              _defer_render: dict | None = None) -> dict:
    """Check one URL. Returns {url, verdict, status, note}.

    _defer_render: internal — when a dict is passed, headless escalation is NOT run
    inline; the URL is parked there and check_urls() batch-renders in ONE browser
    (8 threads × concurrent Chromium launches = swallowed failures → false
    Unverified/Blocked, found 2026-07-11 with 15 NoDesk leads)."""
    cfg = cfg or _load_config()
    platforms = cfg.get("platforms", [])
    markers = _markers_for(url, platforms)
    min_delay = float(cfg.get("caps", {}).get("min_delay_same_host_s", 1))
    timeout = int(cfg.get("scan", {}).get("timeout_s", 25))
    host = _host(url)

    _polite_wait(host, min_delay)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        status: int | str = resp.status_code
        body = resp.text
    except requests.RequestException as exc:
        _log_evidence(url, f"error:{type(exc).__name__}", "", "unverifiable_direct", "direct")
        return {"url": url, "verdict": "unverifiable_direct", "status": None,
                "note": f"fetch error: {type(exc).__name__}"}

    # Himalayas company-URL bounce is a quirk, not staleness — but a bounce to a
    # generic feed means the specific posting is gone everywhere else.
    if resp.history and _host(resp.url) != host and "himalayas.app" not in host:
        _log_evidence(url, status, body, "stale", "direct")
        return {"url": url, "verdict": "stale", "status": status, "note": f"redirected off-host to {resp.url}"}

    if status in (404, 410):
        _log_evidence(url, status, body, "stale", "direct")
        return {"url": url, "verdict": "stale", "status": status, "note": "gone"}

    if status == 200:
        # Redirect to a generic feed (path collapsed to a listing root) = posting gone.
        if resp.history and "himalayas.app" not in host:
            final_path = re.sub(r"^https?://[^/]+", "", resp.url).rstrip("/")
            if final_path.count("/") <= 1 and len(final_path) < 30:
                _log_evidence(url, status, body, "stale", "direct")
                return {"url": url, "verdict": "stale", "status": status,
                        "note": f"redirected to generic feed {resp.url}"}
        verdict = _evaluate_body(body, markers)
        if verdict:
            _log_evidence(url, status, body, verdict, "direct")
            return {"url": url, "verdict": verdict, "status": status, "note": "direct body"}
        # app-shell 200 → headless escalation
        if use_headless:
            if _defer_render is not None:
                _defer_render[url] = (status, body, markers)
                return {"url": url, "verdict": "_deferred", "status": status, "note": ""}
            html = _render_one(url)
            return _finish_rendered(url, status, body, html, markers)
        _log_evidence(url, status, body, "unverifiable_direct", "direct")
        return {"url": url, "verdict": "unverifiable_direct", "status": status,
                "note": "app-shell 200; headless disabled"}

    # 403-class bot blocks: headless render retry (delta row 9) — still the source URL,
    # so a rendered JD counts for liveness. Unresolved → unverifiable_direct.
    if status in (401, 403, 406, 429, 503) and use_headless:
        if _defer_render is not None:
            _defer_render[url] = (status, body, markers)
            return {"url": url, "verdict": "_deferred", "status": status, "note": ""}
        html = _render_one(url)
        return _finish_rendered(url, status, body, html, markers)

    _log_evidence(url, status, body, "unverifiable_direct", "direct")
    return {"url": url, "verdict": "unverifiable_direct", "status": status, "note": f"HTTP {status}"}


def _render_one(url: str) -> str:
    try:
        import render

        return render.render(url)
    except Exception:
        return ""


def _finish_rendered(url: str, status: int, body: str, html: str, markers: list[str]) -> dict:
    if html:
        verdict = _evaluate_body(html, markers)
        if verdict:
            _log_evidence(url, status, html, verdict, "headless")
            return {"url": url, "verdict": verdict, "status": status, "note": "rendered body"}
    _log_evidence(url, status, html or body, "unverifiable_direct", "headless")
    return {"url": url, "verdict": "unverifiable_direct", "status": status,
            "note": f"HTTP {status}; render inconclusive"}


def check_urls(urls: list[str], cfg: dict | None = None, use_headless: bool = True) -> list[dict]:
    """Parallel HTTP pass, then ONE shared browser for every headless escalation
    (concurrent per-thread Chromium launches silently fail under load)."""
    cfg = cfg or _load_config()
    parallelism = int(cfg.get("caps", {}).get("link_check_parallelism", 8))
    deferred: dict[str, tuple] = {}
    with ThreadPoolExecutor(max_workers=parallelism) as pool:
        results = list(pool.map(lambda u: check_url(u, cfg, use_headless, deferred), urls))
    if deferred:
        try:
            import render

            rendered = render.render_many([(u, None) for u in deferred])
        except Exception:
            rendered = {u: "" for u in deferred}
        finished = {u: _finish_rendered(u, st, body, rendered.get(u, ""), markers)
                    for u, (st, body, markers) in deferred.items()}
        results = [finished.get(r["url"], r) if r["verdict"] == "_deferred" else r for r in results]
    return results


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("urls_file", help="one URL per line")
    ap.add_argument("--profile", default=None)
    cli = ap.parse_args()
    if cli.profile:
        paths.set_profile(cli.profile)
    url_list = [line.strip() for line in Path(cli.urls_file).read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    for result in check_urls(url_list):
        icon = {"live": "✅", "stale": "❌", "unverifiable_direct": "❓"}[result["verdict"]]
        print(f"{icon} {result['verdict']:<20} {result['status']!s:<6} {result['url']}  ({result['note']})")
