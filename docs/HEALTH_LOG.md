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
| 2026-07-20 | borjan-pm | Welcome to the Jungle, JustRemote | NEVER_PRODUCED | **Open — worth a live fetch.** First real (residential-IP) telemetry: both now show `http_ok: true, raw: 0` — a clean request that returns nothing, not a blocked/unreachable outage. This is a reclassification from what pre-build telemetry looked like (previously read only as a `sources_down` outage); with `http_ok` now recorded, it's visibly the reached-but-empty shape. Not yet diagnosed live — could be selector drift (their markup changed under `HARVEST_SPEC`) or a bot-wall that still returns a 200 shell page. **Next review: fetch each board's listing URL directly and inspect the HTML** to tell those two apart. | Pending — no catalog change made yet. | — |
