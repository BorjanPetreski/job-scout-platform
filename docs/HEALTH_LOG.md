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

_2026-07-20 — Platform Health & Self-Healing shipped (PR #52). No live review run yet; the first
real scan writing `platform_stats` seeds the baseline. Known standing degradations from the
[HEALTH_MONITORING.md](HEALTH_MONITORING.md) seed to confirm on the first review: JustRemote +
Welcome to the Jungle (DOWN_STREAK in borjan-pm history), Remotive (DEGRADED stub), and the empty
ATS token lists (Greenhouse/Lever/Workable/Pinpoint → NEVER_PRODUCED candidates)._

## Review log

| Date | Profile | Board | Signal | Live diagnosis | Fix applied | PR |
|------|---------|-------|--------|----------------|-------------|----|
| _(none yet — first review pending the first scan with health telemetry)_ | | | | | | |
