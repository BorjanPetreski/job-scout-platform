# Platform Health & Self-Healing — design seed

> **Living design note.** Captured early (2026-07-18) so it compounds: each later phase
> *reinforces* this, and the doc grows with it. **Scheduled as a full build between Phase 3a and
> Phase 3b** (Borjan's call — "fully build this before continuing with 3b"). It follows the same
> pipeline as every build: brainstorm → detailed plan → Fable 5 review gate → Opus 4.8 build.
>
> **BUILD STATUS (2026-07-20): Layers 1 + 1.5 + the Layer-2 cue are BUILT** (Opus 4.8) — see the
> build record **[PHASE_3_HEALTH_PLAN.md](PHASE_3_HEALTH_PLAN.md)**. Shipped: per-platform health
> telemetry in `runs.json` (`platform_stats` with `raw` + `http_ok`), `core/health.py` emitting the
> five signals below, in-scan self-healing (retry-with-backoff + direct→headless escalation, always
> reported), the `health_review_due` counter, `job-scout-run` skill wiring, and
> `tests/unit_health.py`. **Layer 2-runtime** (in-app self-repair) remains a spec for **Phase 4+**
> (needs the embedded LLM). The rest of this doc is the enduring design/vision it was built from.

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

### Known blind spot (found 2026-07-20, during the first real review's follow-up)

`YIELD_COLLAPSE` and `SELECTOR_SUSPECT` both detect a board getting *worse relative to its own
trailing history* — they need a known-good baseline to fall from. A board that has been **quietly
undercounting since before any good baseline was ever recorded** — always "1" or "4" or "6,"
never higher — is invisible to every current signal: it never reads as zero (`NEVER_PRODUCED`)
and it never reads as a collapse (nothing to collapse *from*). Two real examples surfaced by a
manual live audit of every board reporting a small nonzero count in one real scan (see
[HEALTH_LOG.md](HEALTH_LOG.md) "Low-yield sweep"): Himalayas silently capped its own pagination at
20/page while the code assumed 100/page (skipping 80 real jobs between every request — a
4.5x undercount), and Dynamite Jobs rendered most postings as `<h2 href="...">` instead of a real
`<a>` tag, invisible to the harvester's `<a>`-only selector (a 16x undercount). Both fetched `200`,
both reported `source_down: false`, both looked completely healthy to every Layer-1 signal.

**Not yet built, worth a future pass:** a signal for "this board's yield has never been anything
but suspiciously low relative to its tier/expected volume" — independent of trend, since trend is
exactly what this blind spot lacks. Candidate shape: flag any Tier 1/2 board whose yield has
*never once* exceeded some small absolute floor across its whole recorded history, prompting an
occasional live sanity check regardless of whether anything "collapsed." Filed here rather than
built blind — the right floor value depends on real per-platform volume data this build doesn't
have yet.

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

### Layer 1.5 — self-healing (in-scan remediation) (Borjan, 2026-07-18)

Between the mechanical scan and the Layer-2 review, a bounded **self-healing** step that recovers
the *mechanically-recoverable* failures within the same run:

- **Safe to auto-heal:** retry-with-backoff on transient failures; escalate direct→headless fetch
  when a board blocks the plain request; fail over to a known alternate endpoint/mirror.
- **NOT auto-healed (flag for Layer 2):** a selector/endpoint that actually changed, a board to
  activate/deactivate, any catalog-structure edit — these need diagnosis + review, never an
  automatic edit (a wrong auto-edit could silently corrupt results → violates honest-failure).

**Effect:** fewer "sources down" per run, less manual repair, more resilient coverage.
**Guardrails (non-negotiable):** stay conservative; **always report what was healed** ("recovered
X via headless") so the honest-failure signal survives — never silently paper over real rot; and
respect per-host politeness so retries don't read as scraping and trip more bot-walls. Done greedily
it hides the very signals the health loop needs; done conservatively it's a strict win.

### Layer 2-runtime — in-app runtime healing (Borjan, 2026-07-18)

The distinction from Layer 2: Layer 2 is a *dev-side* Claude review that repairs the **shipped
catalog** (fix lands in the next release). **Layer 2-runtime** is the **app healing itself at
run time** — when the app embeds the LLM (Phase 4+), a confirmed degradation triggers an in-app
Claude call that diagnoses the break and produces a repair applied to the **user's own instance**,
so the user gets improved results **immediately, without waiting for an app update.** Doable, and a
direct mitigation of the board-rot maintenance-treadmill risk in BUSINESS_NOTES. Design constraints
(these are what make it safe rather than dangerous):

- **Fetch-layer only.** Runtime repairs may touch selectors / HARVEST_SPEC / URL pattern /
  endpoint / fetch-mode — *never* filters, scoring, eligibility, or judgment. A runtime change to
  what the user *sees as a match* could harm them unseen; getting data off a board can't.
- **Validate-before-adopt.** Run the repaired fetch, check the output is sane (structured,
  plausible count, passes shape checks); adopt the per-user override **only if it validates**,
  else fall back to honest "source down." An unvalidated auto-repair (silently-wrong) is worse
  than honest-failure — never adopt one.
- **Per-user override, reported.** The repair is a local/instance override (the Phase-4
  client-side store), not a repo edit; the app tells the user "auto-repaired X."
- **Bounded COGS.** Fire only on confirmed degradation, rate-limited and cached — never
  re-diagnose the same break every scan. Pairs naturally with BYO-key (§ ARCHITECTURE 7b).
- **Telemetry loop + precedence (the "gets overwritten by better code" model).** Opt-in, good
  runtime repairs flow back so the dev-side Layer 2 folds *vetted* fixes into the shipped catalog
  (all users benefit). Precedence: shipped catalog is the base; a runtime override supersedes it
  for freshness; **a newer shipped fix for that board supersedes/expires the override** — so
  vetted code wins on update and a stale/bad override never persists.

Near-term (the scheduled health build) ships Layer 1/1.5/2; **Layer 2-runtime lands with the app
(Phase 4+)** since it needs the embedded LLM.

### In-app platform settings — user-facing health outcomes (Phase 4) (Borjan, 2026-07-20)

The Layer-1 thresholds (window, down_streak, yield_collapse_factor, min_baseline,
never_produced_min_runs, systemic_frac, due_at_sessions) are **system-wide + immutable — never
user-configurable and never profile-overridable.** Detection sensitivity is a platform-engineering
decision; a user knob there would let someone hide real rot or drown in false alarms. What the app
exposes to the user is the **outcome layer, not the config layer** — a **Platform settings screen**:

- **Per-board analytics** for *this user's* instance: scan count, yield over time (raw + shortlisted),
  live/off status, last-produced date, and the health signals seen (the `platform_stats` time-series
  the client-side store already keeps — § "Phase 4 surfaces the health report as a real status view").
- **Off + reason.** When the health check descopes a board (deemed dead/unrecoverable — a persistent
  DOWN_STREAK/NEVER_PRODUCED that Layer-2 diagnosis couldn't repair), the board is turned **off for
  that user's instance and the user is notified**, with the plain-language reason ("off — unreachable
  8 scans running; last produced 2026-05-02").
- **User re-enable / restart — the override.** The user can switch a descoped board **back on** even
  though the health check turned it off. The motivating case: a board may have yielded nothing simply
  because there were **no openings at that time**, not because it's broken — the user is entitled to
  try it again. Re-enabling **restarts that board's health count** (clears the stale streak/baseline so
  a fresh trial isn't instantly re-flagged by old history) and the trial runs on real data.
- **Precedence — the same "user override, then vetted code wins" model as Layer 2-runtime.** A
  user's forced-on/off choice supersedes the auto-descope for their instance; a later shipped fix
  that actually repairs the board supersedes/expires the override. The descope is a **per-user
  instance state**, never a repo catalog edit — consistent with the honest-failure floor (nothing
  auto-edits scanner config) and the Phase-4 client-side store.

**Engine-side counterpart (buildable before the app).** The "restart a board's health count"
primitive is a pure operation on the telemetry — a per-board restart marker that makes `health.py`
ignore runs before it. The app's re-enable button eventually calls exactly this. Until the app
exists, the same effect is reached in a review by flipping the board's catalog `active`/`status`
through the validator; the restart primitive is parked for when auto-descope (Phase 4) creates
something to restart.

### Known current degradations — health-build seed (2026-07-18)

The first target list for the health build (from borjan-pm's 2026-07-18 PM run, residential IP —
so genuine, not just cloud-IP bot-blocking):

- **Source down:** Remote Rocketship (worldwide), Welcome to the Jungle, JustRemote — 0 raw +
  `source_down`; candidates for `DOWN_STREAK` if it persists. Likely endpoint/bot-wall changes.
- **Degraded:** Remotive — anonymous API is a stub (~41 jobs, params ignored; category HTML masks
  companies). A Tier-1 board running at a fraction of its value; needs a fetcher fix or reroute.
- **Latent coverage (opportunity, not a fault):** Greenhouse / Lever / Workable / Pinpoint ATS
  boards fetch nothing because the profile's `ats_boards` token lists are empty — populate with
  real company tokens for high-quality direct-ATS coverage.
- **NOT degradations (working as designed):** the stream-gated skips (ai-jobs.net, Dribbble,
  ProBlogger, icrunchdata) — a PM profile correctly does not fetch ai-ml/design/content boards.

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
