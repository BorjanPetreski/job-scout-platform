# PROGRESS — Job Scout Platform build log

> Session-resume contract for the platform build (successor to job-scout-pm's
> BUILD_PROGRESS.md, which stays untouched as the v3 archive). Read this FIRST on any
> session start/resume. Continue from the state below; never redo ✅ steps; update in the
> same session as the work; push before the session ends.

Plan of record: [PROJECT_PLAN.md](PROJECT_PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) · [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md) · **Phase 2 build plan: [PHASE_2_PLAN.md](PHASE_2_PLAN.md)**

> **NEXT SESSION = PHASE 2 BUILD.** Phase 2 has been fully brainstormed and planned (2026-07-15).
> The design contract + ordered build checklist live in **[PHASE_2_PLAN.md](PHASE_2_PLAN.md)**.
> Start there and execute steps 2.1→2.11; do not re-open the settled decisions (D1–D13).

**Standing production constraint: `job-scout-pm/` runs live schedules against `main`.
Do not break it before the Phase 1 cutover step.**

---

## Phase status

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | Documentation set (plan, architecture, config spec, this log) | ✅ merged (PR #8) |
| 1 | Core engine extraction + borjan-pm parity + shortlist liveness sweep | 🟡 built — in review; cutover (1.12) pending Borjan |
| 2 | Template library + setup interview + Notion provisioning | 🟡 planned — ready to build ([PHASE_2_PLAN.md](PHASE_2_PLAN.md)) |
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
| 1.12 | CUTOVER: re-point laptop + cloud schedules; freeze `job-scout-pm/` as archive | 🟢 freeze complete — only schedule re-point remains | **Full runbook: [CUTOVER.md](CUTOVER.md).** **Legacy freeze DONE 2026-07-14:** first attended run validated the new engine; `job-scout-pm/README.md` archive note (5c); `main` ruleset required check swapped `Validate job-scout-pm` → `Validate platform` (5a); `validate-legacy` CI job + parity step retired, `validate-platform` now the sole CI job/required check (5b). **Only remaining cutover action:** re-point the laptop scheduled task + cloud Routine(s) to the new prompt (`…scan for borjan-pm per skills/job-scout-run/SKILL.md. Unattended mode.`) — Borjan (laptop) + Routine tooling (cloud). Phase 1 closes once schedules fire on the new engine. |

## Phase 2 — Template library + setup interview + Notion provisioning (build checklist)

**Full plan + locked decisions (D1–D13): [PHASE_2_PLAN.md](PHASE_2_PLAN.md).** Ordered so
`borjan-pm` stays production at every step. First real test = onboard a senior Java backend
engineer (post-break, targeting mid/medior part-time) under Borjan's Notion, supervised.

| # | Step | Status | Notes |
|---|------|--------|-------|
| 2.1 | Schema extensions: `target_seniority`, `employment_type`, `run.effort(+by_run_type)` in schema + validator + loader | ⬜ | Additive/non-breaking — `borjan-pm` must still validate. Plan §3.1 |
| 2.2 | Template format v2: `platform_tiers` + `seniority_comp_bands` + inheritance/loader support | ⬜ | Plan §3.3 |
| 2.3 | Catalog expansion: per-stream slug maps + new boards as full `status: unverified` entries; per-stream tiers → templates | ⬜ | Plan §3.2 |
| 2.4 | Template library across the taxonomy: ⭐ tech-core deepest (incl **backend-java**), business/support/content as groundwork | ⬜ | Plan §2 |
| 2.5 | `core/provision_notion.py`: provision + adopt modes, token/parent params, idempotent | ⬜ | Plan §5 |
| 2.6 | `skills/job-scout-setup/`: the CV-driven templater/interview skill | ⬜ | Plan §4 |
| 2.7 | Write-back loop: opt-in consent, generic-only, staged suggestions, curator merge | ⬜ | Plan §6 |
| 2.8 | Effort/model tier: schema + documented mapping + two-stage design (wiring deferred) | ⬜ | Plan §7 |
| 2.9 | First real test: backend-java onboarding end-to-end; supervised live scan; capture lessons | ⬜ | Plan §8, acceptance D13 |
| 2.10 | CI: extend `validate-platform` to new schema/templates/catalog + per-⭐-template `--plan` smoke | ⬜ | — |
| 2.11 | Docs: update ARCHITECTURE + PROFILE_CONFIG_SPEC + PROGRESS | ⬜ | — |

## Phase 3 / 4

Checklists to be seeded when the phase starts (from PROJECT_PLAN.md scopes). Do not
pre-plan details here — plans go stale; the plan of record is PROJECT_PLAN.md.

## Session log

| Date | Session | Work done |
|------|---------|-----------|
| 2026-07-13 | Phase 0 (cloud, branch `claude/job-scout-engine-abstraction-2g5b0o`) | Wrote the four-doc planning set; seeded Phase 1 checklist; PR #8 merged |
| 2026-07-13 | Phase 1 build (same session/branch, restarted from main) | Built steps 1.1–1.11 end-to-end: catalog, templates (PM + fe-react), profiles (borjan-pm + demo), loader+validator, core extraction, sweep, generic skill, state migration, parity (config diff + live back-to-back runs), CI. Cutover (1.12) deliberately left for Borjan. Env notes: selectolax pip-installed; playwright not needed (`--no-headless` runs); `REQUESTS_CA_BUNDLE=/root/.ccr/ca-bundle.crt` required for live fetches in cloud sessions |
| 2026-07-13 | Phase 1 merge + cutover prep | PR #9 merged. Hit a self-inflicted merge block: the CI change renamed the job that `main`'s ruleset required by exact name (`Validate job-scout-pm`) → required check went permanently "expected". Fixed by renaming the legacy job back to the exact required name (comment added so it's not re-renamed). Borjan then added an admin bypass + the `Validate platform` required check to the ruleset (permanent guard). Cutover prep PR #10 merged: references copied into the profile + CUTOVER.md runbook. |
| 2026-07-14 | Post-cutover: lessons feedback + legacy freeze (branch `claude/job-scout-platform-resume-mfdp2r`) | Fed the first-attended-run lessons back into the engine + skill (v4.1.0): computed candidate annotations in `core/scan.py` (`non_english_jd` Polish-only-JD detector, `start_date_passed` stated-start-in-past detector, `missing_company` data-quality flag) and `core/dedup.py` helpers (`company_index`, `role_family`) driving `company_prior` + `applied_variant_saturation` (location-agnostic country-clone cross-check). Skill: non-English-JD hard filter, prior-history surfacing, Notion page-ID caching (kills the query→flip 429s), memory-ID re-verification rule, honesty-check step in the pitch router. Profile: JJ.it Polish-only filter_note + catalog quirk; `pitching.md` got the salary-ask heuristic, an explicit gap-honesty procedure, and a (Borjan-to-confirm) intro/links block. **Legacy freeze:** `job-scout-pm/README.md` archive note; parity CI step retired from `validate-platform` (tiers now diverge by design post-recompute — `parity_diff.py` kept as historical). validate-legacy CI job + ruleset swap deliberately deferred to avoid the required-check trap. |
| 2026-07-15 | Phase 2 brainstorm + execution plan (branch `claude/job-scout-phase-2-plan-kq3i6m`) | Interactive design session (Opus 4.8) with Borjan. Settled Phase 2 as **broad template groundwork + CV-driven setup templater + Notion provisioning**. Locked 13 decisions (D1–D13): option-C breadth (templates + catalog expansion, new boards as `status: unverified`); one cross-pollinating catalog with **per-stream tier rotation** (catalog=capability, template=tier order); CV read-not-stored templater with guardrails (reweight/select + obvious tech terms, no inventing types); opt-in human-reviewed write-back loop; `target_seniority` (soft + `strict`) orthogonal to role; `employment_type` (hard + `any` escape); `run.effort` model-tier (entitlement-shaped, two-stage design, **design-and-defer** with scheduling); provisioning token/parent as params (Borjan's Notion for trial, per-user end goal); scheduling deferred (config-only). Expanded taxonomy to ~12 streams incl ai-ml, web-dev, game-dev, tvos/android-tv, it-support, content-writing, SE-leadership subvariants. First test = senior Java backend eng → mid/medior part-time, supervised. Wrote **[PHASE_2_PLAN.md](PHASE_2_PLAN.md)** (design contract + ordered 2.1–2.11 checklist); seeded the Phase 2 table above; flagged **next session = build phase** (for a Fable 5 build run). No code changed — planning only. |
| 2026-07-13 | Cutover: state lock + supervised first live run | Routines paused by Borjan. Final `migrate_state.py` = verified no-op (765=765, state already final). **First live run of core v4.0.0** on borjan-pm: 116 candidates, 18 platforms covered, 4 sources down (all known degradations), sweep correctly deferred all 18 unreviewed (<24h). **Caught + fixed a real bug**: salary period inference read monthly non-USD pay 12x too low (63 false below_floor→5 genuine) — currency-neutral EUR-magnitude inference (commit d26927b). Judgment pass under Borjan's **worldwide/EMEA-open-only** policy: 5 shortlisted, 111 dropped (logged to seen.jsonl; drops kept local this run, not pushed to Notion). **REST Notion path live-validated for the first time** (NOTION_TOKEN via env; 5 rows + digest pushed, post-write asserted). Token was shared in chat → Borjan to rotate. Remaining cutover: re-point cloud Routine (Claude via MCP) + laptop task (Borjan), then freeze legacy. |
