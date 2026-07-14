# Cutover Runbook — legacy `job-scout-pm/` → `core/` engine (Phase 1 step 1.12)

> The deliberate, reversible switch that makes `core/scan.py --profile borjan-pm` the
> production scanner and freezes the legacy skill. Ordered so the live schedules never
> scan against stranded state. Do this in one coordinated pass with Borjan present.

Status: **prerequisites done** (Phase 1 merged; branch-protection bypass + `Validate
platform` required check added 2026-07-13). Ready to run when Borjan is.

## Preconditions (all met)

- [x] Phase 1 merged to `main` (PR #9).
- [x] `main` ruleset: admin bypass added (never hard-blocked by a missing check again);
      `Validate platform (core + catalog + templates + profiles)` added as a required check.
- [x] `profiles/borjan-pm/references/` populated (pitching.md, gemini-prompt.md) — the
      run skill's pitch router resolves.
- [ ] Confirm `NOTION_TOKEN` is set in the cloud environment (unchanged from v3).

## Ordered switch (coordinated — some steps are Borjan-only)

1. **Quiesce legacy schedules.** Borjan: pause BOTH the laptop scheduled task and the
   cloud Routine(s) that fire the v3 scan. Nothing may write legacy state after this
   point, or the final copy in step 2 will miss it.
2. **Final state sync.** `python3 core/migrate_state.py` (idempotent union-merge — safe
   even if nothing changed since the build). Commit the result:
   `git add profiles/borjan-pm/state && git commit -m "cutover: final legacy state copy"`.
   Verify the seen.jsonl record count matches or exceeds the build-time 765.
3. **Re-point the schedules to the new prompt.** Both lanes fire:
   `Run the job scout AM|PM scan for borjan-pm per skills/job-scout-run/SKILL.md.
   Unattended mode.`
   - Laptop scheduled task — **Borjan edits** (its command/prompt).
   - Cloud Routine(s) — Claude may update if it has access to the Routine tooling;
     otherwise Borjan re-points them.
   - Copy `claude-settings.example.json` → `.claude/settings.json` at the repo root on
     the laptop (permissions now target `core/*` and `profiles/**/state/**`).
4. **First supervised run** on the new engine, watching the ledger + Notion together:
   `python3 core/state_sync.py pull --profile borjan-pm` → `python3 core/scan.py
   --profile borjan-pm` → judgment/scoring/log per the skill → `notion_sync` →
   `state_sync push`. Confirm: coverage ledger sane, shortlist rows land in the SAME
   Passed/Seen Log, digest on the SAME Runs page, sweep line present, dedup suppresses
   already-seen roles.
5. **Freeze the legacy skill.** In this order to avoid the required-check trap:
   a. [ ] **ADMIN, PENDING** — Update `main` ruleset: **remove `Validate job-scout-pm`**
      from required checks (the `Validate platform` check added in preconditions is the
      stable replacement). Borjan-only (GitHub admin). Nothing in code can do this, and
      it MUST land before 5b.
   b. In `.github/workflows/ci.yml`: [x] parity step removed 2026-07-14 (parity diverges
      by design post-tier-recompute; `core/parity_diff.py` kept as historical). [ ] the
      `validate-legacy` job is **still present on purpose** — it is the current required
      check, so deleting it before 5a re-triggers the block. Retire it right after 5a.
   c. [x] Done 2026-07-14 — `job-scout-pm/README.md` archive note added.
   d. Do NOT delete `job-scout-pm/` — it's the reference archive and the parity anchor.
6. **Rollback (if the new engine misbehaves in the first days):** un-freeze is trivial —
   re-point the schedules back to the v3 prompt; legacy code and state history are
   untouched under `job-scout-pm/`. State converges because both engines share the same
   Notion inbox and the dedup history was copied, not moved.

## After cutover

- Mark PROGRESS.md step 1.12 done; Phase 1 closed.
- Phase 2 (templates + setup interview) can begin — see PROJECT_PLAN.md.
