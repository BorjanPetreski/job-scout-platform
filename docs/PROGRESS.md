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
| 0 | Documentation set (plan, architecture, config spec, this log) | 🟡 in review — this PR |
| 1 | Core engine extraction + borjan-pm parity + shortlist liveness sweep | ⬜ not started |
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
| 0.5 | Borjan reviews docs + answers open questions | ⬜ | Blocks Phase 1 kickoff decisions; defaults adopted in plan §5 apply if unanswered |

## Phase 1 — Core engine extraction (build checklist)

Ordered so the live scan keeps working at every step. Details: PROJECT_PLAN.md Phase 1,
ARCHITECTURE.md throughout.

| # | Step | Status | Notes |
|---|------|--------|-------|
| 1.1 | `core/schema/profile.schema.yaml` + `profile_loader.py` + `validate.py` (validator in core) | ⬜ | Schema per PROFILE_CONFIG_SPEC.md §2; strict validation |
| 1.2 | `catalog/platforms.yaml` — extract platform registry, parameterize URLs with `{category}` slots + slug maps | ⬜ | Mechanical extraction from job-scout-pm/config.yaml; keep every quirk verbatim |
| 1.3 | `templates/project-management/delivery-manager.yaml` — PM template extracted from SKILL.md + config | ⬜ | First template, battle-tested by construction |
| 1.4 | `profiles/borjan-pm/profile.yaml` — Borjan's values; resolved-config diff vs today's effective config passes | ⬜ | Comparison script, not eyeballing (spec §8) |
| 1.5 | Move scripts → `core/`, thread `--profile` through; state paths profile-namespaced | ⬜ | No behavior change; salary.py added per spec §5 |
| 1.6 | `core/sweep.py` — shortlist liveness sweep + Notion `Stale/Expired` flip | ⬜ | ARCHITECTURE.md §6; seeded-stale acceptance test |
| 1.7 | `skills/job-scout-run/SKILL.md` — generic run skill (engine policy + judgment layer reads profile) | ⬜ | Three-lane detection and Appendix-A fallback preserved |
| 1.8 | Migrate `job-scout-pm/state/` → `profiles/borjan-pm/state/` verbatim | ⬜ | History is the asset; never regenerate |
| 1.9 | Parity runs: full rotation on new engine vs old (coverage ledger, dedup decisions, Notion writes) | ⬜ | Old path untouched until this passes |
| 1.10 | Demo second profile (dry-run, e.g. fe-react) validates + plans with zero engine changes | ⬜ | The abstraction proof |
| 1.11 | CI: audit `core/` + catalog + all profiles (replace job-scout-pm target) | ⬜ | Keep old audit green until 1.12 |
| 1.12 | CUTOVER: re-point laptop + cloud schedules; freeze `job-scout-pm/` as archive | ⬜ | Deliberate, reversible; needs Borjan for the laptop schedule |

## Phase 2 / 3 / 4

Checklists to be seeded when the phase starts (from PROJECT_PLAN.md scopes). Do not
pre-plan details here — plans go stale; the plan of record is PROJECT_PLAN.md.

## Session log

| Date | Session | Work done |
|------|---------|-----------|
| 2026-07-13 | Phase 0 (cloud, branch `claude/job-scout-engine-abstraction-2g5b0o`) | Wrote the four-doc planning set; seeded Phase 1 checklist; PR opened for review |
