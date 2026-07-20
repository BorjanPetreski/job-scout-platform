# HEALTH_LOG — platform health review history

> The auditable record of every Layer-2 platform-health review (see
> [HEALTH_MONITORING.md](HEALTH_MONITORING.md) + [PHASE_3_HEALTH_PLAN.md](PHASE_3_HEALTH_PLAN.md)).
> One row per flagged board per review: what `core/health.py` flagged, the live diagnosis,
> the catalog fix applied (through the validator — never an ad-hoc scanner edit), and the PR.
> This is how board-rot repair stops being invisible tribal knowledge and becomes a trend we
> can see: a board that recurs here is a demotion candidate; a signal that keeps mis-firing is a
> threshold to tune.

## How a review works (the cue → fix loop)

1. A scan prints `⚠ platform health review due`. That's the cue.
2. Run `python3 core/health.py [--profile <id>]` — it flags boards mechanically and acks the counter.
3. For each finding, **fetch a live sample and diagnose** the real cause (selector drift? moved
   endpoint? renamed slug? new bot-wall? empty config?).
4. Apply the fix in `catalog/platforms.yaml` (HARVEST_SPEC / quirk / `fetch_mode` / `active` /
   `status` / ATS tokens) and prove it with `python3 core/validate.py`.
5. Add a row below. Link the PR. Flip the board's `status` back to `active`/`verified` only once a
   live fetch produces sane, structured results.

**Signal → likely fix cheat-sheet:**

| Signal | Most common real cause | Typical catalog fix |
|--------|------------------------|---------------------|
| `SELECTOR_SUSPECT` | markup/HTML changed under a HARVEST_SPEC | update the `href` regex / `company_idx` / `min_hyphens`, or flip `fetch_mode` to headless |
| `DOWN_STREAK` | endpoint moved, new bot-wall, or board gone dark | new URL/api, add a mirror, escalate fetch_mode, or demote/deactivate |
| `YIELD_COLLAPSE` | pagination broke, or a category slug renamed | fix the cursor/slug/category id in `params` |
| `NEVER_PRODUCED` | empty ATS token list, or wrong slug for this profile's stream | populate `ats_boards`, or correct the stream mapping |
| `SYSTEMIC` | **not board rot** — network/proxy/DNS at scan time | none — re-run when connectivity is restored |

## Baseline (build landed)

_2026-07-20 — Platform Health & Self-Healing shipped (PR #52 + #53). **First real review ran the
same day** (borjan-pm, residential IP, 2026-07-20 PM scan) — see the Review log below. Result: 6
`NEVER_PRODUCED` findings, no `SELECTOR_SUSPECT`/`DOWN_STREAK`/`YIELD_COLLAPSE`/`SYSTEMIC`. Notably,
JustRemote + Welcome to the Jungle no longer read as `DOWN_STREAK` (a blocked outage) now that real
`http_ok` telemetry exists — they're `http_ok: true, raw: 0`, i.e. the reached-but-empty shape,
correctly reclassified. Left open for a live-fetch diagnosis (row below)._

## QA findings (pre-production, cloud-IP test scan — not a real review)

_2026-07-20 — a full live `scan.py --profile borjan-pm` run from this build environment (cloud IP,
not Borjan's residential one) proved the telemetry pipeline end-to-end and surfaced two real
findings before any production data existed. **State was restored afterward** (cloud-IP telemetry
doesn't belong in the real baseline) — these are QA notes, not a Layer-2 review row._

- **JustRemote and Welcome to the Jungle answered with a plain HTTP 200 and harvested 0 postings**
  — no connection error at all. Previously read only as `sources_down` (implying a blocked/unreachable
  outage); the real shape is reached-but-empty, i.e. exactly what `SELECTOR_SUSPECT` is designed to
  catch once a rich trailing baseline exists (it's currently reading `NEVER_PRODUCED` instead,
  since the pre-existing history has no runs with `raw > 0` to baseline against — the signal is
  behaving correctly on the data it has). **Re-check on the first real production review**: these
  two may be selector drift, not a bot-wall, and worth a live fetch to confirm.
- **A heal that didn't heal.** Remote Rocketship (worldwide + Europe) escalated direct→headless
  after a `403`, got a real body back, but still harvested **0** candidates — yet the original code
  reported `✚ healed[…]: recovered via headless`, which overstates what happened (reachability, not
  recovery). **Fixed same-day** in `fetch_boards.py`'s `fetch_html_listing`: a heal is now only
  claimed when the escalation *also* recovers ≥1 candidate; otherwise it's logged as `escalated to
  headless for …, still 0 harvested` — an honest non-recovery, not a false heal claim.

## Review log

| Date | Profile | Board | Signal | Live diagnosis | Fix applied | PR |
|------|---------|-------|--------|----------------|-------------|----|
| 2026-07-20 | borjan-pm | Greenhouse / Lever / Workable / Pinpoint HQ (ATS boards) | NEVER_PRODUCED | Not a fault — confirmed config gap: profile's `ats_boards` token lists are genuinely empty for all four (`greenhouse: []`, `lever: []`, `workable: []`, `pinpoint: []`), so there's nothing to fetch yet. `http_ok: true`, `raw: 0` for each, consistent with "no boards configured" (the fetcher's own honest note). | None needed yet — latent coverage opportunity, not rot. Populate `ats_boards` with real company tokens when available (per HEALTH_MONITORING.md "Known current degradations"). | — |
| 2026-07-20 | borjan-pm | JustRemote | NEVER_PRODUCED | **Live-diagnosed across two rounds.** Round 1: fetched the profile's category URL directly and headless; also checked the site's nav for a renamed category (`remote-manager-exec-jobs`) — both 0 postings, just blog/nav links, matching the pre-existing 2026-07-11 quirk (lazy-load-on-scroll, no API channel). Round 2 (Borjan approved a scoped `render.py` policy amendment — see below): re-tested with the new `scroll_rounds` capability, trying both `window.scrollTo` and a real `page.mouse.wheel` event, several rounds each — content size grows slightly (more nav/footer revealed) but **zero real postings surface either way.** | **`render.py` gained a scoped, policy-compliant `scroll_rounds` parameter** (passive `window.scrollTo`/viewport-move only — no click/type/navigation-decision, still returns HTML text for the existing parser, never a screenshot/image/vision step) — a genuine, bounded widening of the 2026-07-11 "structural computer-use ban," approved by Borjan specifically for lazy-load boards. Wired into `fetch_boards.py` as a new `fetch_mode: headless_scroll`. **Deliberately NOT applied to JustRemote's catalog entry** — exhaustive testing shows scroll doesn't fix this specific board (either the category has no live postings right now, or real results need a pagination click, out of scope), so flipping the mode would only add latency for nothing. The capability stays available for a future board where scroll genuinely is the blocker. Quirk note updated with the full test history. | #55 |
| 2026-07-20 | borjan-pm | Welcome to the Jungle | NEVER_PRODUCED | **Live-diagnosed, genuinely new (no prior quirk existed).** Fetched direct + headless for the profile's filtered query URL AND the bare `/jobs` listing with no query at all — **all four return only the marketing/app shell**, 0 job or company links, near-identical byte size regardless of query. No `__NEXT_DATA__`, no embedded Algolia app-id/search-key despite the URL's Algolia-InstantSearch-shaped query params (`refinementList[...][]=`) — the search now appears to run entirely client-side against an endpoint not exposed in page source. This is an architecture change, not a selector/regex fix. | **Quirk note added** to `catalog/platforms.yaml` documenting the finding (no fetch-behavior change — `active: true`/`fetch_mode: direct` unchanged, since a static/snapshot fetch genuinely can't reach the content right now regardless of mode). Flagged as needing either a longer-interaction headless pass (accept cookie-consent, wait for the search XHR) or their internal search API reverse-engineered — left for a future session, not guessed at here. | PR pending |
