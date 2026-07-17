# job-scout-platform

A job-searching platform built around a profile-agnostic scanning engine, driven by
Claude. It scans job boards on a schedule, filters and scores postings with real
judgment, verifies they're still live, and keeps a clean shortlist in Notion — for any
role, via templates and a CV-driven setup interview. Phases 1–2 are built and live;
next up: an application assistant, then a companion app.

**New here? Start with [docs/PLATFORM_GUIDE.md](docs/PLATFORM_GUIDE.md)** — the
human-readable guide: what this is, why, what's been built, how it works, and a worked
example of onboarding + daily use.

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
- **`skills/job-scout-setup/`** — the CV-driven setup interview that onboards a new
  profile end-to-end (classify → tailor → provision Notion → validate → first scan).
- **`suggestions/`** — staged, consented, non-PII template enrichments awaiting curator
  review (the opt-in write-back loop).
- **`job-scout-pm/`** — the legacy v3.1.2 scanner, **frozen as the reference archive**
  since the Phase 1 cutover (2026-07-14). Do not run.
- **`docs/`** — the platform plan:
  - [PLATFORM_GUIDE.md](docs/PLATFORM_GUIDE.md) — **the human-readable guide; start here**
  - [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — vision, phases, acceptance criteria
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — engine/catalog/profile separation, pipeline, contracts
  - [PROFILE_CONFIG_SPEC.md](docs/PROFILE_CONFIG_SPEC.md) — profile schema, templates, option sets
  - [PROGRESS.md](docs/PROGRESS.md) — build log; **read first when resuming build sessions**
  - [CUTOVER.md](docs/CUTOVER.md) — the ordered runbook for switching production to the `core/` engine
