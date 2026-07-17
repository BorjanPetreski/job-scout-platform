# Architecture — Core Engine, Configuration Layers, and Boundaries

> Companion to [PROJECT_PLAN.md](PROJECT_PLAN.md). This describes the target structure
> Phase 1 builds toward and the contracts later phases depend on.

Status: **draft for Borjan's review** · Created: 2026-07-13

---

## 1. The separation principle

Three kinds of knowledge live in today's `job-scout-pm`, and the whole abstraction is
pulling them apart cleanly:

| Kind | Examples today | Where it goes |
|------|----------------|----------------|
| **Engine** — true for every profile, changes only when we learn a better way to scan | fetch fallback chain, liveness definition ("only a direct fetch of the source URL counts"), dedup match order, coverage honesty, evidence logging, state sync, Tracker write firewall, country-clone follow-up pattern, snippet-blindness rule | `core/` code + the generic run skill |
| **Platform** — true for every profile that uses a given board | JustJoin.it list chips lie; NoDesk keeps expired postings listed; Lever JSON API bypasses bot-detection; expired markers; fetch modes | `catalog/platforms.yaml` |
| **Profile** — true only for one person's search | keywords, salary floor + currency + gross/net + period, work model, location/eligibility/citizenship, timezone window, travel tolerance, scoring rubric inputs, archetypes, platform tiers (conversion data is per-role!), Notion IDs, schedule | `profiles/<id>/profile.yaml` (built from `templates/`) |

Litmus test used throughout: *"would a React engineer in Lisbon need this line changed?"*
If yes → profile. If only when the board changes behavior → catalog. Otherwise → engine.

## 2. Target repo layout

```
job-scout-platform/
├── core/                      # THE ENGINE — profile-agnostic, no role/person data
│   ├── scan.py                # orchestrator: load profile → plan → fetch → filter(1st pass) → liveness → sweep → emit
│   ├── fetch_boards.py        # per-platform fetchers driven by catalog entries (API→direct→headless→mirrors)
│   ├── check_links.py         # liveness checker + evidence log (2.7.0 definition, unchanged)
│   ├── sweep.py               # NEW: shortlist liveness sweep (§6)
│   ├── dedup.py               # seen-log read/write/match (URL-exact → 3-part key)
│   ├── render.py              # headless fetch wrapper (render(url) → html, nothing more)
│   ├── salary.py              # NEW: salary parsing + normalization to the profile's canonical unit (spec §5)
│   ├── profile_loader.py      # NEW: load + validate profile.yaml against schema; resolve template inheritance
│   ├── provision_notion.py    # Phase 2: provision/adopt Tracker/Passed-Seen/Runs (idempotent, D19);
│   │                          #   instruct→verify-by-probe (D17); writes output.notion into the profile
│   ├── secrets.py             # Phase 2: secret-storage SEAM (D18) — resolve token by key, env fallback
│   ├── writeback.py           # Phase 2: opt-in generic-only staged suggestions (D6), PII-guarded
│   ├── data/                  # Phase 2: seniority_lexicon.yaml (D21 base title→band lexicon)
│   ├── notion_sync.py         # one-way push, profile-parameterized targets
│   ├── state_sync.py          # git round-trip, profile-namespaced paths
│   ├── linkedin_tripwire.py   # guest-endpoint discovery, keywords from profile
│   └── validate.py            # config/schema/state validators (CI entrypoint) — the validator lives HERE
├── catalog/
│   └── platforms.yaml         # shared platform registry: fetch strategy, quirks, expired markers,
│                              #   parameterized URL/API patterns with {category}/{query} slots,
│                              #   category slug maps (platform category id per stream)
├── templates/                 # role templates + subvariants (PROFILE_CONFIG_SPEC.md §6)
│   ├── project-management/
│   └── software-engineering/
├── profiles/
│   └── borjan-pm/
│       ├── profile.yaml       # the ONLY file that knows who Borjan is and what he wants
│       └── state/             # seen.jsonl, runs.json, fetch_evidence.jsonl, jd_cache/, last_run_candidates.json
├── skills/
│   ├── job-scout-run/         # generic scan skill: engine policy + judgment layer, reads profile for all values
│   └── job-scout-setup/       # Phase 2: CV-driven setup interview / templater (provision→persist→validate→scan)
├── suggestions/               # Phase 2: staged write-back suggestions (outside templates/; own CI check)
├── assistant/                 # Phase 3: Claude Projects package (instructions + setup guide)
├── app/                       # Phase 4: FE setup/companion app
├── docs/                      # this documentation set + PROGRESS.md
└── job-scout-pm/              # legacy v3.1.2 — production until Phase 1 cutover, then frozen archive
```

Invocation shape: `python3 core/scan.py --profile borjan-pm` (profile id is the one
required argument everywhere; skills resolve it from context or ask once).

## 3. The three-layer configuration model

**Layer 1 — engine defaults** (in code / `core/defaults.yaml`): timeouts, parallelism
caps, politeness delays, freshness window default, fallback chain order. Overridable per
profile only where it makes sense (e.g. freshness window), not where it's safety
(LinkedIn caps are engine law).

**Layer 2 — platform catalog** (`catalog/platforms.yaml`): everything from today's
platform entries *minus* the PM-specific URLs. Search URLs become patterns:

```yaml
# catalog/platforms.yaml (illustrative)
- id: himalayas
  tier_default: 2                 # starting tier for NEW profiles; live tier is profile data
  fetch_mode: direct
  url_pattern: "https://himalayas.app/jobs/remote/{category}"
  categories:                     # slug map: stream → platform's own category slug
    project-management: project-management
    software-engineering: software-development
  expired_markers: ["This job posting is no longer available"]
  quirks: "Company-URL bounce is a platform quirk, NOT staleness."
```

A platform with no slug for a profile's stream falls back to its query pattern
(`?q={query}`) or is skipped-with-honesty in the ledger (`no category mapping`), never
silently. ATS platforms (Greenhouse/Lever/Workable/Pinpoint) are naturally generic
already — boards are discovered per profile and stored in profile state, since which
companies are relevant is profile knowledge.

**Layer 3 — profile** (`profiles/<id>/profile.yaml`): full schema in
[PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md). Assembled by template + user answers,
validated by `core/validate.py` at every run start (invalid profile = refuse to scan,
never guess).

**What happens to the judgment layer:** the generic run skill keeps the *filter types*
and the discipline (every shortlist candidate gets a full-JD judgment read; scripts flag,
Claude decides; ambiguity in unattended mode resolves conservatively with `❓ NEEDS
<user>`), but every filter's *values* come from the profile: the salary floor, the
timezone window, the eligible-locations test (today's EU-country-list detector
generalizes to "closed location list that doesn't include any of the profile's
`location.match_terms`"), tool lock-in list, travel tolerance, citizenship facts.
Profile-specific *lessons* (e.g. "Cyclad confirmed EU-citizenship drops apply to me
despite B2B") are recorded in the profile's `filter_notes`, which the skill reads —
so the learning loop survives per profile without touching the engine.

## 4. Run pipeline (engine, per profile)

```
0. state pull (git)                                   state_sync
1. load + validate profile, resolve catalog           profile_loader, validate
2. plan: active platforms × profile stream/keywords   scan
3. fetch enumeration (fallback chain per catalog)     fetch_boards
4. keyword title-filter (profile keyword sets)        scan
5. dedup vs full history                              dedup
6. machine first-pass filters (profile values)        scan  ← auto-drops logged with reasons
7. JD fetch to cache + liveness verification          check_links (+ render)
8. SHORTLIST LIVENESS SWEEP of prior unreviewed rows  sweep (§6)
9. emit candidates JSON + coverage ledger; NO scoring scan
──────────────────────────────────────────────────────
10. judgment read + scoring (profile rubric)          Claude, via skills/job-scout-run
11. same-invocation decision logging                  dedup append
12. Notion sync (profile targets) + digest            notion_sync
13. delta output → STOP                               skill
14. state push (git)                                  state_sync
```

Steps 0–9 are the deterministic core; 10–13 are the skill's judgment layer. The boundary
is exactly where it is today (scan.py "DOES NOT SCORE") — that split survives because
it's what lets the FE app (Phase 4) reuse the core while Claude does the judging.

## 5. Notion contract (shared with the Phase 3 assistant)

Per profile, provisioned per PROFILE_CONFIG_SPEC.md §7:

- **Passed/Seen Log** — the scanner's only write target. Scanner writes
  `New — Unreviewed` shortlist rows (+ role notes in page body) and drop records; the
  sweep (§6) may flip `New — Unreviewed` → `Stale/Expired`. The assistant flips
  `New — Unreviewed` → `User Declined`/`Applied`-adjacent reasons as the user works the
  queue.
- **Applications Tracker** — **never a scanner write target** (invariant preserved
  verbatim from v2.7.0). Writers: the assistant's "applied" flow and the interactive
  "I applied" chat flow. Statuses: Applied/Screening/Interview/Offer/Rejected/Withdrawn.
- **Runs page** — scanner digest lines, newest first.

Ownership rule that keeps the two apps from fighting: **the scanner owns row creation
and staleness; the human-driven flows own status progression.** The scanner never
un-declines, never re-shortlists a declined row (dedup suppresses it), and never touches
a row after it reaches the Tracker.

## 6. Shortlist liveness sweep (new in Phase 1)

Problem: the user may collect for days before applying; postings die in the meantime,
and today nothing re-checks a row after it lands in `New — Unreviewed`.

Design (`core/sweep.py`, runs inside every scan, step 8):

- **Scope:** seen.jsonl records with `status: shortlisted` not yet resolved by the user
  (still `New — Unreviewed` in Notion), excluding rows already retired.
- **Recheck policy:** liveness per the same 2.7.0 definition and the same checker —
  direct/rendered fetch of the source URL only; mirrors never confer liveness. Rate-aware:
  a row is re-checked at most once per `sweep.recheck_interval_h` (default 24h, profile-
  overridable), so a big backlog doesn't multiply fetch load; the per-host politeness
  caps are shared with the main scan.
- **On stale (confident: 404/410/expired marker):** update seen.jsonl
  (`status: dropped`, reason `Stale/Expired (post-shortlist sweep)`), flip the Notion row
  to `Stale/Expired` with a dated note — **flag, not delete**: the row stays visible so
  the user sees what expired and dedup history stays intact. The digest line reports
  `S went stale`.
- **On unverifiable (bot-block/JS-wall):** mark `❓ unverified <date>` in the row's
  notes, do NOT retire — same honesty rule as scan-time liveness; two consecutive
  unverifiable sweeps escalate the flag for the user to check manually.
- **Evidence:** every sweep check appends to `fetch_evidence.jsonl` like any other check.

## 7. State model (multi-profile from day one)

All run state becomes profile-namespaced: `profiles/<id>/state/…`. The formats are
unchanged (append-only `seen.jsonl` last-wins semantics, `runs.json` ledger + recompute
counter, evidence log, JD cache). `state_sync.py` pushes/pulls per profile; two profiles
never share dedup history (the same URL can legitimately be a candidate for two people).
The `borjan-pm` migration moves `job-scout-pm/state/` → `profiles/borjan-pm/state/`
verbatim — history is the most valuable asset and is never regenerated.

## 7a. Effort / model tier (Phase 2 design-and-defer, D9/D10)

The profile's `run.effort` (`fast`|`mid`|`high`) and optional `run.effort_by_run_type` map
to a compute/model tier: **fast→Haiku, mid→Sonnet, high→Opus**, shaped as a future
billing/entitlement axis (free = `fast` + unscheduled; paid = `mid`/`high` + weekly-deep +
scheduling). The intended runtime is a **two-stage judgment**: a cheap-model triage of the
raw candidate list, then a capable-model deep read of the shortlist survivors via subagent
delegation, with `effort_by_run_type` letting a frequent cheap daily sweep coexist with a
capable weekly deep sweep. **Phase 2 ships the schema field + this design only** — actual
model-at-launch selection belongs with the scheduler (also deferred, §8/D12), so no model
wiring exists yet; `run.effort` is recorded and validated but does not change run behavior.

## 8. What deliberately does NOT change

- The three-lane model (Code local / Code cloud / chat-native Appendix-A fallback) and
  the mandatory state pull/push framing steps.
- The liveness, dedup, blocked-lead, and coverage-honesty definitions — battle-tested,
  moved not rewritten.
- The "no auto-apply, no computer-use browsing, no authenticated scraping, no automated
  tier recompute" boundaries — engine law, listed in the generic skill for every profile.
- Notion as the DB. Revisit only at Phase 5 (a storage adapter boundary in
  `notion_sync.py` is cheap insurance and Phase 1 will keep writes behind one module,
  but no second backend is built now).
