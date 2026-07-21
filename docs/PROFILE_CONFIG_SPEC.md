# Profile & Template Configuration Spec (draft)

> The contract between the engine and everything that configures it: profile schema,
> option sets the setup flows present, salary normalization, template format, and Notion
> provisioning. Phase 1 implements the profile schema + loader/validator; Phase 2
> implements templates + the interview; Phase 4's FE app renders these same option sets
> as screens. Companion to [ARCHITECTURE.md](ARCHITECTURE.md).

Status: **draft for Borjan's review** · Created: 2026-07-13

---

## 1. Design rules

1. **Every option set below is data, not prose** — the setup interview (Phase 2) and the
   FE app (Phase 4) render the SAME definitions. One source of truth
   (`core/schema/profile.schema.yaml` + option enums), no duplicated forms.
2. **Templates prefill, users override.** No question is asked that a chosen template
   can answer with a sensible default; every default is shown and changeable.
3. **Validation is strict**: an unknown key, a tierless active platform, a salary without
   currency, a filter value with no unit — all refuse the run with a named error.
   (v2.7.1 lesson generalized: silent skips come from tolerated config gaps.)
4. **Profile ≠ person-secrets.** The profile holds search criteria and eligibility facts.
   CV content, past answers, and voice/pitch material stay in the Claude Project
   (Phase 3) — the scanner never needs them.

## 2. Profile schema (`profiles/<id>/profile.yaml`)

Illustrative — the normative schema ships as `core/schema/profile.schema.yaml` in Phase 1.
Shown with `borjan-pm` values as the worked example:

```yaml
schema_version: 1
id: borjan-pm
template: project-management/delivery-manager   # provenance; template updates never auto-apply

candidate:
  display_name: Borjan Petreski
  location: { city: Skopje, country: North Macedonia, timezone: Europe/Skopje }
  # Terms that count as "includes me" in location lists (drives the closed-list detector):
  location_match_terms: [North Macedonia, Macedonia, Skopje]
  citizenship: [MK]                 # ISO codes; the eu_citizenship filter derives from this
  eligibility:
    employment_models: [b2b_contractor, full_time]   # both equally fine — never deprioritize either
    needs_visa_sponsorship: false
  experience_years: 7
  certs: [PSM, PSPO, ECBA]
  domains: [Travel & Leisure, EdAI, Social Prospecting, IoT, Media/Streaming]

search:
  stream: project-management        # catalog category-slug key
  # subvariant: backend-java        # NEW (Phase 2): primary subvariant; optional — when omitted the
  #                                 #   `template:` path carries it. (borjan-pm uses the template path.)
  # subvariant_secondary: null      # NEW (Phase 2, D15): optional; sets unioned at setup, primary drives comp/tiers
  work_model: [remote]              # enum: remote | hybrid | on_site (multi-select)
  keywords:
    core: [project manager, scrum master, delivery manager, agile delivery lead, program manager]
    expanded: [implementation manager, release manager, proxy product owner, service delivery manager]
  archetypes: [Delivery Manager, Scrum Master, Technical PM, BA-leaning]
  regions_acceptable: [worldwide, emea, europe]     # informative for scoring, not a hard filter
  # target_seniority:               # NEW (Phase 2, D7): what they want to SEE (distinct from
  #   bands: [mid]                  #   experience_years). enum intern|junior|mid|senior|staff|principal|lead|manager
  #   strict: false                 #   false = judgment scoring input; true = hard filter. ("medior" title -> mid, D21)
  # employment_type:                # NEW (Phase 2, D8): which posting types to surface (hard by default)
  #   accept: [part_time, contract] #   enum full_time|part_time|contract|b2b|freelance|internship|any ('any' disables)

compensation:                       # full spec in §5
  floor: { amount: 2500, currency: EUR, basis: net, period: month }   # OPTIONAL as of Phase 2 (D20) —
                                    #   user-provided or unset; when unset the below-floor first-pass is disabled
  gross_net_ratio: 0.72             # net = gross × ratio (country-dependent; template default, user-tunable)
  # fte_fraction: 0.5               # NEW (Phase 2, D22): pro-rates a SET floor for part-time targets (0<f<=1)
  assume_unstated: judgment         # unpublished salary → judgment-layer estimation heuristics

hard_filters:                       # typed toggles + values; regex machinery lives in the engine
  timezone_window: { latest_end_local: "17:00" }    # work required after this local time → drop
  travel: none                      # enum: none | occasional_ok | any
  salary_floor: from_compensation
  tool_lockin_drop: [Dynamics 365, SAP, Salesforce, Workday, ServiceNow, Oracle]
  clearance: drop
  grind_culture: drop
  role_exclusions: [pure business analyst]          # per-stream, template-provided
  closed_location_list: drop_if_absent              # uses candidate.location_match_terms
filter_notes: |                     # profile-learned lessons the judgment layer reads
  EU-citizenship clauses drop even though B2B bypasses visa/payroll (Cyclad).
  CloudLinux Scrum Master is a known recurring stale — never resurface.

scoring:
  surface_threshold: 7.0
  bands: from_template              # template supplies band criteria text; overrides allowed inline
  salary_estimation_heuristics: from_template

platforms:
  tiers:                            # per-profile DATA (conversion-driven), seeded from catalog tier_default
    1: [justjoin-it, remotive, workable, lever, himalayas]
    2: [remote-rocketship-sm, remote-rocketship-pm-eu, nodesk, greenhouse]
    3: [wwr, jobgether, dynamite, arc, working-nomads, wttj, landing-jobs, justremote, remote-ok, pinpoint, deel, crossover]
  disabled: [europeremotely, otta]
  rejected: from_template_plus_local  # names + evidence reasons; do-not-re-add discipline
  recompute_after_sessions: 5
  linkedin_tripwire: { enabled: true, locations: [European Union, Worldwide] }

sweep:                              # shortlist liveness sweep (ARCHITECTURE.md §6)
  recheck_interval_h: 24

output:
  notion:
    tracker: { data_source_id: "560bd8e3-…", parent_page_id: "6fed5421-…" }
    passed_seen: { data_source_id: "21ab771f-…", parent_page_id: "b4aaa7e8-…" }
    runs_page_id: "398054b0-88af-81b7-8670-fef8aad15254"
  digest_language: en

schedule:
  runs: [{ at: "08:00", label: AM }, { at: "18:00", label: PM }]
  full_sweep_dow: Mon
  freshness_window_h: 48

# run:                              # NEW (Phase 2, D9/D10): compute/model tier — RECORDED + documented
#   effort: mid                     #   now, NOT wired to model selection yet (lands with the deferred scheduler).
#   effort_by_run_type:             #   fast->Haiku, mid->Sonnet, high->Opus; entitlement-shaped.
#     daily: fast
#     weekly_deep: high
```

## 3. Option sets the setup flows present

These enums are the "screens". Each field: options, default source, and who renders it
(interview = Phase 2, app = Phase 4 — always both).

| Field | Options presented | Default from |
|-------|-------------------|--------------|
| Stream | template library list (project-management, software-engineering, …) | — (first question) |
| Subvariant | template's subvariant list (e.g. frontend → react/angular/vue; generic "software developer") | template |
| Secondary subvariant | optional; a second subvariant whose keyword/archetype sets are unioned in (D15) | — (offered when CV/goal spans two) |
| Target seniority | intern/junior/mid/senior/staff/principal/lead/manager (multi) + strict toggle (D7) | template / CV-derived |
| Employment type | full_time/part_time/contract/b2b/freelance/internship (multi) or `any` to disable (D8) | template / CV-derived |
| Work model | remote / hybrid / on-site (multi) | template (remote) |
| Salary floor | amount + currency (EUR/USD/GBP/… ISO list) + basis (gross/net) + period (hour/day/month/year), **or leave unset** (D20 — judgment-time estimation) | user-provided or unset (no shipped numbers) |
| FTE fraction | 0 < f ≤ 1; pro-rates a set floor for part-time targets (D22) | 0.5 for part-time targets, else unset |
| Run effort | fast / mid / high compute tier; optional per-run-type override (D9/D10, recorded not yet wired) | template / unset |
| Gross↔net ratio | number, with per-country presets table | candidate country |
| Location & eligibility | city/country/timezone; citizenship; employment models (b2b/full-time/either); visa need | — (asked once) |
| Timezone window | latest acceptable end-of-day local time | 17:00-equivalent |
| Travel | none / occasional OK / any | none |
| Tool lock-in exclusions | multi-select from template's list + free add | template |
| Role exclusions | template list (e.g. "pure BA" for PM stream) + free add | template |
| Keywords | template core + expanded sets, editable | template |
| Platforms | catalog list with template's relevance marks; tiers seeded from `tier_default` | catalog+template |
| Schedule | 1×/2× daily times, weekly full-sweep day | 08:00+18:00, Mon |
| Notion | provision new databases (default) or point at existing IDs | provision |
| Write-back consent | opt in / out of staging generic (non-PII) template enrichments for curator review (D6, `writeback.consent`) | out (opt-in) |

## 4. Keyword & category model

- Keywords are **local title-match filters** on enumerated postings (substring matching,
  as today), not search queries — the catalog's category URLs do enumeration.
- A template supplies `core` (always-on) and `expanded` (promote/demote dataset) sets.
  The promote/demote review stays user-triggered per profile, driven by
  `keyword_source` data recorded on every candidate — mechanism unchanged, now per profile.
- The profile's `search.stream` selects each platform's category slug from the catalog.
  A subvariant may add narrower slugs where a platform has them (e.g. JustJoin.it
  category per tech stack) — slug maps live in the catalog, subvariant → slug preferences
  in the template.

## 5. Salary model (normalization in `core/salary.py`)

Everything compares in the profile's canonical unit: **floor-currency, gross, per month**.

- **Parsing:** extract amount(s), currency, period, basis from posting text; ranges use
  the range **maximum** for the floor test (a role whose top can't reach the floor is
  out; judgment layer notes when only the bottom clears — mirrors current practice).
- **Period:** hour ×160, day ×20, year ÷12 (engine constants, documented).
- **Basis:** stated gross ↔ net via the profile's `gross_net_ratio`. No tax engine —
  the ratio is a per-profile knob with country presets; anything within ±10% of the floor
  after conversion is flagged `salary borderline — verify` rather than auto-dropped.
- **Currency:** static rates table in the engine (`core/data/fx.yaml`), refreshed
  manually/periodically; each normalization records the rate used in the candidate
  record. Precision beyond "does it clear the floor" is not a goal.
- **Unstated salary:** never a drop; the judgment layer applies the template's estimation
  heuristics (e.g. "US/UK HQ paying globally → likely clears") — heuristics text is
  template data because it is stream-specific.
- **Floorless (Phase 2, D20):** `compensation.floor` is optional. When unset, the machine
  below-floor first-pass is **disabled** (`normalize_floor` returns `canonical_gross_month:
  null`, `assess()` returns `unparseable`) and salary judgment falls **entirely** to the
  template's `salary_estimation_heuristics` — no shipped per-seniority numbers, never an
  auto-drop. `gross_net_ratio` is required only when a floor is set (still validated 0.3–1.0
  when present without one).
- **Part-time (Phase 2, D22):** when a floor **is** set and the target is part-time, the
  canonical floor is pro-rated by `fte_fraction` (0 < f ≤ 1; 0.5 default seeded by the
  templater for part-time only) before comparison — a full-time €3,000/mo floor at 0.5 FTE
  compares against €1,500. Day/hourly rates still normalize via the period model above. A
  full-time profile (e.g. `borjan-pm`) leaves `fte_fraction` unset and its floor is unchanged.

## 6. Template format (`templates/<stream>/<subvariant>.yaml`)

A template is a **partial profile** plus interview hints — same schema keys as §2, only
the profile-agnostic ones, with two extra blocks:

```yaml
schema_version: 1
template_id: software-engineering/frontend-react
extends: software-engineering/frontend      # single-inheritance chain: stream → subvariant → variant
label: "React Software Engineer"
suggest_also: [frontend, fullstack-js]      # shown as alternatives during setup

defaults:                                    # any subset of profile keys from §2
  search:
    keywords:
      core: [react developer, react engineer, frontend engineer, front-end developer, ui engineer]
      expanded: [javascript engineer, typescript engineer, web developer, next.js developer]
    archetypes: [Frontend Engineer, Fullstack-leaning, UI Engineer]
  hard_filters:
    role_exclusions: [pure designer, wordpress-only]
    tool_lockin_drop: []                     # stream-appropriate; PM's ERP list doesn't apply
  compensation:
    floor: { amount: 3000, currency: EUR, basis: gross, period: month }  # suggested band, always confirmed

scoring_bands: |                             # stream-specific band criteria text (the 9/8/7 rubric)
  9.0–10.0: modern React (hooks, SSR/Next), TS, product-team ownership, worldwide/EMEA, salary confirmed…
  …
salary_estimation_heuristics: |              # TEXT ONLY — no hardcoded per-seniority numbers (D20)
  …
platform_tiers:                              # v2 (Phase 2, D3/§3.3) — per-stream starting tier order
  1: [justjoin-it, lever, workable, greenhouse, himalayas, remotive]
  2: [remote-rocketship-worldwide, nodesk, wwr, arc]
  3: [jobgether, dynamite, working-nomads, wttj, landing-jobs, remote-ok, deel]
seniority_titles:                            # v2 (Phase 2, D21) — extends core/data/seniority_lexicon.yaml
  sde ii: mid                                #   stream/region-specific title → base band
  staff engineer: staff
interview:                                   # Phase 2 hints — control PACING, never VISIBILITY:
  emphasize: [work_model, compensation.floor, candidate.location]  # confirmed one-by-one
  skip_if_defaulted: [hard_filters.grind_culture, sweep]  # not asked one-by-one, but still
                                              # shown + overridable in the mandatory defaults
                                              # summary before provisioning (rule 2, SKILL.md §6)
```

Resolution: `stream defaults → subvariant → variant → user answers`, deep-merged in that
order; the resolved result must validate as a full profile. The current PM setup becomes
`templates/project-management/delivery-manager.yaml` — extracted from, and verified
against, today's `config.yaml` + `SKILL.md` so the first template is battle-tested by
construction.

**Template v2 blocks (Phase 2).** Beyond `scoring_bands` / `salary_estimation_heuristics`
/ `interview`, a v2 template may carry:
- `platform_tiers` (D3/§3.3) — the per-stream tier ordering that **seeds** a new profile's
  `platforms.tiers`. It is **template-only and never loader-merged**: seeded once at
  interview time, after which the profile's tiers are per-profile conversion DATA (a later
  template edit never retiers an existing profile — `borjan-pm`'s live tiers stay put by
  construction). At seed time, active platforms the block doesn't list are placed
  deterministically — catalog `tier_default` if they carry a slug for the stream, else
  `disabled` (recorded, not silent).
- `seniority_titles` (D21) — stream/region-specific title→band entries that extend the base
  `core/data/seniority_lexicon.yaml`, deep-merged along the `extends` chain and into the
  resolved `cfg["seniority_lexicon"]` the judgment layer reads for `target_seniority`.
- `salary_estimation_heuristics` is **text only** — no shipped per-seniority band numbers
  (D20); the floor is user-provided or unset (judgment-time estimation from this text).

## 7. Notion provisioning (Phase 2, `core/provision_notion.py`)

For a new profile: create **Applications Tracker** (status select with the six canonical
options, Source, Date Applied, Fit Score, Keyword Source, Notes), **Passed/Seen Log**
(Status incl. `New — Unreviewed`/`Stale/Expired`, Reason Passed, Platform select, Job
URL, Fit, Archetype), the **Runs** digest page, and the "📥 New — Unreviewed" view;
write the resulting IDs into the profile. Platform select options are patched lazily
before first write (mechanism exists today). Existing databases can be adopted instead —
the provisioner then only verifies schema compatibility and reports gaps.

## 8. Companion binding (Phase 3a, `core/compose_assistant.py`)

The Application Companion (Phase 3a) runs on a claude.ai Project / Claude Desktop with the Notion
MCP; it can't read the repo, so a **PII-free composer** binds a profile to it. `compose_assistant.py`
emits, per profile, into `profiles/<id>/assistant/`:

- **`project-instructions.md`** — the full companion doctrine (the generic `assistant/[0-9][0-9]-*.md`
  modules) + a **config-only snapshot** (salary floor, eligibility/employment models, location +
  timezone, Notion `data_source_id`s) + the profile's `voice-seed`/`data-manifest`. Uploaded to
  **Project knowledge** (it's ~30k chars — too long for the custom-instructions field).
- **`project-bootstrap.md`** — a compact (~3k) subset that fits the **custom-instructions field**
  (~4k cap): identity, the snapshot, consent/retention, hard boundaries, the pinned Notion write
  vocabulary, and a pointer to read the full file. Both stamped with a compose date + source-config
  hash; idempotent (re-compose is a no-op unless the profile/config/package changed).

Author-supplied, per-profile, **optional** (checked into the repo — no PII beyond public links):

- **`profiles/<id>/assistant/voice-seed.md`** — authored voice guidance (source-doc priority,
  person-specific corrections, links). Absent ⇒ the composer emits the guided-Q&A voice path.
- **`profiles/<id>/assistant/data-manifest.md`** — what the user uploads to the Project + each
  item's retention class (domain kept / voice-only shredded). Absent ⇒ a generic checklist.

The user's CV, voice profile, and knowledge base are **built and held inside the Project**, never
composed from the repo (data principle). CI (3a.8) checks the committed bindings are compose-clean
and that all binding files pass a no-PII denylist (emails / phones / postal addresses).

## 9. Migration note for `borjan-pm`

Phase 1 derives all three artifacts from the live system as a **mechanical extraction
with a diffable audit trail**: catalog = platform entries minus PM URLs; template =
PM-generic policy from SKILL.md + config; profile = Borjan's values. Acceptance = the
resolved `borjan-pm` profile reproduces today's effective configuration key-for-key
(a comparison script, not eyeballing), and state moves verbatim per ARCHITECTURE.md §7.
