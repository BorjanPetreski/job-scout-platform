# job-scout-platform

A job-searching platform built around a profile-agnostic scanning engine, driven by
Claude. It scans job boards on a schedule, filters and scores postings with real
judgment, verifies they're still live, and keeps a clean shortlist in Notion — for any
role, via templates and a CV-driven setup interview. On top of the scanner sits the
**Application Companion**: it learns your voice, grows your knowledge base, and drafts
applications that sound like you.

**Where things stand:** Phases 1–2 (engine + templates/setup) and Phase 3a (companion
voice + KB + apply loop, accepted 2026-07-19) are built and live. The Platform Health &
Self-Healing layer is in, with board audits ongoing. Next major: Phase 3b (interview
lifecycle). Live status always lives in [docs/STATE.md](docs/STATE.md).

**New here? Start with [docs/PLATFORM_GUIDE.md](docs/PLATFORM_GUIDE.md)** — the
human-readable guide: what this is, why, what's been built, how it works, and a worked
example of onboarding + daily use.

**Claude Code sessions:** the working agreement is [CLAUDE.md](CLAUDE.md); the
session-start hook auto-injects [docs/STATE.md](docs/STATE.md) (current lane / next
step / phase status) so sessions open oriented without re-reading history.

## Layout

- **`core/`** — THE ENGINE (profile-agnostic): scan orchestrator, fetchers, liveness
  checker, shortlist sweep, dedup, salary normalization, Notion sync/provisioning,
  state sync, loader/validator, health + arch-review counters, assistant composer.
  Run: `python3 core/scan.py --profile <id>` (`--plan` for a no-network dry run).
- **`catalog/platforms.yaml`** — shared platform knowledge (fetch modes, quirks,
  parameterized URL patterns).
- **`templates/`** — role templates (partial profiles + stream judgment text).
- **`profiles/<id>/`** — per-user config (`profile.yaml`) + namespaced state + the
  profile-side companion binding (`assistant/`: voice-seed, data-manifest).
- **`assistant/`** — the companion's generic doctrine package (voice acquisition, KB +
  growth loop, apply loop, pinned Notion write contract, verification, delivery
  discipline) + `GUIDED-FLOW.md` (the proven-prompt library) + `SETUP.md` / `DRY-RUN.md`.
- **`skills/job-scout-run/`** — the generic run skill (policy + judgment layer).
- **`skills/job-scout-setup/`** — the CV-driven setup interview that onboards a new
  profile end-to-end (classify → tailor → provision Notion → validate → first scan).
- **`tests/`** + **`sims/`** — the behavioral gate: unit tests for pure `core/` logic,
  sims for cross-boundary flows. Run: `python3 tests/run_all.py`.
- **`suggestions/`** — staged, consented, non-PII template enrichments awaiting curator
  review (the opt-in write-back loop).
- **`job-scout-pm/`** — the legacy v3.1.2 scanner, **frozen as the reference archive**
  since the Phase 1 cutover (2026-07-14). Do not run.

## Docs

**Session state + history**
- [STATE.md](docs/STATE.md) — **the dashboard**: current lane, next actions, phase
  status, open threads. Auto-injected into Claude sessions; rewritten every session.
- [PROGRESS.md](docs/PROGRESS.md) — append-only build log: per-phase checklists + the
  session log. History, not a session-start read.

**Plan of record**
- [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — vision, phases, acceptance criteria (the
  source of truth for scope).
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — engine/catalog/profile separation,
  pipeline, contracts.
- [PROFILE_CONFIG_SPEC.md](docs/PROFILE_CONFIG_SPEC.md) — profile schema, templates,
  option sets.
- [PLATFORM_GUIDE.md](docs/PLATFORM_GUIDE.md) — the human-readable guide (refreshed at
  each phase end).

**Runbooks & living operational docs**
- [HEALTH_MONITORING.md](docs/HEALTH_MONITORING.md) — health & self-healing design;
  [PHASE_3_HEALTH_PLAN.md](docs/PHASE_3_HEALTH_PLAN.md) — the interstitial build
  record; [HEALTH_LOG.md](docs/HEALTH_LOG.md) — every board-health review + the "How a
  review works" protocol.
- [LAPTOP_LANE.md](docs/LAPTOP_LANE.md) — attended + unattended runs on a laptop.
- [ENFORCEMENT_COVERAGE.md](docs/ENFORCEMENT_COVERAGE.md) — declared params vs. what
  the scanner actually enforces.
- [CUTOVER.md](docs/CUTOVER.md) — the Phase 1 cutover runbook (executed 2026-07-14).
- [ARCHITECTURE_QUALITY_SCOPE.md](docs/ARCHITECTURE_QUALITY_SCOPE.md) — scope + status
  of the periodic full-codebase architecture passes.

**Phase records & side captures**
- [PHASE_2_PLAN.md](docs/PHASE_2_PLAN.md) — closed; D1–D23 decision reference.
- [PHASE_3A_PLAN.md](docs/PHASE_3A_PLAN.md) — the 3a design contract + checklist
  (complete); [PHASE_3A_ACCEPTANCE.md](docs/PHASE_3A_ACCEPTANCE.md) — the acceptance
  runbook/record.
- [PHASE_3_PLAN.md](docs/PHASE_3_PLAN.md) — ⚠️ **superseded** first-pass apply-bot
  plan; kept for the still-valid bridge decisions it settled.
- [ANI_FIRST_RUN_FEEDBACK.md](docs/ANI_FIRST_RUN_FEEDBACK.md) — banked first-run
  companion feedback.
- [BUILD_AND_FLIP_PLAYBOOK.md](docs/BUILD_AND_FLIP_PLAYBOOK.md) — the product-agnostic
  build-method playbook (grows via CLAUDE.md DoD #7).
- [BUSINESS_NOTES.md](docs/BUSINESS_NOTES.md) — monetization / GTM / valuation notes.
