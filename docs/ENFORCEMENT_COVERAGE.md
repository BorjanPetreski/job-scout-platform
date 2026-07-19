# Enforcement coverage — declared params vs. what the scanner actually enforces

Borjan's ask (2026-07-19): *every* constraint a profile declares should be considered by the scan,
not just the ones a user happens to notice leaking. This is the living map of **declared → enforced**,
the known gaps, and the pattern for adding new params (incl. ones a user adds at onboarding that the
app doesn't ship). Pair with the **balance rule** below — enforcing hard must never silently zero results.

## The two-layer contract (recap)

`scan.py` (scripts) **flags** with machine-certainty; the `job-scout-run` skill (judgment) **decides**.
A constraint is "enforced" at one of three strengths:
- **DROP (mechanical)** — `scan.py` Filters Out before the shortlist. Reserved for machine-certain,
  impossible-to-satisfy misses (you literally can't take the job). Routed to `seen.jsonl` "Filtered Out".
- **FLAG → judgment-drop** — `scan.py` annotates; the skill drops per doctrine / `filter_notes`.
- **ASSESS / informative** — metadata for scoring, never a drop.

## Coverage table

| Declared param | Enforcement today | Notes / gap |
|---|---|---|
| `candidate.location` + `location_match_terms` | **DROP** (`closed_location_list`, `us_only`) + judgment | Solid. |
| `candidate.citizenship` | FLAG (`eu_citizenship`) → judgment | Citizenship clauses need reading; flag is right. |
| `candidate.eligibility.needs_visa_sponsorship` | judgment only | Visa wording varies wildly; keep judgment. |
| `search.work_model` | **DROP** (opt-in `work_arrangement`) ✅ *new* | Fixed 2026-07-19 (was declared-but-unenforced — the hybrid leak). |
| `search.employment_type` | **DROP** (opt-in `employment_mismatch`) ✅ *new* | Fixed 2026-07-19 (was swallowed by contract co-occurrence). |
| `search.languages` | **DROP** (opt-in `language_mismatch`) ✅ *new* | Generalized from Polish-only → configurable multi-language set. |
| `search.target_seniority` (strict) | FLAG (`seniority_off_target`) → judgment | **GAP:** `strict: true` still relies on the judgment layer to drop. Candidate for a mechanical drop (the signal `seniority_detected` already exists). |
| `search.regions_acceptable` | informative (scoring) | By design — geography is covered by location filters. |
| `compensation.floor` | ASSESS (`salary_assessment`) → judgment | Borderline never auto-drops (D20). Correct. |
| `hard_filters.travel` | **DROP** | Solid. |
| `hard_filters.clearance` | **DROP** | Solid. |
| `hard_filters.grind_culture` | **DROP** | Solid. |
| `hard_filters.role_hard_drop_terms` | **DROP** (title) + FLAG (body) | Task #12 pattern. Correct. |
| `hard_filters.closed_location_list` | **DROP** | Solid. |
| `hard_filters.tool_lockin_drop` | FLAG → judgment | Primary-skill lock-in needs reading; flag is right. |
| `hard_filters.role_exclusion_terms` | FLAG → judgment | Deliberately flag-not-drop (CLAUDE.md standing rule). |
| `hard_filters.timezone_window` | FLAG (`timezone`) → judgment | Working-hours parsing is fuzzy; auto-drop risky. Keep flag for now. |

## Known gaps to close next

1. **`target_seniority.strict: true` → mechanical drop.** The one clear "declared hard but only
   judgment-enforced" case left. `seniority_detected` is already computed; a confident out-of-band
   posting under `strict` could Filter Out mechanically (mirror the `employment_mismatch` toggle).
   Guard against over-drop: seniority titles are noisy ("Lead" in a body ≠ lead role) — title-scoped only.
2. **Everything else is intentionally flag/assess** — don't convert without a deliberate reason
   (the CLAUDE.md caution). Reading-required signals (visa, citizenship, tool lock-in, timezone) stay judgment.

## Pattern for NEW params (incl. custom onboarding params)

When a user declares a new hard constraint the app doesn't ship a control for:
1. Add the signal detector to `scan.py` (machine-certain only).
2. Expose an **opt-in `hard_filters.<name>: [off|flag|drop]`** toggle (default the *safe* value —
   `flag`, or `off` if it shares a common default like `work_model`), compiled through only when
   non-default so unrelated profiles stay byte-identical.
3. Route `drop` through the post-annotation partition and **count it in `drop_by_param`** so the
   over-constraint nudge covers it automatically.
4. Default to **flag, not drop**, unless the miss is genuinely impossible-to-satisfy.

## Balance rule — never silently zero the funnel

- **Drop telemetry (built 2026-07-19):** every run records `funnel_in` (candidates that reached
  filtering), `drop_by_param` (counts by cause), and `drop_nudges`. When any single param drops
  **≥40%** of the funnel, the ledger prints `⚠ over-constraint: <param> dropped N/M (X%) — consider
  relaxing`. A high share isn't always wrong (Ani's remote-only legitimately drops ~53% — Poland is
  hybrid-heavy) — it **informs**, never auto-relaxes.
- **Borjan's "0 new" diagnosed (2026-07-19):** NOT a mechanical over-drop. His last scan produced
  **80 candidates, 1 mechanical drop** — the 0 was the *judgment layer* declining all 80 for legitimate
  reasons (US-only / PL-hybrid / Polish-only / auth-walled). The funnel was healthy; the market was thin.
  The telemetry above now makes that distinction visible on every run (mechanical drops vs. thin market).
</content>
