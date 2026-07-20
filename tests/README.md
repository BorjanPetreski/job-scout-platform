# tests/ — the behavioral gate

`core/validate.py` is the **structural** gate: it proves every file *compiles* and every
profile/template *resolves*. It cannot catch a logic bug — a detector can return the wrong answer
and validate stays green. This directory is the **behavioral** gate: it proves the pure-logic
layer actually returns the right answers.

Same convention as the rest of the repo — plain self-asserting Python, **no pytest**, no new
dependency (matches `validate.py` and `sims/`). Each module defines `main() -> list[str]` (the
failures) and is runnable standalone or via the runner.

## Layout

| File | Covers |
|------|--------|
| `unit_detectors.py` | `core/scan.py` pure detectors — `detect_language`, `language_flag`, `stated_language_requirement`, `detect_employment`, `detect_work_arrangement`, `start_date_passed`, `detect_seniority` |
| `unit_dedup.py` | `core/dedup.py` normalization — `norm_url`, `norm_company`, `role_family` (incl. characterization tests pinning two known quirks) |
| `_harness.py` | tiny shared `Suite` helper (puts `core/` on the path) |
| `run_all.py` | runs the unit suites **and** the `sims/` acceptance harnesses; the CI entry point |

Cross-boundary flows (Notion sync/reconcile round-trips) live in `sims/` as mocked-boundary
harnesses, not here — `run_all.py` runs those too.

## Run

```bash
python3 tests/run_all.py          # everything (what CI runs)
python3 tests/unit_detectors.py   # one suite, standalone
```

## What to test where (the scope discipline)

- **Unit-test** pure logic in `core/` (detectors, dedup/scoring helpers): cheap, high-value.
- **Sim** cross-process / external-integration flows against a *mocked* boundary (`sims/`).
- **Don't** unit-test the fragile fetch/render I/O — that layer is covered by honest-failure +
  `fetch_evidence` telemetry + the scheduled health-review loop (see `HEALTH_MONITORING.md`).
- Config resolution is already covered by `core/validate.py`.
