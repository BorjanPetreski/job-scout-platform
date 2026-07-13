# job-scout-platform

A job-searching platform built around a profile-agnostic scanning engine, driven by
Claude. Today it runs one production profile; the plan is templates for any role, a
guided setup, an application assistant, and eventually a laptop + mobile product.

## Layout

- **`core/`** — THE ENGINE (profile-agnostic): scan orchestrator, fetchers, liveness
  checker, shortlist sweep, dedup, salary normalization, Notion sync, state sync,
  loader/validator. Run: `python3 core/scan.py --profile <id>` (`--plan` for a
  no-network dry run).
- **`catalog/platforms.yaml`** — shared platform knowledge (fetch modes, quirks,
  parameterized URL patterns).
- **`templates/`** — role templates (partial profiles + stream judgment text).
- **`profiles/<id>/`** — per-user config (`profile.yaml`) + namespaced state.
- **`skills/job-scout-run/`** — the generic run skill (policy + judgment layer).
- **`job-scout-pm/`** — the legacy v3.x scanner (PM profile), running on laptop +
  cloud schedules. **Production until the Phase 1 cutover** (PROGRESS.md step 1.12),
  then frozen as an archive.
- **`docs/`** — the platform plan:
  - [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — vision, phases, acceptance criteria
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — engine/catalog/profile separation, pipeline, contracts
  - [PROFILE_CONFIG_SPEC.md](docs/PROFILE_CONFIG_SPEC.md) — profile schema, templates, option sets
  - [PROGRESS.md](docs/PROGRESS.md) — build log; **read first when resuming build sessions**
  - [CUTOVER.md](docs/CUTOVER.md) — the ordered runbook for switching production to the `core/` engine
