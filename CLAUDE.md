# CLAUDE.md — working agreement for this repo

This file is the short list of things that must happen every session — the parts that
quietly rot if left to memory. Detailed context lives in `docs/` per the Docs map below;
the prompt library is `assistant/GUIDED-FLOW.md`.

## Session START protocol (before anything else, every session)

1. **`docs/STATE.md` is already in your context** — the session-start hook injects it
   (with the current git branch/status). It is the single source of truth for current
   build state: active lane, next actions, phase status, open threads. Trust it first.
   If the injection is missing, read `docs/STATE.md` from disk.
2. **Do NOT read `docs/PROGRESS.md` at session start** and do NOT re-explore the repo
   to re-derive state — no repo-wide scans, no Explore subagents for "where are we".
   Read source files only when the step's diff actually touches them.
3. **Report before acting:** current lane + the concrete next step (from STATE), then
   propose the diff for that step — the Verification First guardrail applies (3
   bullets, wait for confirmation). Never redo ✅ steps.
4. **If STATE.md contradicts the repo** (stale row, a ⚑ flag, a step whose diff can't
   be pinned down), SAY SO before proposing anything — name the gap, fix STATE.md
   first. Never silently re-derive state or bluff a plan from stale docs.

## Docs map — what to read when (token discipline)

- **Injected every session:** `docs/STATE.md` (dashboard; small on purpose).
- **On demand, when the step touches them:** `PROJECT_PLAN.md` (vision/scope — source
  of truth for phases), `ARCHITECTURE.md` (design contracts), `PROFILE_CONFIG_SPEC.md`
  (profile schema), the ACTIVE phase plan STATE points at.
- **Task-scoped runbooks — only when doing that task:** `HEALTH_LOG.md` +
  `HEALTH_MONITORING.md` + `PHASE_3_HEALTH_PLAN.md` (health reviews/board audits),
  `ARCHITECTURE_QUALITY_SCOPE.md` (the periodic arch pass), `CUTOVER.md` (cutover),
  `LAPTOP_LANE.md` (attended/unattended laptop runs), `ENFORCEMENT_COVERAGE.md`
  (declared→enforced param map), `PHASE_3A_ACCEPTANCE.md` (3a acceptance record),
  `ANI_FIRST_RUN_FEEDBACK.md` (banked feedback), `BUSINESS_NOTES.md` (GTM/valuation).
- **Outputs, not inputs:** `PLATFORM_GUIDE.md` and `BUILD_AND_FLIP_PLAYBOOK.md` are
  things we WRITE (phase-end refresh / DoD #7). Never read them to derive build state.
- **Append-only history:** `docs/PROGRESS.md` — per-phase checklists + session log.
  Written at session end (DoD #2); at write time read only the section you're
  updating, never the whole file.
- **Archive — never plan of record:** `PHASE_2_PLAN.md` (closed; D1–D23 decision
  reference only). `PHASE_3_PLAN.md` is **SUPERSEDED** — never read it as the Phase 3
  plan; the active plan is whatever STATE.md points at. If unsure which phase doc is
  live, STATE.md decides.

## Definition of done — check BEFORE wrapping up a session

1. **Fold in proven prompts (standing rule).** If a step was *dogfooded / proven* this
   session, fold its tuned prompt into `assistant/GUIDED-FLOW.md` (mark ✅) **in its own
   small PR** — the moment it's proven, not batched at the end. A long session can stop
   at any time; never let a proven prompt sit un-banked in chat. Unproven drafts stay
   out. *(The Stop hook nudges when a branch changed `core/` or `skills/` but not
   GUIDED-FLOW — it only reminds; "did I prove a reusable prompt?" stays part of done.)*
2. **Update the state pair.** (a) Rewrite `docs/STATE.md` — Now / Next / phase rows /
   open threads / Last updated — to match end-of-session reality. (b) Append a session
   row to `docs/PROGRESS.md` (what changed + why) and flip any affected checklist box.
   *(The Stop hook nudges when a branch changed files but not STATE.md.)*
3. **Keep `borjan-pm` behavior honest + the behavioral gate green.** Engine/config
   changes keep the prime directive: `python3 core/validate.py` green (structural) AND
   `python3 tests/run_all.py` green (behavioral), and no unintended change to what
   `borjan-pm` resolves/scans. **Scoped test rule:** adding or changing *behavioral
   logic in `core/`* — a detector, dedup/scoring/normalization helper, or
   sync/reconcile rule — adds or updates a committed check in the same PR: a **unit
   test** (`tests/unit_*.py`) for pure functions, a **sim** (`sims/*.py`) for
   cross-boundary flows. Unit-test the pure logic, sim the boundaries, leave fragile
   fetch/render I/O to honest-failure + health monitoring. Don't chase coverage; cover
   the layer where regressions bite (`tests/README.md`).
4. **Architecture self-review gate ("the Uncle Bob pass").** Before wrapping a PR that
   changes `core/` control flow — new concurrency, a new abstraction/module boundary,
   or non-trivial restructuring (NOT a config tweak or docs-only change) — re-read the
   diff cold, as a stranger's PR, against: SOLID (each piece owns one responsibility;
   policy lives with related policy), DRY (shared helper over duplicated logic), and
   the check that bit us 2026-07-21 — **does every declared constant/comment/log line
   match what the code ACTUALLY enforces?** (a semaphore in one unbounded shared pool
   logged a cap it never enforced; caught only by re-reading cold — PROGRESS
   2026-07-21). Prefer the standard pattern for the problem's shape (e.g. a Bulkhead —
   per-resource-class pools — over an ad hoc semaphore) over whatever compiled first.
   Self-review, not a rewrite pass — fix what's wrong, don't invent scope. No hook
   enforces this; treat it as part of done.
5. **Broader architecture review — periodic, not per-PR (nudged).** #4 spot-checks the
   diff; some quality dimensions (boundary bloat, coupling drift, inconsistent
   patterns, eroding extensibility) only surface from a full-codebase pass. Cadence:
   the scan ledger prints `⚠ architecture review due` when the `arch_review` counter
   in `runs.json` crosses `due_at_sessions` (default 10; `core/arch_review.py`) — the
   nudge is a CUE to ASSESS, never an order to run; weigh real cost/benefit. When due
   and worth it: run as its OWN dedicated session, scope + status tracked in
   `docs/ARCHITECTURE_QUALITY_SCOPE.md` so each pass resumes where the last stopped.
   Verify every finding against real code before acting; fix what's proportionate,
   seed the rest (#8). `python3 core/arch_review.py --ack` resets after a pass (acks
   every profile — one pass covers the shared engine). "Is one due" is a CHECKED
   judgment call, never a skipped one.
6. **No PII in the repo** — no CV body facts, emails, phone numbers, or addresses (the
   3a.8 no-PII denylist enforces the binding files; keep it true everywhere).
7. **Capture build-method lessons (the meta-layer).** If this session taught something
   reusable about *how to build apps* — product-agnostic, not job-scout-specific —
   fold it into `docs/BUILD_AND_FLIP_PLAYBOOK.md`. The transferable asset across apps
   is the **method**. Skip only if nothing generic was learned; don't force it.
8. **Seed unbuildable ideas into the plan of record (never lose feedback).** Anything
   raised this session — feedback, an idea, a gap — that **can't be built now** must be
   **seeded into `docs/PROJECT_PLAN.md`** (the right phase's scope, or the §3x parked
   table) before wrapping — not left only in a side doc or chat. A side-doc capture is
   fine as detail, but the plan of record must *point* to it under a phase. Buildable
   engine follow-ups out of this session's scope get seeded too. The test: *could this
   feedback silently die if no one re-reads this chat? If yes, it isn't seeded yet.*

## Standing rules worth remembering

- **Prime directive:** `borjan-pm` is live production and sacred (full text: STATE.md
  / PHASE_2_PLAN §0a). The frozen `job-scout-pm/` archive stays intact.
- **Human-readable docs step** ends every phase's build (PROJECT_PLAN §4) — refresh
  `docs/PLATFORM_GUIDE.md`.
- **Scripts flag, Claude decides** — mechanical filters flag; the judgment layer
  decides. Never turn a flag into a silent mechanical drop without a deliberate reason
  (task #12's title-scoped hard-drop is the pattern).
- **Notion is the only scanner↔companion bridge**; the scanner never writes the
  Applications Tracker (firewall). Per-profile state isolates under
  `profiles/<id>/state/`.
- **A platform fix generalizes — check it, don't assume it's one-off** (2026-07-21).
  Any fetch/coverage improvement found on one board (undercounted stream coverage, a
  region/scope gap, incomplete pagination) is checked live against every OTHER board —
  already-audited or not — before moving on; an already-"good enough" board gets
  reopened if the check finds something. Full protocol: `docs/HEALTH_LOG.md` "How a
  review works" step 5.

## Compact Instructions

Always preserve:
1. Full test/output logs from the last task executed.
2. Key architectural decisions, current branch goals, pending TODOs, and active test
   failures.
3. Active branch name and target goals.
4. The injected `docs/STATE.md` content (or re-read it after compaction).
5. Any not-yet-banked DoD #7 lesson candidate or DoD #1 proven prompt discussed this
   session — name each explicitly in the summary (better: bank it before compacting;
   the PreCompact hook reminds).

Always drop: raw build logs, long cat outputs, passing test outputs, preceding file
reads, and historical trial-and-error diffs. Summarize chat history down to core
architectural decisions.

## Autonomous Execution Guardrails

- **Verification First:** Before making multi-file changes, state the plan in 3 bullets
  and wait for human confirmation.
- **Terminal Output Limit:** Never pipe full raw logs into chat; redirect large logs to
  `.claude/logs/` and read only the error stack.
- **Subagent Policy:** Use subagents ONLY for isolated research/codebase reads. Do not
  spawn subagents to run nested edits.
