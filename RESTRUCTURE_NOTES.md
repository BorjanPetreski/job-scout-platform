# Session-lifecycle restructure — what changed and why

Drop-in bundle for `job-scout-platform` (based on main @ 2026-07-21, PR #69). Every file
keeps its repo-relative path — unzip over the repo root on a branch and review the diff.

## The problem being fixed

1. **Session-start token burn.** `docs/PROGRESS.md` (171KB ≈ 43K tokens) self-declared
   as "read FIRST on any session start" — but ~145KB of it is the append-only session
   log, pure history. Every session paid ~40K tokens to learn ~1K tokens of state.
2. **State rot.** Current state lived as prose banners inside that log. Editing a huge
   file's narrative is exactly what gets skipped: the banner still said "NEXT: build
   3a.1–3a.10" while the checklist below showed all of 3a ✅ complete (2026-07-19); the
   phase table said Phase 1 "cutover pending" vs the README's "cutover 2026-07-14";
   row 3a.7 said "ani: not yet run" vs the stage table's "portability passed 07-19".
3. **README stale** (pre-3a status; 6 of 19 docs listed) and the Stop hook logic was an
   unmaintainable inline one-liner.

## The fix — a closed state loop

**INITIATE** → SessionStart hook installs deps (unchanged) AND injects `docs/STATE.md`
+ git branch/status into context. Sessions open oriented for ~1K tokens; no manual
reads, no re-exploration, PROGRESS.md never loaded.
**DRIVE** → CLAUDE.md gains a Session START protocol (trust STATE; don't read PROGRESS
at start; report lane + propose diff + wait; flag contradictions) and a tiered Docs map
covering all 19 docs (on-demand / task-scoped / outputs-not-inputs / archive-never-
plan-of-record, incl. the superseded PHASE_3_PLAN hazard).
**COMPLETE** → DoD #2 becomes "update the state pair" (rewrite STATE.md + append the
PROGRESS row). The Stop hook now nudges BOTH the GUIDED-FLOW fold-in (existing) and a
missing STATE.md update (new).

## Files in this bundle

| File | Change |
|---|---|
| `docs/STATE.md` | **NEW** — the dashboard: Now / Next / phase status / open threads / standing constraints. Seeded from actual repo state; two ⚑ reconciliation flags for you to confirm (Phase 1 cutover closure; the 3a.7 note correction). |
| `CLAUDE.md` | Rewritten: + Session START protocol, + Docs map, DoD #2 now updates the state pair, compact-instructions cleanup (+ preserve injected STATE after compaction). **All 8 DoD rules, standing rules, and guardrails preserved** — prose tightened, no rule dropped. |
| `docs/PROGRESS.md` | Header replaced (now: append-only history, not a session-start read; phase table moved to STATE.md). **Checklists + session log preserved byte-identically** except one grounded fix: 3a.7's stale "ani portability: not yet run" → "PASSED 2026-07-19" per the stage table + session rows. |
| `.claude/hooks/session-start.sh` | Extended: deps logic unchanged + STATE.md/git context injection (with a loud fallback if STATE.md is missing). |
| `.claude/hooks/stop-check.sh` | **NEW** — the Stop one-liner moved to a maintainable script + the STATE-not-updated nudge + the always-on DoD #7 lesson-assessment nudge (fires on any changed branch not covered by the core/skills nudge and not touching the playbook; "no generic lesson" is a valid answer, silence isn't). |
| `.claude/hooks/pre-compact.sh` | **NEW** — PreCompact hook (manual + auto): last-moment reminder to bank un-folded DoD #7 lessons / DoD #1 prompts before compaction summarizes them away. Paired with Compact-Instructions preserve item 5 as the parachute if the reminder is ignored. Cannot block compaction; exits 0. |
| `.claude/settings.json` | Hooks now reference the two scripts. Permissions untouched. |
| `claude-settings.example.json` | Synced with settings.json (hooks added, sync note added). Permissions untouched. |
| `docs/BUILD_AND_FLIP_PLAYBOOK.md` | DoD #7 fold-in (3 anchored edits, rest byte-identical): §1's session-resume contract revised to the state/history split closed by hooks; §A skeleton entry updated to the STATE+PROGRESS pair ("adopt the split from day one"); §F gains the session-lifecycle kit bullet + the hook-detectability caveat. |
| `README.md` | De-staled (3a complete, health lane active, 3b next), full layout (assistant/, tests/, sims/), complete tiered docs list, Claude-session pointer. |

## After merging — small manual follow-ups

1. `chmod +x .claude/hooks/*.sh` (zip may not preserve the execute bit).
2. Confirm the two ⚑ flags in STATE.md, then delete them.
3. Optional but recommended: `git mv docs/PHASE_3_PLAN.md docs/archive/PHASE_3_PLAN.md`
   — the banner + docs map guard it, but a filename that can't be mistaken for the
   active Phase-3 plan survives context compaction better than any instruction.
4. The SessionStart injection also fires for unattended scan sessions (~1K tokens of
   harmless orientation). If you ever want scans leaner, gate the injection on an env
   var — not done here to keep behavior uniform.

## Expected effect

Session start drops from ~45K tokens (CLAUDE.md + full PROGRESS read) to ~4K
(CLAUDE.md + injected STATE) — roughly 40K tokens saved per session, plus no
re-exploration, and state that can't silently rot because the Stop hook checks it and
the next session's injected STATE surfaces any lie immediately.
