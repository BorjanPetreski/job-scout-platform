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
3. **Keep `borjan-pm` behavior honest.** Engine/config changes must keep the prime directive:
   `python3 core/validate.py` green, and no unintended change to what `borjan-pm` resolves/scans.
4. **No PII in the repo** — no CV body facts, emails, phone numbers, or addresses (the 3a.8
   no-PII denylist enforces the binding files; keep it true everywhere).
5. **Capture build-method lessons (the meta-layer).** Assess whether this session taught something
   reusable about *how to build apps* — a pattern, discipline, or pitfall that is **product-agnostic**
   (not job-scout-specific). If it's valuable, fold it into `docs/BUILD_AND_FLIP_PLAYBOOK.md` (the
   generic framework). The transferable asset across apps is the **method**, not this product — so
   don't let a good lesson evaporate. Skip only if nothing generic was actually learned; don't force it.
6. **Seed unbuildable ideas into the plan of record (never lose feedback).** Anything raised this
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
