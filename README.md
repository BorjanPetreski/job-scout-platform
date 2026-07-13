# job-scout-platform

A job-searching platform built around a profile-agnostic scanning engine, driven by
Claude. Today it runs one production profile; the plan is templates for any role, a
guided setup, an application assistant, and eventually a laptop + mobile product.

## Layout

- **`job-scout-pm/`** — the live v3.x scanner (PM/Delivery Manager profile), running on
  laptop + cloud schedules. Production until the Phase 1 cutover.
- **`docs/`** — the platform plan:
  - [PROJECT_PLAN.md](docs/PROJECT_PLAN.md) — vision, phases, acceptance criteria
  - [ARCHITECTURE.md](docs/ARCHITECTURE.md) — engine/catalog/profile separation, pipeline, contracts
  - [PROFILE_CONFIG_SPEC.md](docs/PROFILE_CONFIG_SPEC.md) — profile schema, templates, option sets
  - [PROGRESS.md](docs/PROGRESS.md) — build log; **read first when resuming build sessions**
