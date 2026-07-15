# Phase 2 Execution Plan — Template Library + Setup Interview + Notion Provisioning

> The detailed build plan for Phase 2, produced from a design brainstorm and written to be
> **executed by a build agent in a later session** (the next session picks up here — see
> PROGRESS.md). Companion to [PROJECT_PLAN.md](PROJECT_PLAN.md) §Phase 2 (scope),
> [ARCHITECTURE.md](ARCHITECTURE.md) (structure/contracts), and
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md) (schema/templates). This document is the
> plan of record for the Phase 2 build; where it refines the earlier drafts, it wins, and
> the build should update those docs to match as it goes.
>
> Status: **ready to build** · Created: 2026-07-15 · Brainstorm: Opus 4.8 · Build target: Fable 5

---

## 0. What Phase 2 is (one paragraph)

Turn the single battle-tested PM template into a **broad groundwork template library** spanning
most IT-adjacent job streams, and build a **CV-driven setup interview ("the templater")** that
reads a new person's CV, places them into the nearest template, tailors it to their real
experience/seniority/goals, provisions their Notion, validates, and does a first scan. The
platform catalog **grows** with stream-appropriate boards (added as researched-but-unverified
entries), and platform **tiers rotate per stream**. First real test: onboard a **senior Java
backend engineer** (post-break, targeting **mid/medior part-time**) under Borjan's Notion as a
supervised trial.

## 0a. Prime directive — `borjan-pm` is production and sacred (do not regress)

**Phase 1's engine works and Borjan uses it daily to find his own jobs. That must keep working,
unchanged in behavior, the entire way through Phase 2 and beyond.** This is the top constraint —
it outranks any Phase 2 convenience.

- **Purely additive.** Phase 2 *extends*; it never obfuscates, rewrites, or removes what already
  serves `borjan-pm`. Every schema field is additive with a default that preserves current behavior;
  every catalog/template change is backward-compatible; `borjan-pm` validates and scans identically
  before and after each step.
- **Continuous dogfooding.** Borjan keeps running the scanner for himself *while* we build — we do not
  pause his job search to build the platform. Running it in anger is how we learn (it's how v3 got good).
  No Phase 2 step may require taking `borjan-pm` offline.
- **State/history is untouchable.** `profiles/borjan-pm/state/` (seen.jsonl, runs, evidence, JD cache)
  is the most valuable asset — never regenerated, migrated destructively, or reset by any Phase 2 work.
- **Borjan is user #1, forever.** When the app arrives (Phase 4/5), Borjan is **account #1** and
  everything already built for him — profile, state/history, Notion, config — is **carried in verbatim**,
  not re-created. Nothing in Phases 2–4 may assume a "fresh start" that would strand his existing setup.

If any Phase 2 change would force a regression here, the change is wrong — find the additive path instead.

## 1. Decisions locked in the brainstorm (the design contract)

These are settled. Do not re-litigate; implement.

| # | Decision |
|---|----------|
| D1 | **Broad templates + catalog expansion (option C).** Every stream in the taxonomy (§2) gets a groundwork template. The catalog gains stream-appropriate boards, added as **full researched entries marked `status: unverified`**, not in any active tier until a live smoke test. |
| D2 | **One cross-pollinating catalog.** No hard tech/non-tech partition — a platform declares category slugs for whatever streams it supports; a scan uses whichever platforms have a slug for the profile's stream. A "marketing" board may surface a PM role and vice versa. |
| D3 | **Per-stream tier rotation.** A platform's tier is stream-dependent (tier-1 for PM can be tier-3 for sales). **Catalog owns platform capability** (slugs, fetch mode, quirks); **each template owns its stream's tier ordering** (seeds the profile's `platforms.tiers`). |
| D4 | **The setup skill is a CV-driven "templater".** It ingests the CV, classifies to stream/subvariant, and tailors the template. CV is **read to derive search config, never stored in the repo** (spec §1 rule 4 preserved). |
| D5 | **Templater guardrails.** May **reweight/select** from template-provided keyword + archetype sets and **add CV-obvious concrete tech terms** (e.g. "Spring Boot", "Kafka"). May **not invent** new filter types or archetypes — those come from the template. |
| D6 | **Write-back learning loop: opt-in, consented, generic-only, staged, human-reviewed (option a).** With consent, generic (non-PII) enrichments are **staged as suggestions** for a curator to approve into the template. No auto-merge yet (option b is a later upgrade once the pattern is trusted). |
| D7 | **Seniority is soft by default with an optional `strict` toggle.** `target_seniority` scores (target band highest; well-above deprioritized-with-note; below flagged) unless `strict: true` makes it a hard filter. Seniority is **orthogonal to role**: staff/principal are seniority levels on an engineering template, not separate templates. |
| D8 | **Employment type is hard by default with an "any" escape.** `employment_type` hard-filters to the chosen set (`full_time`/`part_time`/`contract`/`b2b`/`freelance`/`internship`); choosing **`any`** disables the filter. Documented caveat: a hard employment filter on sparse boards thins the ledger — that's the user's informed choice, and `any` is the escape hatch. |
| D9 | **Effort/model tier = compute tier, entitlement-shaped.** An `effort` field maps to a model (fast→Haiku, mid→Sonnet, high→Opus). Design target: **per-run-type (option b)** — cheap model for frequent sweeps, capable for the weekly deep sweep — with a **two-stage split (option c)** as default mechanism (cheap-model triage → capable-model shortlist read). The enum is shaped as a **future billing/entitlement axis** (free = low + unscheduled; paid = mid/high/weekly-deep/scheduled). |
| D10 | **Model-tier is design-and-defer for Phase 2 (option a).** Phase 2 defines the schema field + documents the mapping and the two-stage design. **Actual subagent-orchestrated wiring lands later, with scheduling** (model-at-launch lives with the scheduler, which is deferred). |
| D11 | **Provisioning takes token + parent-page as parameters, never hardcoded.** Borjan's workspace for the supervised trial; **per-user Notion is the end goal.** Token-paste + parent-page pick is a **discrete promptable step** (Phase 4 renders it as a field). Modes: **provision** or **adopt existing**. |
| D12 | **Scheduling stays deferred.** The interview **writes schedule config into `profile.yaml`** but does **not** wire the laptop task / cloud Routine (same manual gap as today). |
| D13 | **First test = backend-java, supervised, real scan, config-only schedule.** Acceptance: provision real Notion DBs under Borjan's workspace + **one manual live scan completes with an honest coverage ledger**; schedule written as config, cron not wired. |
| D14 | **Interview interaction posture is user-chosen.** At the start of the confirm phase the templater offers, with a friendly explanation, a choice between **(a) progressive** (confirm only high-impact/ambiguous fields, accept template defaults for the rest) and **(b) full field-by-field**. Not hardcoded. |
| D15 | **A profile may target a primary + optional secondary subvariant.** Keyword/archetype sets are **unioned** across the two; the **primary drives** the comp band and stream tier ordering. (A fullstack dev, or the Java case also taking broader JVM/backend roles.) A second distinct target = a second profile. |
| D16 | **CV strongly preferred but not required.** No-CV path = guided Q&A build (less auto-tailoring, same schema output). |
| D17 | **Notion access is instruct → verify-by-probe.** The integration-token creation + "share the parent page with the integration" click live in the Notion UI and cannot be scripted; the interview instructs the user, then verifies by a probe write and reports if access is missing. Honest, not pretend-headless. |
| D18 | **Secrets: capture once, store encrypted-at-rest per user, never in the repo.** Phase 2 designs the seam (profile references a secret; the value is captured once and stored encrypted, env fallback for the trial). End goal = the app manages accounts/login/configs/Claude-API + Notion connectors as a **full one-time setup** — Phase 2 must not preclude it. |
| D19 | **Provisioning is idempotent via a marker.** Re-running detects existing DBs (provisioning marker / title) and **adopts** them; never duplicates. |
| D20 | **No shipped salary numbers (option c).** Templates carry **`salary_estimation_heuristics` text only** — no hardcoded per-seniority band numbers (they'd be stale/country-wrong). Floor is **user-provided or unset**; when unset the judgment layer estimates from the posting per the template's heuristics. |
| D21 | **Seniority vocabulary = core base lexicon + template extensions.** `core` ships a base title→band lexicon (junior/mid/senior/staff/principal/lead…); templates extend it with stream/region-specific titles ("medior", "SDE II", "staff"). |
| D22 | **Part-time comp = pro-rate the floor to FTE fraction.** When a floor is set and the target/role is part-time, pro-rate the floor by an `fte_fraction` (default 0.5, user-tunable) before the salary comparison; day/hourly rates normalize via the existing `salary.py` period model. |
| D23 | **`borjan-pm` is production and sacred — see §0a (prime directive).** Phase 2 is **purely additive**; Borjan **keeps using the engine for his own job search throughout the build** (continuous dogfooding); his profile/state/history/Notion are never regressed, reset, or destructively migrated; and when the app ships he is **account #1** with everything carried in verbatim. This constraint outranks any Phase 2 convenience. |

## 2. Stream / subvariant taxonomy (the groundwork deliverable)

⭐ = build deepest + battle-test first. **backend-java is the live test case.** `✅` = already exists.
Business streams get solid groundwork templates now but are marked **"catalog coverage pending
dogfood"** (their best boards are the new unverified ones).

- **software-engineering** ⭐
  - frontend: react ✅, angular, vue, svelte
  - web-dev: wordpress, headless-cms, shopify-ecommerce, webflow-no-code
  - backend: **java** ⭐, node, python, dotnet, go, ruby, php
  - fullstack: js, python
  - mobile: ios, android, react-native, flutter, tvos, android-tv
  - devops-sre-platform
  - embedded
  - security-appsec
  - game-dev: unity, unreal, gameplay
  - leadership (own subvariants, distinct keywords/archetypes): engineering-manager, tech-lead
- **ai-ml** ⭐ — ai-engineer (llm/genai), ml-engineer, mlops, computer-vision, nlp, ai-research, prompt-engineer
- **qa** ⭐ — manual, automation-sdet, performance
- **data** ⭐ — data-analyst, data-scientist, analytics-engineer, bi, data-engineer
- **design-ux** ⭐ — product-designer, ux-researcher, visual-graphic, design-systems
- **product-management** — delivery-manager ✅, scrum-master, technical-pm, product-owner, product-manager, program-manager, release-manager, business-analyst
- **marketing** — growth, content, product-marketing, performance-paid, seo, social, lifecycle-crm
- **sales** — sdr-bdr, account-executive, account-manager, sales-engineer, customer-success
- **people-hr** — recruiter-talent, people-ops, hr-business-partner, learning-development
- **it-support** — technical-support, customer-support, helpdesk, sysadmin, network-admin
- **content-writing** — technical-writer, copywriter, content-creator, content-strategist

Notes for the build:
- **Seniority orthogonal to role** (D7): no `senior-*` / `principal-*` templates — `target_seniority` on the base subvariant.
- **Overlap is expected** (data-engineer ∈ SE ∩ data; sales-engineer ∈ sales ∩ SE; ai spans SE/data). The templater resolves overlap by asking the user (§4 step 3); templates may `suggest_also` their neighbors.
- **Depth tiers:** ⭐ streams get full keyword sets (core+expanded), archetypes, scoring bands, salary heuristics, seniority→comp tables, per-stream platform tiers, interview hints, and a `--plan` smoke test. Business/support/content streams get the same shape at groundwork depth, honestly marked unverified where the catalog can't yet serve them.

## 3. Schema, catalog & template-format changes

### 3.1 Profile schema additions (`core/schema/profile.schema.yaml` + `validate.py` + `profile_loader.py`)

Additive and **non-breaking** — `borjan-pm` must still validate (fields default to current behavior).

```yaml
search:
  stream: software-engineering         # existing
  subvariant: backend-java             # existing (primary)
  subvariant_secondary: null           # NEW (D15): optional; keyword/archetype sets unioned, primary drives comp+tiers
  work_model: [remote]                 # existing; enum remote|hybrid|on_site (already present)
  target_seniority:                    # NEW (D7)
    bands: [mid, medior]               # enum: intern|junior|mid|medior|senior|staff|principal|lead|manager
    strict: false                      # false = scoring input; true = hard filter
  employment_type:                     # NEW (D8)
    accept: [part_time, contract]      # enum: full_time|part_time|contract|b2b|freelance|internship|any
                                       #   'any' present in list = filter disabled
compensation:
  floor: null                          # NEW default (D20): user-provided or unset; no template numbers shipped
  fte_fraction: 0.5                    # NEW (D22): pro-rates the floor for part-time targets; default 0.5, tunable
run:
  effort: mid                          # NEW (D9/D10): fast|mid|high  -> model tier; entitlement-shaped
  effort_by_run_type:                  # NEW, optional: per-run-type override (design target b)
    daily: fast
    weekly_deep: high
```

- `experience_years` stays (actual experience); `target_seniority` is what they want to *see*
  (the two differ in the Java case). The templater sets `target_seniority` from CV + stated goal.
- Validator: unknown enum value = named refusal (spec §1 rule 3). `any` in `employment_type.accept`
  is mutually exclusive with other values (validate and error if mixed).
- `run.effort*` are recorded + documented in Phase 2; **not wired to actual model selection yet** (D10).

### 3.2 Catalog changes (`catalog/platforms.yaml`)

- **Per-stream category slugs** already the design (`categories: {stream: slug}`); extend the maps to
  the new streams for every existing platform **that genuinely has a category** — leave absent where
  none exists (engine already emits "no category mapping" honestly).
- **New platforms** (stream-appropriate boards for marketing/sales/people-hr/design/support/etc.):
  add **full researched entries** (`fetch_mode`, `url_pattern`, `expired_markers`, `quirks`,
  category slugs) with `status: unverified`. They are **not** placed in any profile's active tiers
  until a live smoke test flips them verified. Research the entries; do not stub.
- **Per-stream tiers live in templates, not the catalog** (D3). Keep `tier_default` in the catalog as
  a last-resort fallback only; the authoritative per-stream tier ordering is template data.

### 3.3 Template format v2 (`templates/<stream>/<subvariant>.yaml`, PROFILE_CONFIG_SPEC §6)

Extend the existing format with:
- `platform_tiers:` per-stream tier ordering (seeds `profile.platforms.tiers`) — **new, per D3**.
- `salary_estimation_heuristics:` stream-specific **text only** — **no hardcoded band numbers** (D20).
  The floor is user-provided or unset; when unset the judgment layer estimates from the posting using
  this text. (Replaces the earlier numeric `seniority_comp_bands` idea, which would ship stale/
  country-wrong numbers.)
- `seniority_titles:` template extensions to the core seniority lexicon (D21) — stream/region-specific
  titles ("medior", "SDE II", "staff engineer") mapped to the base bands.
- `interview:` hints block already specified (emphasize / skip_if_defaulted) — use it.
- Inheritance chain unchanged: `stream defaults → subvariant → variant → user answers`, deep-merged,
  result must validate as a full profile.

**New core artifact:** `core/data/seniority_lexicon.yaml` — the base title→band lexicon (D21),
extended per-stream by templates' `seniority_titles`. Consumed by the judgment layer to map a
posting's stated level to a band for `target_seniority` scoring/filtering.

## 4. The setup interview / templater (`skills/job-scout-setup/SKILL.md`)

Conversational flow in Claude Code. Every step is **scriptable/promptable** (Phase 4 constraint) —
no step exists only as human-readable prose.

1. **Kickoff** — request CV (PDF or pasted text) + optional target-role note / hard constraints
   (location, must-be-part-time, salary floor if known). **CV preferred, not required** (D16): if none,
   fall back to a guided Q&A build (same schema output, less auto-tailoring).
2. **Extract** — read CV (or run the Q&A) → structured extract: titles, years, tech/skills, domains,
   seniority signals, location, languages. **CV read, never written to the repo** (D4).
3. **Classify** — extract → stream + **primary subvariant**, and optionally a **secondary subvariant**
   (D15) if the CV/goal spans two (e.g. broader JVM/backend). Clear match → confirm. Ambiguous/multi →
   present top candidates (use templates' `suggest_also`), user picks primary (+ optional secondary).
   No-match → nearest stream + generic subvariant, **log a template-gap** (feeds library growth).
4. **Consent gate** — ask permission to stage anonymized write-back learnings (D6). Record the answer.
5. **Tailor** — deep-merge template defaults (primary; **union** primary+secondary keyword/archetype
   sets per D15); apply CV enrichments within guardrails (D5): reweight/select keyword+archetype sets,
   add CV-obvious concrete tech terms; set `target_seniority` (actual vs target), `employment_type`,
   `work_model`. **Comp: do not fabricate a floor** (D20) — take it from the user if stated, else leave
   unset for judgment-time estimation via the template's `salary_estimation_heuristics`; set
   `fte_fraction` for part-time targets (D22).
6. **Confirm interview** — first offer the user a choice, with a friendly explanation, between
   **(a) progressive** (confirm only high-impact/ambiguous fields, template defaults for the rest) and
   **(b) full field-by-field** (D14). Then run the chosen posture; surface `target_seniority.strict` and
   the `employment_type: any` escape. Never ask what a template default already answers (spec §1 rule 2).
7. **Provision → persist → validate** — run `provision_notion` (§5) → write `profiles/<id>/profile.yaml`
   → `validate.py` (refuse to proceed on any error) → write `schedule:` config (cron **not** wired, D12).
8. **First run** — offer `core/scan.py --profile <id> --plan` (dry-run) then one live scan; review the
   ledger together.
9. **Write-back** — if consented (step 4), extract **generic** enrichments (no PII/CV text) and stage
   them for curator review (§6).

The interview skill itself runs on a capable model (CV understanding + classification are reasoning-
heavy) — this is separate from the profile's scan-time `run.effort`.

## 5. Notion provisioning (`core/provision_notion.py`, NEW)

- Inputs: `--token` (or `NOTION_TOKEN` env) and `--parent-page-id`, **explicit params, never hardcoded**
  (D11). For the trial these are Borjan's; the design assumes each user brings their own later.
- **Access is instruct → verify-by-probe (D17):** the token creation + the Notion-UI "share the parent
  page with the integration" click cannot be scripted. The interview **instructs** the user through
  those steps, then **probes** (a test write / metadata read) and reports clearly if the integration
  lacks access — no pretending it's fully headless.
- **provision mode:** create **Applications Tracker** (status select w/ the six canonical options,
  Source, Date Applied, Fit Score, Keyword Source, Notes), **Passed/Seen Log** (Status incl.
  `New — Unreviewed` / `Stale/Expired`, Reason Passed, Platform select, Job URL, Fit, Archetype),
  the **Runs** digest page, and the **📥 New — Unreviewed** view under the parent page; lazy-patch
  platform select options before first write (mechanism exists today); write resulting IDs into
  `profile.output.notion`.
- **adopt mode:** point at existing `data_source_id`/`page_id`s, **verify schema compatibility, report
  gaps**, do not mutate beyond additive select options.
- **Idempotent via a marker (D19):** re-running detects existing provisioned DBs (a provisioning
  marker / known titles under the parent) and **adopts** them — never creates duplicates.
- This is the only component needing Notion **write** scope.

**Secret-storage seam (D18):** the Notion token (and later the Claude API key + other connectors) is
**captured once and stored encrypted-at-rest, keyed to the user/profile — never committed to the repo.**
The profile stores a *reference* to the secret, not the value. Phase 2 builds the minimal seam (encrypt
+ store + resolve at runtime, with `NOTION_TOKEN` env as the trial fallback); the full account/login/
config/connector management is the app layer (Phase 4/5), and this seam must not preclude a **one-time
setup** there.

## 6. Write-back learning loop (opt-in, staged, human-reviewed)

- Gate: only runs if the user consented at step 4 (D6).
- Extract **generic** enrichments only — keyword/archetype-set additions that are role-generic
  (e.g. "Kafka" for backend-java), **never CV text, names, employers, or any PII**.
- Stage, don't merge: append to a per-template review queue (e.g.
  `templates/<stream>/<subvariant>.suggestions.yaml` or an equivalent staging file), with provenance
  (source profile id, date, frequency counter) but **no personal data**.
- Curator approves suggestions into the template (Borjan for now). Auto-merge-with-guardrails is a
  **later** upgrade (D6 option b) once the pattern is trusted.

## 7. Effort / model tier + two-stage judgment (design-and-defer, D9/D10)

- **Now:** define `run.effort` (+ optional `effort_by_run_type`) in the schema; document the mapping
  (fast→Haiku, mid→Sonnet, high→Opus) and the **two-stage design** (cheap-model triage of the raw
  candidate list → capable-model deep-read of the shortlist, via subagent delegation) in the run skill
  and here. Note the entitlement shape (free = low + unscheduled; paid tiers unlock mid/high/weekly-
  deep/scheduled).
- **Deferred (with scheduling):** actually wiring model selection — the scheduler chooses the launch
  model per run type, and/or the judgment step spawns a subagent at the chosen model. Not built in
  Phase 2 because model-at-launch belongs with the (deferred) scheduler.

## 8. First real test — backend-java engineer (acceptance, D13)

- Persona: senior Java backend engineer, post-break, targeting **mid/medior part-time** to survey the
  market. Real CV provided by Borjan.
- Run the **full interview** end-to-end → `backend-java` classification (optional secondary subvariant
  if he'd take broader JVM/backend, D15) → tailoring (Java/Spring/Kafka concrete terms,
  `target_seniority: {bands: [mid, medior], strict: false}`, `employment_type: {accept: [part_time,
  contract]}`, `fte_fraction: 0.5`, **floor left unset unless he states one**, D20/D22) → provision under
  **Borjan's Notion** (supervised, instruct→verify-by-probe) → validate → **one manual live scan** with
  an honest coverage ledger → schedule config written, cron not wired.
- **Acceptance:** valid non-PM profile produced by the interview; provisioning creates real DBs;
  one live scan completes with a sane ledger and correct catalog URLs/keywords/filters for the stream;
  seniority/employment-type semantics behave (mid roles surface, senior deprioritized-with-note, part-
  time honored per D8, floor pro-rated by FTE if he set one per D22). Capture lessons into the profile /
  skill / catalog per the friction-logging culture.

## 9. Ordered build checklist (seed into PROGRESS.md Phase 2 table)

Ordered so nothing breaks `borjan-pm` (which stays production) at any step.

| # | Step | Notes |
|---|------|-------|
| 2.0 | **Pre-build review gate (Fable 5)** — one scoped adversarial review of this plan; amend for any blocking findings (D1–D23 intact) before 2.1 | §12.1 |
| 2.1 | **Schema extensions** — add `target_seniority`, `employment_type`, `subvariant_secondary`, `compensation.fte_fraction`, `run.effort(+by_run_type)` to `profile.schema.yaml` + validator + loader; update PROFILE_CONFIG_SPEC §2/§3. `borjan-pm` still validates. | §3.1, D14–D22 |
| 2.2 | **Template format v2** — `platform_tiers` + `salary_estimation_heuristics` (text, no numbers) + `seniority_titles` + inheritance/loader; add `core/data/seniority_lexicon.yaml`; update spec §6. | §3.3, D20–D22 |
| 2.3 | **Catalog expansion** — per-stream slug maps for existing platforms; add new stream-appropriate boards as **full `status: unverified` entries**; per-stream tiers move to templates. | §3.2 |
| 2.4 | **Template library** — build the §2 taxonomy: ⭐ tech-core deepest + battle-tested (incl **backend-java**), business/support/content as groundwork marked coverage-pending. | §2 |
| 2.5 | **`core/provision_notion.py`** — provision + adopt modes, token/parent params, instruct→verify-by-probe, idempotent-via-marker, lazy select patch; **secret-storage seam** (encrypt/store/resolve, env fallback). | §5, D17–D19 |
| 2.6 | **`skills/job-scout-setup/`** — the templater/interview skill: CV-or-Q&A, primary+secondary subvariant, user-chosen posture, full step sequence. | §4, D14–D16 |
| 2.7 | **Write-back loop** — consent gate, generic-only extraction, staged suggestions, curator merge path. | §6 |
| 2.8 | **Effort/model tier** — schema field + documented mapping + two-stage design (wiring deferred). | §7 |
| 2.9 | **First real test** — backend-java onboarding end-to-end; supervised live scan; capture lessons. | §8 |
| 2.10 | **CI** — extend `validate-platform` to cover new schema/templates/catalog; every template validates; per-⭐-template `--plan` smoke where catalog supports. | — |
| 2.11 | **Docs** — update ARCHITECTURE (job-scout-setup, provision_notion, write-back), PROFILE_CONFIG_SPEC (new fields, template v2), PROGRESS. | — |

## 10. Out of scope for Phase 2

- Wiring actual schedules (laptop task / cloud Routine) — deferred (D12).
- Wiring actual model selection / subagent two-stage judgment — designed, deferred to scheduling (D10).
- Billing/subscription enforcement — the `effort` enum is only *shaped* for it (D9).
- Per-user Notion multi-tenancy beyond token/parent-page parameterization — trial runs under Borjan's
  workspace (D11).
- The **full account/login/config/connector management** (Claude API + Notion connectors, one-time
  setup) — Phase 2 builds only the encrypted secret-storage *seam* (D18); the account system is the
  Phase 4/5 app layer.
- Auto-merge of write-back suggestions — human-reviewed only for now (D6).
- The Phase 3 Application Assistant and Phase 4 FE app.

## 11. Guardrails carried from Phase 1 (do not regress)

- **`borjan-pm` stays production and sacred — the prime directive (§0a / D23).** Nothing in Phase 2
  may break its scans, state, history, or Notion writes; Borjan keeps using it for his own search
  throughout; additive-only, no destructive migration, account #1 carried in verbatim at app time.
- Scanner **never** writes the Applications Tracker (invariant); Passed/Seen Log is the scanner's only
  write target; the sweep owns staleness.
- Strict validation: invalid profile/template/catalog = **refuse the run with a named error**.
- Coverage honesty: a platform with no slug for a stream is **skipped-with-honesty in the ledger**,
  never silently.
- CV/PII never enters the repo (D4) or write-back suggestions (D6).

## 12. Execution handoff — models, effort, and the pre-build review gate

Recommended pipeline: **plan (done) → Claude Fable 5 pre-build review → Claude Opus 4.8 build.**
Put the most-capable model where judgment on the finished spec pays off (adversarial review of a
complex artifact), and the cost-efficient model on the high-volume execution.

### 12.1 Pre-build review gate (step 2.0) — Claude Fable 5

Before any build step, run **one scoped adversarial review of this plan** on Claude Fable 5. Purpose:
catch structural gaps before they propagate into 12 templates + the setup skill + provisioning. Scope
it tightly — the review hunts for blocking risks, not restyling or new scope. Review prompt:

> Read `docs/PROGRESS.md`, then `docs/PHASE_2_PLAN.md` in full. Act as a pre-build reviewer of
> `PHASE_2_PLAN.md`. Hunt ONLY for **structural gaps, contradictions, unstated assumptions, and
> checklist-sequencing risks** that would cause the Phase 2 build to fail or require rework. Do NOT
> re-litigate the locked decisions D1–D23, and do NOT propose new scope/streams. Output a short
> prioritized list of genuine risks, each with a one-line suggested fix — or "no blocking issues
> found." Do not change any files — this is review only.

Effort: **xhigh** (bounded one-shot, high leverage — worth the depth; `high` is the acceptable floor).
Address any *blocking* findings by amending the plan (keeping D1–D23 intact) before starting 2.1;
non-blocking suggestions are optional.

### 12.2 Build model + per-step effort — Claude Opus 4.8

Build on `claude-opus-4-8`. A well-specified checklist is execution, not open-ended reasoning —
Fable 5's edge doesn't pay off here and draws ~1.5–2× the usage. Default effort **`high`**; tier it:

| Steps | Effort | Why |
|-------|--------|-----|
| 2.4 (bulk template YAML), 2.10–2.11 (CI, docs) | `medium` | mechanical, well-patterned |
| 2.1–2.3 (schema/catalog/format), 2.7–2.8 (write-back, effort-tier) | `high` | real design surface, bounded by spec |
| 2.5–2.6 (provisioning, CV templater skill), 2.9 (live test) | `xhigh` | trickiest logic + the end-to-end test |

Escalate a single step to Fable 5 only if it turns out genuinely hard/ambiguous mid-build.
