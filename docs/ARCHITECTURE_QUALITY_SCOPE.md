# Architecture Quality Scope — the full pass, and what's already covered

> Companion to [CLAUDE.md](../CLAUDE.md) DoD #4 (per-PR self-review) and #5 (this doc's
> periodic, whole-codebase pass). #4 catches "does this diff do what it claims." This doc
> scopes the broader question #4 structurally can't reach: "is the codebase's design still
> sound as a whole" — module boundaries, the SOLID letters beyond Single Responsibility,
> design-pattern fit, coupling/cohesion, extensibility, naming, performance, testing
> strategy, security posture. Run as its OWN dedicated session when due (DoD #5), not
> squeezed into an unrelated PR.

## Status

**Second full pass ran 2026-07-21** (Opus 4.8, branch `claude/architecture-quality-review-ywgw58`)
— the dedicated session that executed all 9 sections below. See `docs/PROGRESS.md` 2026-07-21 for
the write-up. Method mirrored the first pass: re-measured `core/` (6,039 lines / 20 files, up from
~5,900), split into 4 file-groups + 2 whole-system groups, ran 6 parallel research agents each given
the SPECIFIC section text below (not "find problems"), then **independently re-verified every finding
against the real code before acting** — which caught the pass's false positive (an agent claimed a
`zł`-suffixed PLN salary is mis-parsed as USD ~4x; empirically it parses to `None`/unparseable = the
safe side, the dead `_CUR_SYMBOL['zł']` map entry is merely unreachable). All 9 sections are now
**covered**:

1. **SOLID beyond SRP** — Open/Closed, DIP, Liskov/ISg traced across the functional codebase. Verdict:
   the `(p,cfg)->dict` fetcher contract + `_ok`/`_down`/`_cand` constructors are clean; OCP costs
   (new fetch mechanism = new `HANDLERS` fn; new filter TYPE = engine change) are real but acceptable
   at current size, documented under §5. No OOP-shaped violations (mostly N/A by design, stated
   explicitly).
2. **Design-pattern fit** — Strategy/dispatch (`HANDLERS`), fault-isolation (`fetch_platform`),
   Bulkhead (`fetch_many`), post-write-verify (`_patch_verified`) all sound. Anti-patterns found:
   the seen-record 11-field literal duplication (FIXED via `dedup.make_seen_record`), stringly-typed
   status/reason/vocab (partly FIXED — `dedup.STATUSES` hoisted; Notion vocab seeded).
3. **Module boundary / file-size** — `scan.py` (888) + `notion_sync.py` (667) are the split
   candidates; `run_scan` God-function + detector-extraction seeded (production-path, deferred).
4. **Coupling/cohesion** — built the full import/call graph: clean DAG, no cycles, `paths` base →
   `profile_loader` hub → `dedup` mid-layer. Real coupling is data-shape, not imports (seen-record
   contract FIXED; enriched-candidate schema + `source_url`-in-sweep seeded; `dedup.unsynced` dead
   code seeded).
5. **Extensibility** — stress-traced two concrete scenarios (GraphQL/auth platform; non-regex filter
   type). "Config not code" holds for values/regex/strategy-choice, breaks at the "new KIND of thing"
   boundary; `HARVEST_SPECS`→catalog is the highest-leverage fix (seeded).
6. **Naming/consistency** — `_private` prefix, verb-noun, docstring depth all principled. Minor: `norm_*`
   vs `normalize_*`, duplicated `UA` string, mid-file constant placement (notes only).
7. **Performance** — dedup match is O(n+m) (confirmed, not regressed); config regex compiles once at
   load (confirmed). The one real per-candidate hot spot (`stated_language_requirement`'s 26 full-JD
   scans rebuilding patterns) FIXED via module-level precompile; three cache-mitigated minor ones
   seeded.
8. **Testing-architecture** — `salary.py` (pure scoring driving a hard filter, ZERO tests) and the
   `state_sync` mergers were the real gaps: both CLOSED this PR (`unit_salary.py`, extended
   `unit_state_sync.py`). Sim-fidelity risks (single-page fakes can't catch pagination bugs; rich_text
   round-trip un-modeled) seeded.
9. **Security** — traced JD/API external input end-to-end into paths (hashed → no traversal),
   subprocess (git list-form, no shell → no injection), Notion API structure (inert typed values,
   fixed endpoints → no structure injection), and tokens (never logged/persisted). **No exploitable
   injection path in any sink.** One low-severity note: `last_run_candidates.json` git-commits 1500
   chars of truncated *public* JD text (not PII/secrets) — acceptable, noted.

**Outstanding after this pass** (all seeded into PROJECT_PLAN.md §3x — nothing lost): the Notion
sync/reconcile hardening bundle (deferred — live daily-critical path), `scan.py` decomposition
(deferred — production orchestrator), candidate-schema + sweep-source_url, test/sim-fidelity
hardening, `HARVEST_SPECS`→catalog, and the minor perf/consistency bundle. These are follow-up WORK
items, not un-covered DIMENSIONS — every section above was actually executed. The next *full* pass
isn't due until the codebase materially grows again (DoD #5's cadence); the seeded items are ordinary
engine follow-ups, buildable without re-scoping.

**First full pass ran 2026-07-21** (Sonnet 5, branch `claude/commit-9184cee-orphaned-6isb5r`,
PR #61) — see `docs/PROGRESS.md` 2026-07-21 "Full `core/` architecture regression pass" for
the write-up. That pass covered:
- The "boring check" (does every declared constant/comment/log line match what the code
  enforces) — thoroughly, and it's where every real bug came from.
- DRY — found real duplication, documented + deferred the fix (see PROJECT_PLAN.md's parked
  table), didn't refactor.
- Single Responsibility (one SOLID letter) — lightly, as "is this policy in the right
  module," not a rigorous per-function audit.
- Resource/concurrency safety — thoroughly (it was the live trigger).
- One named invariant (the Notion Tracker firewall) — verified end-to-end.

The 9 sections below were **explicitly NOT covered by the first pass** and became the scope of the
second (2026-07-21) pass above; they remain the section briefs a future pass re-runs against a
materially larger codebase:
1. SOLID: Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
2. Design-pattern fit (deliberate catalog check, not incidental)
3. Module boundary / file-size appropriateness
4. Coupling/cohesion at the whole-system level
5. Extensibility (stress-tested, not assumed)
6. Naming/consistency conventions
7. Performance / algorithmic complexity
8. Testing-architecture strategy (separate from DoD #3's per-PR coverage rule)
9. Security posture beyond individual ad-hoc checks

Update this doc's Status section after each full pass — what ran, what it covered, what's
still outstanding — so the next one picks up where this one left off instead of re-scoping
from scratch or silently re-covering the same ground.

---

## How to run it (same discipline as 2026-07-21, don't skip these)

1. **Split the codebase into groups sized for parallel research agents** — `core/` was ~5,900
   lines across 20 files in July 2026; re-measure (`wc -l core/*.py`) and re-split by logical
   area, not a fixed file list (the codebase has grown since).
2. **One agent per group, one section below (or a cluster of sections) per agent** — give each
   agent the SPECIFIC section text below, not just "review this file." A vague "find
   architecture problems" prompt produces vague findings; a scoped question produces
   demonstrable ones.
3. **Independently re-verify every finding against the real code before acting** — the
   2026-07-21 pass caught 2 false positives this way (an agent flagged a validation
   inconsistency that turned out to have a legitimate reason once the surrounding code was
   read). Never fix something a sub-agent claimed without reading the actual lines yourself.
4. **Fix what's proportionate; seed the rest** — a finding that needs a big refactor or
   touches live-production-critical paths (Notion sync, borjan-pm's daily run) gets scoped and
   documented into `PROJECT_PLAN.md`'s parked table (DoD #8), not rushed into the same PR just
   because it was found today.
5. **Every fix needs the same rigor as any other core/ change** — `core/validate.py` +
   `tests/run_all.py` green, a unit test or sim for new/changed behavioral logic (DoD #3), and
   this doc's own gate (DoD #4) applied to the fixes themselves before wrapping.
6. **Ack the cadence counter when done** — after a pass runs, `python3 core/arch_review.py --ack`
   resets the `arch_review` "review due" counter in every profile's `runs.json` (the nudge that
   printed `⚠ architecture review due` in the scan ledger, added 2026-07-21). Skipping the ack
   just means the nudge keeps firing; running it without having done a real pass is lying to your
   future self — so ack only after actually completing one, alongside updating this Status section.

---

## 1. SOLID beyond Single Responsibility

This codebase is mostly functional Python (module-level functions, a few dispatch dicts like
`fetch_boards.HANDLERS`) rather than class hierarchies — Liskov Substitution and Interface
Segregation may genuinely not apply in their classic OOP form. **Don't assume that and skip
them — test it.** Look for:
- **Open/Closed:** does adding a new platform, template, or hard-filter type require editing
  existing dispatch logic (`fetch_platform`'s `if/elif` chain, `hard_filter`'s pattern loop),
  or does it plug in without modifying working code? Where it doesn't, is that a real cost or
  an acceptable tradeoff for this codebase's size?
- **Dependency Inversion:** do lower-level modules (`fetch_boards.py`) ever reach up into or
  assume things about higher-level orchestration (`scan.py`) rather than the other way
  around? Any concrete dependency on a specific caller's shape, not an abstraction?
- **Liskov/Interface Segregation:** genuinely check whether these apply anywhere (any
  duck-typed "interface" this codebase leans on, e.g. every `fetch_*` function's implicit
  `(p, cfg) -> dict` contract, or every hard-filter's implicit shape) — and if a violation is
  found, report it; if truly inapplicable, say so explicitly rather than silently skipping.

## 2. Design-pattern fit (catalog what's there, evaluate it, don't assume it's good)

Patterns ALREADY informally in use, worth evaluating deliberately rather than incidentally:
- `fetch_boards.HANDLERS` — a dispatch-table / Strategy pattern. Well-applied? Any platform
  that doesn't cleanly fit the `(p, cfg) -> dict` contract and is faking it?
- `fetch_platform`'s per-platform try/except — a fault-isolation pattern (bulkhead-adjacent,
  distinct from the concurrency Bulkhead added 2026-07-21). Consistent across every call site
  that needs it?
- The 2026-07-21 concurrency Bulkhead (`fetch_boards.fetch_many`) — now that it's had time to
  run for real, does the split (headless pool / HTTP pool) still make sense, or has the
  platform mix shifted?
- Also look for **anti-patterns**: a God object/module doing too much (candidate: `scan.py`
  at 885 lines — see §3), feature envy (a function that mostly operates on another module's
  data), primitive obsession (stringly-typed states where a small enum/constant set would be
  safer — e.g. the `status` field in `dedup.py`'s `seen.jsonl` records).

## 3. Module boundary / file-size appropriateness

`core/scan.py` (885 lines) and `core/fetch_boards.py` (797 lines) were the two largest files
as of 2026-07-21 — re-measure, they may have grown. For each oversized file, ask: is there a
natural seam it should split along? Candidate seams to evaluate (not prescriptions — verify
each actually reduces coupling rather than just moving lines around):
- `scan.py`: the pure detector functions (`detect_language`, `detect_seniority`,
  `detect_employment`, `detect_work_arrangement`, `stated_language_requirement`,
  `start_date_passed`) vs. the orchestration (`run_scan`, the CLI). These are already
  unit-tested in isolation (`tests/unit_detectors.py`) — do they need to physically live in
  the same file as the orchestrator that calls them?
- `fetch_boards.py`: the `HANDLERS`-dispatched API fetchers vs. the generic
  `fetch_html_listing`/render escalation path vs. the concurrency orchestration
  (`fetch_many`/`_is_headless_platform`, added 2026-07-21) — three fairly distinct
  responsibilities currently in one file.
- Any other file that's grown past ~500 lines since 2026-07-21 — re-run `wc -l core/*.py` and
  check.

A file's size alone isn't a defect — only split where it demonstrably reduces coupling or
improves testability; don't split for a line-count target.

## 4. Coupling/cohesion at the whole-system level

Build (even informally) a real import/call graph across `core/*.py` — who imports whom, who
calls into whose internals (not just public functions). Look for:
- Circular or surprising dependencies (does anything low-level end up depending on something
  high-level, even indirectly through a shared helper?).
- Modules that know too much about each other's internal data shapes rather than going
  through a clean interface (e.g. does `scan.py` construct raw dicts matching
  `fetch_boards.py`'s internal candidate shape rather than using a shared constructor?).
- High-cohesion check: does each module's actual set of functions genuinely belong together,
  or has anything drifted in that belongs elsewhere (e.g. does `dedup.py` contain anything
  that isn't really about dedup semantics)?

## 5. Extensibility (stress-tested, not assumed)

The system's stated design goal (PROFILE_CONFIG_SPEC.md, ARCHITECTURE.md) is that new
platforms/streams/templates plug in via config, not engine-code changes. Actually trace one
concrete scenario end-to-end rather than assuming the goal holds:
- Pick a plausible new platform with an UNUSUAL fetch shape (e.g. GraphQL-only, or requiring
  a multi-step auth handshake) and trace exactly what would need to change. Does it fit the
  existing `HANDLERS`/`fetch_mode` model, or would it force an engine-code change disguised as
  "just a new fetcher"?
- Pick a plausible new stream/template with an unusual hard-filter need (something not already
  expressible via `hard_filters`' existing keys) and trace the same way.
- Report honestly where the "config not code" promise holds and where it quietly doesn't.

## 6. Naming/consistency conventions

Deliberately excluded from the 2026-07-21 pass ("don't report naming preferences" — correct
for a bug hunt, but left this genuinely unchecked). A real pass here means:
- Function/variable naming pattern consistency across `core/*.py` (verb-noun conventions,
  `_private` prefix consistency, abbreviation consistency).
- Module-level constant naming/organization (are related constants grouped consistently
  across files the way `fetch_boards.py`'s concurrency constants are, or scattered
  differently per file?).
- Docstring format/depth consistency — some functions here carry paragraph-length historical
  narrative docstrings (deliberate house style, per CLAUDE.md's own voice), others have none;
  is that split principled (public API vs. internal helper) or arbitrary?

## 7. Performance / algorithmic complexity

Not evaluated at all in the first pass. Spot-check the hot paths against realistic data
volumes (`borjan-pm`'s `seen.jsonl` is 1,300+ records and growing):
- `dedup.py`'s match logic — is `load_seen()`'s by-url/by-key dict construction still O(n)
  and the match itself O(1), or has anything crept in that's O(n) per candidate (which would
  make a full scan O(n*m))?
- `profile_loader.py`'s config compilation — any regex compilation happening per-candidate
  inside the hot scan loop that should be hoisted to compile once?
- The concurrency work (2026-07-21) changed fetch TIMING — re-check whether the
  keyword/hard-filter pass over `survivors` in `scan.py` scales reasonably as candidate counts
  grow with deeper `--full-sweep --gap-hours` runs.

## 8. Testing-architecture strategy

Separate question from DoD #3's per-PR "did this specific change get a test." Ask instead:
does the CURRENT test suite (9 targets as of 2026-07-21 — re-count) structurally cover the
riskiest surfaces, or are there systemic blind spots?
- Is there a class of bug the suite structurally cannot catch (e.g. anything only observable
  under real network/timing conditions, or a whole module with zero coverage)?
- Are the `sims/` (cross-boundary, mocked Notion) fixtures kept realistic as the real API
  contract evolves, or do they risk drifting stale and passing against a fake that no longer
  matches reality? (The 2026-07-21 pass found exactly this — two existing sims had fake-Notion
  fixtures that were already slightly unfaithful, only surfaced because a NEW check exposed
  the gap. Are there other stale-fixture risks waiting the same way?)

## 9. Security posture beyond individual ad-hoc checks

The first pass checked `secrets.py`'s resolution order in isolation. A real pass traces data
flow end-to-end:
- External input handling: fetched JD text and platform API responses flow into Notion writes
  and local file paths — any injection-adjacent risk (e.g. could adversarial JD content ever
  influence a file path, a shell command, or a Notion API call structure rather than just
  being stored as inert text)?
- Path-traversal-shaped risks anywhere a profile ID or similar identifier crosses into a file
  path (`profiles/<id>/state/...`) — is `<id>` ever attacker-influenced, and if so, validated?
- Anything logging or persisting more than it needs to (the no-PII discipline, DoD #6, is
  about content; this is about accidental over-capture in logs/telemetry/error messages).
