# CLAUDE.md — working agreement for this repo

Full context lives in `docs/` (PROJECT_PLAN, ARCHITECTURE, PROGRESS, PHASE_*_PLAN) and the
prompt library in `assistant/GUIDED-FLOW.md`. This file is the short list of things that must
happen every session — the parts that quietly rot if left to memory.

## Definition of done — check BEFORE wrapping up a session

1. **Fold in proven prompts (standing rule).** If a step was *dogfooded / proven* this session,
   fold its tuned prompt into `assistant/GUIDED-FLOW.md` (mark ✅) **in its own small PR** — the
   moment it's proven, not batched at the end. A long session can stop at any time, so never let
   a proven prompt sit un-banked in chat. Drafts that aren't proven yet stay out until they are.
   *(Enforced by the Stop hook in `.claude/settings.json`: it nudges when this branch changed
   `core/` or `skills/` but not `GUIDED-FLOW.md`. The hook only reminds — acting on it is still a
   judgment call, so treat "did I prove a reusable prompt?" as part of done.)*
2. **Log the work in `docs/PROGRESS.md`** — a session-log row (what changed + why), and flip any
   affected checklist box.
3. **Keep `borjan-pm` behavior honest + the behavioral gate green.** Engine/config changes must
   keep the prime directive: `python3 core/validate.py` green (structural), **and**
   `python3 tests/run_all.py` green (behavioral), and no unintended change to what `borjan-pm`
   resolves/scans. **Scoped test rule:** when you add or change *behavioral logic in `core/`* — a
   detector, a dedup/scoring/normalization helper, or a sync/reconcile rule — add or update a
   committed check in the same PR: a **unit test** (`tests/unit_*.py`) for pure functions, a **sim**
   (`sims/*.py`) for cross-boundary flows. This is scoped by design — unit-test the pure logic, sim
   the boundaries, and leave the fragile fetch/render I/O to honest-failure + health monitoring (not
   unit tests). Don't chase a coverage number; cover the layer where regressions actually bite (see
   `tests/README.md`).
4. **Architecture self-review gate ("the Uncle Bob pass").** Before wrapping a PR that changes
   `core/` control flow — new concurrency, a new abstraction/module boundary, or non-trivial
   logic restructuring (NOT a config tweak, NOT a docs-only change) — re-read the diff cold, as
   if reviewing a stranger's PR, against: SOLID (does each piece own one responsibility — policy
   lives in the module that already owns related policy, not wherever was convenient to write),
   DRY (duplicated logic instead of a shared helper), and the boring check that actually bit us
   2026-07-21 — **does every declared constant/comment/log line match what the code ACTUALLY
   enforces?** (a semaphore inside one unbounded shared pool logged a concurrency cap it never
   enforced; caught only by asking "is this done properly" and re-reading cold, not by having
   thought about it while writing it — see `docs/PROGRESS.md` 2026-07-21). Prefer the standard
   pattern for the shape of the problem (e.g. a Bulkhead — dedicated per-resource-class pools —
   over an ad hoc semaphore workaround) over whatever compiled first. This is a self-review, not
   a rewrite-everything pass — fix what's actually wrong, don't invent scope. No hook enforces
   this (unlike #1's GUIDED-FLOW nudge — "did this PR restructure core/ logic?" isn't
   mechanically detectable); treat it as part of done the same way.
5. **Broader architecture review — periodic, not per-PR (scheduled check).** DoD #4 is a
   per-PR spot-check on the diff in front of you; some architectural quality dimensions never
   show up in any single diff (module boundaries growing too large, coupling drifting, a
   design pattern applied inconsistently across the codebase, extensibility eroding) and only
   surface from a full-codebase pass. At natural checkpoints — a phase closing, or roughly
   every 10 sessions that touched `core/` since the last full pass, whichever comes first —
   **ask whether one is due.** Running it is a judgment call weighed against real cost/benefit
   (a quiet, small, or recently-reviewed codebase may not need one) — never automatic busywork
   for its own sake. When due and worth it: scope + run it as its OWN dedicated session (never
   squeezed into an unrelated PR), scope and status tracked in
   `docs/ARCHITECTURE_QUALITY_SCOPE.md` so each pass picks up where the last one left off
   instead of re-scoping from scratch or silently re-covering the same ground. Same discipline
   as #4 applies to the pass itself: verify every finding against the real code before acting,
   fix what's proportionate, seed the rest (#8 below) rather than force it into one session.
   The cadence is now NUDGED (added 2026-07-21): the scan ledger prints `⚠ architecture review
   due` once the `arch_review` counter in `runs.json` crosses `due_at_sessions` (default 10),
   riding the same rails as the health-review/recompute nudges (`core/arch_review.py`) — so "is
   one due?" is prompted, not left to memory. The nudge is a CUE to ASSESS, never an order to
   run: running the pass stays a judgment call weighed against real cost/benefit, and
   `python3 core/arch_review.py --ack` resets the counter after a pass (acks every profile — one
   pass covers the shared engine). Treat "is one due" as part of done the same way as #4 — a
   judgment call, but a CHECKED (and now nudged) one, not a skipped one.
6. **No PII in the repo** — no CV body facts, emails, phone numbers, or addresses (the 3a.8
   no-PII denylist enforces the binding files; keep it true everywhere).
7. **Capture build-method lessons (the meta-layer).** Assess whether this session taught something
   reusable about *how to build apps* — a pattern, discipline, or pitfall that is **product-agnostic**
   (not job-scout-specific). If it's valuable, fold it into `docs/BUILD_AND_FLIP_PLAYBOOK.md` (the
   generic framework). The transferable asset across apps is the **method**, not this product — so
   don't let a good lesson evaporate. Skip only if nothing generic was actually learned; don't force it.
8. **Seed unbuildable ideas into the plan of record (never lose feedback).** Anything raised this
   session — user feedback, an idea, a gap you found — that **can't be built now** (needs a later
   phase, the app, an integration that doesn't exist yet) must be **seeded into `docs/PROJECT_PLAN.md`**
   (the right phase's scope, or the §3x parked table) before wrapping — not left only in a side doc or
   in chat. A side-doc capture (e.g. a feedback file) is fine as the detail, but the plan of record must
   *point* to it under a phase so it actually gets built. If it's an engine follow-up that's buildable
   but out of this session's scope, seed it too (parked table or the relevant PHASE plan). The test:
   *could this feedback silently die if no one re-reads this chat? If yes, it isn't seeded yet.*

## Standing rules worth remembering
- **Human-readable docs step** ends every phase's build (PROJECT_PLAN §4) — refresh
  `docs/PLATFORM_GUIDE.md`.
- **Scripts flag, Claude decides** — mechanical filters flag; the judgment layer decides. Don't
  turn a flag into a silent mechanical drop without a deliberate reason (see task #12's
  title-scoped hard-drop for the pattern).
- **Notion is the only scanner↔companion bridge**; the scanner never writes the Applications
  Tracker (firewall). Per-profile state is isolated under `profiles/<id>/state/`.
- **A platform fix generalizes — check it, don't assume it's one-off** (2026-07-21). Any
  fetch/coverage improvement found on one board (undercounted stream coverage, a region/scope
  gap, incomplete pagination) is checked live against every OTHER board — already-audited or
  not — before moving on, and an already-"good enough" board gets reopened if the check finds
  something. Full protocol + the pattern checklist: `docs/HEALTH_LOG.md` "How a review works"
  step 5.
