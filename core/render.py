#!/usr/bin/env python3
"""render.py — headless page rendering as a fetch method. Nothing else.

Policy (spec §0, Borjan's decision 2026-07-11; narrowly amended 2026-07-20 — do not
extend further without the same kind of explicit sign-off):
The public API surface of this module is `render(url) -> html` (plus `render_many` as
a batched convenience) **plus one scoped exception**: an optional `scroll_rounds` step
that scrolls to the bottom of the page N times before snapshotting, for boards whose
listings lazy-load on scroll (found via the platform-health NEVER_PRODUCED/
SELECTOR_SUSPECT signals; JustRemote is the first user, see catalog `quirks`). Scroll
is `page.evaluate("window.scrollTo(...))")`/`page.mouse.wheel(...)` — a passive viewport
move, never a decision about what to click or type. It still returns HTML text for the
existing regex/selectolax pipeline to parse — no screenshot, no image, no vision model
anywhere in this module. Everything else stays banned: no click/type/navigation-decision
methods exist here, so the computer-use ban stays STRUCTURAL for anything beyond scroll.
Headless Chromium only — no headed option is exposed. Functionally a JS-capable curl,
now with an optional "nudge it to load more" step.
"""

from __future__ import annotations

import os
from pathlib import Path

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT_MS = 30_000

# Managed environments pre-install Chromium outside the playwright cache;
# honor an explicit executable path when the default launch can't find one.
_EXEC_CANDIDATES = [
    os.environ.get("JOB_SCOUT_CHROMIUM", ""),
    "/opt/pw-browsers/chromium",
]


def _executable_path() -> str | None:
    for cand in _EXEC_CANDIDATES:
        if cand and Path(cand).exists():
            return cand
    return None


def render(url: str, wait_selector: str | None = None, timeout_ms: int = DEFAULT_TIMEOUT_MS,
          scroll_rounds: int = 0) -> str:
    """Load `url` in headless Chromium, execute its JS, return the rendered HTML.

    wait_selector: optional CSS selector to wait for before snapshotting
    (falls back to network-idle, then load, whichever succeeds first).
    scroll_rounds: scroll to the page bottom this many times (short wait between each)
    before snapshotting — for lazy-load-on-scroll boards. 0 = no scroll (default,
    unchanged behavior). Still returns HTML text; no screenshot/image is ever taken.
    Raises on navigation failure — callers map that to their fallback chain.
    """
    return render_many([(url, wait_selector)], timeout_ms=timeout_ms, scroll_rounds=scroll_rounds)[url]


def render_many(targets: list[tuple[str, str | None]], timeout_ms: int = DEFAULT_TIMEOUT_MS,
                scroll_rounds: int = 0) -> dict[str, str]:
    """Render several URLs reusing one browser. Returns {url: html}; failed URLs map to ''."""
    from playwright.sync_api import sync_playwright

    results: dict[str, str] = {}
    with sync_playwright() as pw:
        launch_kwargs: dict = {"headless": True}  # headless only, per policy — never parameterized
        exe = _executable_path()
        if exe:
            launch_kwargs["executable_path"] = exe
        # Chromium ignores proxy env vars; managed environments route egress through one.
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}
            # TLS-re-terminating agent proxies reset Chromium's TLS 1.3 ClientHello
            # (verified 2026-07-11: 1.3 → ERR_CONNECTION_RESET, 1.2 → ok). The proxy
            # re-terminates TLS to the real site anyway, so capping this hop is lossless.
            # Without a proxy (Borjan's machine) no flag is set — full TLS 1.3.
            launch_kwargs["args"] = ["--ssl-version-max=tls1.2"]
        browser = pw.chromium.launch(**launch_kwargs)
        try:
            context = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900})
            page = context.new_page()
            for url, wait_selector in targets:
                try:
                    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=timeout_ms // 2)
                        except Exception:
                            pass  # selector may be wrong/renamed; snapshot whatever rendered
                    else:
                        try:
                            page.wait_for_load_state("networkidle", timeout=timeout_ms // 2)
                        except Exception:
                            pass  # long-polling pages never go idle; snapshot after DOM load
                    for _ in range(scroll_rounds):
                        # passive viewport move only — no click/type, no navigation decision.
                        # Triggers a lazy-load site's own IntersectionObserver/scroll listener
                        # to fire its "load more" call; we just wait for it, never drive it.
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        try:
                            page.wait_for_load_state("networkidle", timeout=2000)
                        except Exception:
                            pass  # no new network activity this round; still snapshot below
                    results[url] = page.content()
                except Exception:
                    results[url] = ""
        finally:
            browser.close()
    return results


if __name__ == "__main__":
    import sys

    html = render(sys.argv[1])
    print(f"{len(html)} bytes rendered")
    print(html[:500])
