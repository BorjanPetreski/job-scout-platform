# Platform Health & Self-Healing — design seed

> **Living design note.** Captured early (2026-07-18) so it compounds: each later phase
> *reinforces* this, and the doc grows with it. **Scheduled as a full build between Phase 3a and
> Phase 3b** (Borjan's call — "fully build this before continuing with 3b"). It follows the same
> pipeline as every build: brainstorm → detailed plan → Fable 5 review gate → Opus 4.8 build.
> Nothing here is built yet; this is the spec seed the build starts from.

## The problem it solves

A job scanner's slowest, most inevitable failure mode is **board rot**: over months, platforms
change their HTML, move endpoints, rename category slugs, add bot-walls, or quietly go dark. Left
unmonitored, coverage erodes and nobody notices until a whole stream stops producing. We want the
engine to **measure its own health continuously and honestly**, and Claude to **diagnose and
repair** on a cadence — before erosion costs real jobs.

## What already protects us (the floor — do not regress)

The engine is built to **fail honest, never fail silent**, and this is already true today:

- Every platform fetch returns `source_down` + a `note`; the scan ledger prints `sources down:
  […]` and surfaces `DEGRADED`/`REGRESSED`/`no boards` notes.
- New/unproven boards are gated (`status: unverified ⇒ active: false`) so a changed board can't
  poison results.
- `validate-platform` (CI) guards the core logic on every change.
- Two telemetry streams already accumulate per profile: **`runs.json`** (per run:
  platforms_covered, sources_down, new/dropped/link_dead, sweep, reconcile) and
  **`fetch_evidence.jsonl`** (per check: url/status/method, appended live).

So a degradation shows up as **visibly reduced coverage**, never as silently-wrong results. That
honest-failure floor is what buys time for the health loop to catch and fix a problem — it must
never be traded away for convenience.

## The gap

Catching degradation today relies on a human noticing the ledger, or a dogfood session happening
to look. There is no trend detection, no proactive signal, and — worst — no detection of the
**silent selector break**: a board returns HTTP 200 with HTML but the parser extracts 0 rows
because the markup changed (`source_down` is `false`, so it hides).

## The design — "scripts flag, Claude decides," applied to health

Same two-layer split as the scan itself.

### Layer 1 — `core/health.py` (mechanical, emits signals)

Reads `runs.json` + `fetch_evidence.jsonl` and computes per-platform trends against a trailing
baseline, emitting severity-flagged findings (JSON report + human summary). Candidate signals:

| Flag | Meaning |
|------|---------|
| `DOWN_STREAK` | `source_down` N runs in a row |
| `YIELD_COLLAPSE` | raw candidate count fell far below its trailing median |
| `SELECTOR_SUSPECT` | fetched OK (200 + HTML) but parsed **0**, historically produced many — the silent break |
| `NEVER_PRODUCED` | active but zero candidates ever logged (Pinpoint/Crossover/Landing/JustRemote today) |
| `SYSTEMIC` | *all/most* platforms at ~zero → a core/network problem, not a board |

Pure Python, no judgment, no network beyond what a scan already does. Additive; changes nothing
the scan fetches/filters/scores/writes.

### Layer 2 — the scheduled Claude "platform health review" (judgment, repairs)

On a cadence, Claude runs `health.py`, and for each flagged board **fetches a live sample and
diagnoses**: selector drift? endpoint moved? slug renamed? new bot-wall? Then proposes/applies the
catalog fix (HARVEST_SPEC, quirk, `fetch_mode`, `active`/`status`) — exactly the repairs the
PROGRESS log shows being done by hand (JustJoin category IDs, Remotive slug, behance/problogger),
but **triggered by a signal instead of by chance**, and always through the catalog/validator (no
ad-hoc scanner edits; prime directive holds).

### The hook — reuse the recompute counter

`runs.json` already carries `recompute.sessions_since` / `due_at_sessions` that prints "⚠ tier
recompute due" every N sessions. A parallel **`health_review_due`** counter rides the same
mechanism: the scan prints "⚠ platform health review due," which is Claude's cue to run the
review. Zero new scheduling infrastructure.

## Cross-cutting — how later phases *buff* this

This is not a one-off; it strengthens as the platform grows:

- **New platforms** ship with a health baseline the moment they go active (so `NEVER_PRODUCED` /
  `YIELD_COLLAPSE` have something to compare against).
- **Multi-profile** health aggregates across profiles — a board failing for everyone is a
  platform problem; failing for one is a config problem.
- **Phase 4 (the app)** surfaces the health report as a real status view for the user/operator,
  and the client-side store keeps the health time-series.
- **Phase 5 (integrations)** extends the same monitoring to email-ingest/OAuth connectors and any
  new data sources — each integration registers its own health signals.
- **The companion (Phase 3+)** benefits indirectly: honest coverage in → honest shortlist out.

## Out of scope (guardrails)

- No auto-editing of scanner *logic* — repairs land in the catalog/config through the validator,
  reviewed like any dogfood fix.
- No new network behavior in Layer 1 beyond reading existing telemetry.
- The honest-failure floor is never weakened to make a board "look healthy."

## Next step

When 3a acceptance closes, open the health build with a brainstorm → detailed plan
(`PHASE_3_HEALTH_PLAN.md` or similar) → Fable 5 review gate → Opus 4.8 build, seeding a checklist
into `PROGRESS.md` at that point (not before — plans go stale).
