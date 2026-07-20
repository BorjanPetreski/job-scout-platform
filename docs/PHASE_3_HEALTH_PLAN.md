# PHASE 3 interstitial — Platform Health & Self-Healing (build plan + record)

> The sequenced build between Phase 3a and 3b (Borjan: "fully build this before continuing
> with 3b"). Design seed: **[HEALTH_MONITORING.md](HEALTH_MONITORING.md)** (the *why* + the
> full multi-layer vision). This doc is the *what-shipped* build record for the near-term
> layers. Pipeline: brainstorm → detailed plan → Fable 5 review gate → Opus 4.8 build.
> **Status: Layers 1 + 1.5 + the Layer-2 cue LANDED 2026-07-20 (Opus 4.8).**

## Goal

Close the one gap the honest-failure floor doesn't cover: **the silent selector break** — a
board returns HTTP 200 with HTML but the parser extracts 0 rows because the markup changed, so
`source_down` stays `false` and the degradation hides. More broadly, make the engine **measure
its own health continuously and honestly** and give Claude a **signal-triggered cue** to diagnose
and repair board rot on a cadence, instead of relying on a human noticing the ledger.

Design principle, same as the scan itself: **scripts flag, Claude decides.** `health.py` is
mechanical (emits severity-flagged signals, no judgment, no network, no repairs). Diagnosis +
catalog fixes are the Layer-2 Claude review. Nothing here weakens the honest-failure floor.

## What shipped

### Telemetry contract (the prerequisite)

`runs.json` gained a per-run **`platform_stats`** map (`core/scan.py`): `{platform → {raw,
source_down, http_ok}}`. The new axis is **`http_ok`** — *did the board actually answer (HTTP
200 + a real body)?* — which is what lets `health.py` separate the silent selector break from a
plain outage:

| `source_down` | `http_ok` | meaning | signal |
|---|---|---|---|
| `true`  | `false` | couldn't reach it | DOWN_STREAK |
| `true`  | `true`  | **reached 200 but parsed 0 rows** | **SELECTOR_SUSPECT** |
| `false` | `true`  | produced candidates / clean API | (baseline) |

`http_ok` threads through `fetch_boards.py` via the `_ok`/`_down` helpers (default: `_ok` ⇒ True,
`_down` ⇒ False). The reached-but-empty downs are marked `http_ok=True` explicitly (WWR "RSS
parsed to 0", Deel "careers JSON yielded 0", and `fetch_html_listing` when a 200 body was fetched
but 0 links harvested). A baseline accrues the moment a board goes active — so the signals get
sharper every run.

### Layer 1 — `core/health.py` (mechanical signals)

Pure `compute_health(runs, active_names, thresholds)` over the telemetry (no I/O — unit-tested).
Thresholds live in `core/defaults.yaml` under `health:` and resolve per profile.

| Flag | Fires when | Severity |
|------|-----------|----------|
| `SYSTEMIC` | ≥ `systemic_frac` of active boards at ~0 in the latest run (≥4 present) — a core/network fault, not board rot; **suppresses the per-board flags** (they're symptoms) | critical |
| `SELECTOR_SUSPECT` | latest `http_ok` and `raw==0`, trailing median ≥ `min_baseline` — the silent break | high |
| `DOWN_STREAK` | hard-down (unreachable) ≥ `down_streak` runs in a row | high |
| `YIELD_COLLAPSE` | still producing but `raw < yield_collapse_factor × trailing_median` (median ≥ `min_baseline`) | medium |
| `NEVER_PRODUCED` | active + reached across ≥ `never_produced_min_runs` runs but logged 0 candidates ever | low |

At most one primary flag per board (SELECTOR > DOWN > COLLAPSE), plus NEVER_PRODUCED only when no
other flag explains it. Output: JSON report (`--json`) + a human summary. Legacy runs (written
before `platform_stats`) still yield DOWN_STREAK from the old `sources_down` list; yield-based
signals simply wait for the new telemetry to accrue.

### Layer 1.5 — in-scan self-healing (bounded, always reported)

`fetch_boards.py`: (1) `_get` retries with bounded backoff (2s, 4s) on **transient** failures only
— connection resets, timeouts, 429/5xx — never on a real 4xx (the board answered). (2)
`fetch_html_listing` escalates direct→headless when the plain request is blocked/JS-gated/empty.
Every recovery is surfaced: results carry a `healed` list, recorded in `runs.json` and printed on
the ledger as `✚ healed[board]: recovered via headless`. Conservative by design — a greedy healer
hides the very signals the health loop needs; reporting every heal keeps the honest-failure signal
alive. **Not** auto-healed: a selector/endpoint that actually changed, activating/deactivating a
board, any catalog-structure edit — those are Layer-2 (a wrong auto-edit could silently corrupt
results).

### Capturing repairs — `HEALTH_LOG.md`

Every Layer-2 review records its findings + the catalog fix it applied in
**[HEALTH_LOG.md](HEALTH_LOG.md)** (one row per flagged board), so board-rot repair becomes an
auditable trend instead of tribal knowledge — a board that recurs there is a demotion candidate;
a signal that keeps mis-firing is a threshold to tune.

### The hook — `health_review_due` counter

Rides the recompute mechanism: `scan.py` increments a `health_review` counter each run and prints
`⚠ platform health review due` every `health.due_at_sessions` sessions. That line is Claude's cue
to run `core/health.py`; running it acks the counter (resets to 0). The `job-scout-run` skill is
wired to run the review and diagnose flagged boards through the catalog + validator.

## Deferred (by design)

- **Layer 2-runtime** (in-app self-repair on the user's own instance, telemetry-fed precedence) →
  **Phase 4+**; needs the embedded LLM. Spec is in HEALTH_MONITORING.md.
- Multi-profile health aggregation (platform-fault vs config-fault) → naturally when multi-profile
  ops arrive; `compute_health` is already per-profile-pure and composable.

## Definition of done

- `python3 core/validate.py` green (structural) + `python3 tests/run_all.py` green (behavioral,
  now incl. `unit: health signals`).
- Additive: `borjan-pm` resolved config unchanged; what the scan resolves/scans/writes to Notion
  is unchanged (new fields are *additional* telemetry + an *additional* ledger line).
- `tests/unit_health.py` covers every signal (fires on its shape, quiet otherwise) + legacy
  telemetry + the empty case.
- No PII.
