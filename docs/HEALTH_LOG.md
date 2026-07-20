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
| 2026-07-20 | borjan-pm | JustRemote | NEVER_PRODUCED | **FIXED — the lazy-load diagnosis was wrong.** Two dead-end rounds first: (1) direct+headless on the profile's category URL, plus the renamed-category theory (`manager-exec`) — both showed 0 postings, seemingly confirming the pre-existing 2026-07-11 lazy-load quirk; (2) after Borjan approved a scoped `render.py` `scroll_rounds` capability, re-tested with `window.scrollTo` and a real `mouse.wheel` event — still 0. **Borjan then asked to check `https://justremote.co/remote-jobs` directly** — that surfaced the real cause: their nav dropped the "project-management" category (successor is `manager-exec`), AND postings now use a relative href with no leading slash (`remote-manager-exec-jobs/product-owner-...`) instead of the old absolute `/remote-jobs/{category}/{slug}` — the `HARVEST_SPEC` regex never matched it, so every prior check silently harvested 0 regardless of whether content existed. Plain headless (no scroll needed at all) now yields real postings. | **Two-part catalog fix**: (1) `categories.project-management` updated from `project-management` to `manager-exec`; (2) `HARVEST_SPECS['justremote']` regex updated to match the new relative href shape (`min_hyphens: 2` filters out nav noise like `remote-jobs/new`). **Verified live end-to-end**: `raw: 17, source_down: False, http_ok: True`, incl. genuinely PM-adjacent roles ("Principal Product Manager, AI Custom Models" @ Gitlab, "Product Owner, D365 Finance & Operations" @ Nutrafol). 0/17 happened to keyword-match borjan-pm's specific PM/Scrum-Master title set *this run* — expected (small, mixed-bag category; today's snapshot just didn't have one), not a bug — keyword substring-matching on the concatenated title was independently confirmed still correct. **Known minor cosmetic issue** (not blocking): company + title concatenate without a separator (two adjacent DOM elements, no whitespace between them) — doesn't affect dedup (URL-keyed) or keyword matching; left as a documented quirk rather than building a bespoke parser unprompted. The `scroll_rounds` capability from round 2 turned out not to be the actual fix here, but stays built for a genuine future lazy-load case. | #55 |
| 2026-07-20 | borjan-pm | Welcome to the Jungle | NEVER_PRODUCED | **Live-diagnosed, genuinely new (no prior quirk existed).** Fetched direct + headless for the profile's filtered query URL AND the bare `/jobs` listing with no query at all — **all four return only the marketing/app shell**, 0 job or company links, near-identical byte size regardless of query. No `__NEXT_DATA__`, no embedded Algolia app-id/search-key despite the URL's Algolia-InstantSearch-shaped query params (`refinementList[...][]=`) — the search now appears to run entirely client-side against an endpoint not exposed in page source. This is an architecture change, not a selector/regex fix. | **Quirk note added** to `catalog/platforms.yaml` documenting the finding (no fetch-behavior change — `active: true`/`fetch_mode: direct` unchanged, since a static/snapshot fetch genuinely can't reach the content right now regardless of mode). Flagged as needing either a longer-interaction headless pass (accept cookie-consent, wait for the search XHR) or their internal search API reverse-engineered — left for a future session, not guessed at here. | PR pending |
