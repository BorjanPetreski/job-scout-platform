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
5. **No PII in the repo** — no CV body facts, emails, phone numbers, or addresses (the 3a.8
   no-PII denylist enforces the binding files; keep it true everywhere).
6. **Capture build-method lessons (the meta-layer).** Assess whether this session taught something
   reusable about *how to build apps* — a pattern, discipline, or pitfall that is **product-agnostic**
   (not job-scout-specific). If it's valuable, fold it into `docs/BUILD_AND_FLIP_PLAYBOOK.md` (the
   generic framework). The transferable asset across apps is the **method**, not this product — so
   don't let a good lesson evaporate. Skip only if nothing generic was actually learned; don't force it.
7. **Seed unbuildable ideas into the plan of record (never lose feedback).** Anything raised this
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
