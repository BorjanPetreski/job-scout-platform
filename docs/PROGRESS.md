# PROGRESS — Job Scout Platform build log

> Session-resume contract for the platform build (successor to job-scout-pm's
> BUILD_PROGRESS.md, which stays untouched as the v3 archive). Read this FIRST on any
> session start/resume. Continue from the state below; never redo ✅ steps; update in the
> same session as the work; push before the session ends.

Plan of record: [PROJECT_PLAN.md](PROJECT_PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md)

**Standing production constraint: `job-scout-pm/` runs live schedules against `main`.
Do not break it before the Phase 1 cutover step.**

---

## Phase status

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | Documentation set (plan, architecture, config spec, this log) | ✅ merged (PR #8) |
| 1 | Core engine extraction + borjan-pm parity + shortlist liveness sweep | 🟡 built — in review; cutover (1.12) pending Borjan |
| 2 | Template library + setup interview + Notion provisioning | ⬜ not started |
| 3 | Application Assistant (Claude Projects package) | ⬜ not started |
| 4 | Setup/companion FE app (Agent SDK) | ⬜ not started |

## Phase 0 — Documentation (this PR)

| # | Step | Status | Notes |
|---|------|--------|-------|
| 0.1 | PROJECT_PLAN.md — vision, phases, acceptance criteria, open questions | ✅ 2026-07-13 | 5 open questions for Borjan (plan §5) |
| 0.2 | ARCHITECTURE.md — layers, repo layout, pipeline, Notion contract, sweep design | ✅ 2026-07-13 | |
| 0.3 | PROFILE_CONFIG_SPEC.md — schema draft, option sets, salary model, template format | ✅ 2026-07-13 | Schema is illustrative; normative schema ships in Phase 1 |
| 0.4 | This log seeded with the Phase 1 checklist | ✅ 2026-07-13 | |
| 0.5 | Borjan reviews docs + answers open questions | ✅ 2026-07-13 | Docs merged (PR #8); "lets go" = defaults adopted per plan §5 |

## Phase 1 — Core engine extraction (build checklist)

Ordered so the live scan keeps working at every step. Details: PROJECT_PLAN.md Phase 1,
ARCHITECTURE.md throughout.

| # | Step | Status | Notes |
|---|------|--------|-------|
| 1.1 | `core/schema/profile.schema.yaml` + `profile_loader.py` + `validate.py` (validator in core) | ✅ 2026-07-13 | Strict validation; loader resolves catalog+template+profile → effective config shaped like v3 config.yaml (the parity-friendly design decision) |
| 1.2 | `catalog/platforms.yaml` — extract platform registry, parameterize URLs with `{category}` slots + slug maps | ✅ 2026-07-13 | 23 entries, quirks verbatim; slug-keyed; SE-stream slugs marked `categories_verify_at_setup` (live-verify in Phase 2) |
| 1.3 | `templates/project-management/delivery-manager.yaml` — PM template extracted from SKILL.md + config | ✅ 2026-07-13 | + `software-engineering/frontend-react.yaml` (dry-run only) |
| 1.4 | `profiles/borjan-pm/profile.yaml` — Borjan's values; resolved-config diff vs today's effective config passes | ✅ 2026-07-13 | `core/parity_diff.py` PASSES: key-for-key identical, 16 documented accepted deltas (A1–A7 in the script header) |
| 1.5 | Move scripts → `core/`, thread `--profile` through; state paths profile-namespaced | ✅ 2026-07-13 | + `core/paths.py`, `core/salary.py` (additive `salary_assessment` metadata — never a machine drop) |
| 1.6 | `core/sweep.py` — shortlist liveness sweep + Notion `Stale/Expired` flip | ✅ 2026-07-13 | Seeded-stale acceptance PASSED (retired w/ queued in-place Notion update); 24h deferral verified; live-tested on the 18 real New—Unreviewed rows (all still live, sweep.json committed) |
| 1.7 | `skills/job-scout-run/SKILL.md` — generic run skill (engine policy + judgment layer reads profile) | ✅ 2026-07-13 | v4.0.0, status pre-cutover; three lanes + Appendix A preserved, profile-parameterized |
| 1.8 | Migrate `job-scout-pm/state/` → `profiles/borjan-pm/state/` verbatim | ✅ 2026-07-13 | `core/migrate_state.py`, idempotent union-merge; 765 records/471 URLs migrated. RE-RUN AT CUTOVER — legacy keeps producing state until then |
| 1.9 | Parity runs: full rotation on new engine vs old (coverage ledger, dedup decisions, Notion writes) | ✅ 2026-07-13 | Back-to-back live runs (`--no-headless`): identical covered(14)/down(8) ledgers; all 56 non-LinkedIn candidates IDENTICAL; only diff = LinkedIn tripwire sampling (nondeterministic endpoint). Legacy state git-restored after; Notion writes not exercised (no token) — structural guarantee unchanged + MCP-pending path preserved |
| 1.10 | Demo second profile (dry-run, e.g. fe-react) validates + plans with zero engine changes | ✅ 2026-07-13 | `profiles/demo-fe-react` — `scan.py --plan` produces a coherent React-stream rotation, zero engine changes |
| 1.11 | CI: audit `core/` + catalog + all profiles (replace job-scout-pm target) | ✅ 2026-07-13 | New `validate-platform` job (validate.py + parity_diff.py + per-profile `--plan`); legacy audit KEPT green until 1.12 |
| 1.12 | CUTOVER: re-point laptop + cloud schedules; freeze `job-scout-pm/` as archive | 🟡 prepped — awaiting coordinated run | **Full runbook: [CUTOVER.md](CUTOVER.md).** Prereqs DONE: PR #9 merged; `main` ruleset got admin bypass + `Validate platform` required check (2026-07-13, after the renamed-required-check block on #9); references copied into the profile (this PR). Remaining = the coordinated switch with Borjan (quiesce schedules → final migrate → re-point both lanes → supervised run → freeze legacy). |

## Phase 2 / 3 / 4

Checklists to be seeded when the phase starts (from PROJECT_PLAN.md scopes). Do not
pre-plan details here — plans go stale; the plan of record is PROJECT_PLAN.md.

## Session log

| Date | Session | Work done |
|------|---------|-----------|
| 2026-07-13 | Phase 0 (cloud, branch `claude/job-scout-engine-abstraction-2g5b0o`) | Wrote the four-doc planning set; seeded Phase 1 checklist; PR #8 merged |
| 2026-07-13 | Phase 1 build (same session/branch, restarted from main) | Built steps 1.1–1.11 end-to-end: catalog, templates (PM + fe-react), profiles (borjan-pm + demo), loader+validator, core extraction, sweep, generic skill, state migration, parity (config diff + live back-to-back runs), CI. Cutover (1.12) deliberately left for Borjan. Env notes: selectolax pip-installed; playwright not needed (`--no-headless` runs); `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt` required for live fetches in cloud sessions |
| 2026-07-13 | Phase 1 merge + cutover prep | PR #9 merged. Hit a self-inflicted merge block: the CI change renamed the job that `main`'s ruleset required by exact name (`Validate job-scout-pm`) → required check went permanently "expected". Fixed by renaming the legacy job back to the exact required name (comment added so it's not re-renamed). Borjan then added an admin bypass + the `Validate platform` required check to the ruleset (permanent guard). Cutover prep PR #10 merged: references copied into the profile + CUTOVER.md runbook. |
| 2026-07-13 | Cutover: state lock + supervised first live run | Routines paused by Borjan. Final `migrate_state.py` = verified no-op (765=765, state already final). **First live run of core v4.0.0** on borjan-pm: 116 candidates, 18 platforms covered, 4 sources down (all known degradations), sweep correctly deferred all 18 unreviewed (<24h). **Caught + fixed a real bug**: salary period inference read monthly non-USD pay 12x too low (63 false below_floor→5 genuine) — currency-neutral EUR-magnitude inference (commit d26927b). Judgment pass under Borjan's **worldwide/EMEA-open-only** policy: 5 shortlisted, 111 dropped (logged to seen.jsonl; drops kept local this run, not pushed to Notion). **REST Notion path live-validated for the first time** (NOTION_TOKEN via env; 5 rows + digest pushed, post-write asserted). Token was shared in chat → Borjan to rotate. Remaining cutover: re-point cloud Routine (Claude via MCP) + laptop task (Borjan), then freeze legacy. |
