# job-scout-pm — FROZEN v3.1.2 archive (do not run)

**Status: frozen 2026-07-14.** Superseded by the profile-agnostic `core/` engine +
`profiles/borjan-pm/` (Phase 1 cutover — see [`../docs/CUTOVER.md`](../docs/CUTOVER.md)
and [`../docs/PROGRESS.md`](../docs/PROGRESS.md)). The production scanner is now:

```
python3 core/scan.py --profile borjan-pm      # per skills/job-scout-run/SKILL.md
```

## Why this folder still exists

- **Reference archive** — the v3 skill, config, scripts, and changelog are the lineage
  record for the extracted engine.
- **Parity anchor** — `core/parity_diff.py` compared the resolved `borjan-pm` config
  against `config.yaml` here to prove the extraction was faithful at cutover. That gate
  passed and is now retired (tiers are living per-profile data and diverge by design
  after the first post-cutover recompute).

## Do not

- Do **not** run any script under `job-scout-pm/scripts/` — the schedules point at the
  `core/` engine now; running the legacy path would write stale, un-namespaced state.
- Do **not** re-point any schedule back here except as the documented cutover rollback
  (CUTOVER.md §6) — and only by re-pointing the schedule prompt, never by editing files
  here.
- Do **not** delete this folder — it is the archive and the parity anchor.

## Remaining coordinated retirement steps (admin-gated)

These finish the freeze and are intentionally NOT done in code yet, to avoid the
required-status-check trap (CUTOVER.md §5a→5b, and the 2026-07-13 PROGRESS note):

1. Update `main`'s ruleset to require **`Validate platform`** and remove the
   **`Validate job-scout-pm`** required check.
2. Only THEN retire the `validate-legacy` CI job in `.github/workflows/ci.yml`
   (it is the current required check; removing it before step 1 blocks every PR).
