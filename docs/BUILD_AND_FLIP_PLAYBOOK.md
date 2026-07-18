# Build-and-Flip Playbook — a reusable framework (product-agnostic)

> **Meta doc.** This is *not* specific to the job-scout platform — it's the **repeatable process**
> for building AI-native, quality-first products that can be run as a business or sold on a
> marketplace, extracted from what's working on this project. Captured here for now (2026-07-18);
> lift it into its own repo when the second app starts. The idea (Borjan): once we have a process,
> reuse it to build → flip → build the next → repeat (and maybe, eventually, our own marketplace).

## Why write the process down

The valuable, transferable asset across apps isn't any one product — it's the **method**. If each
app is built the same disciplined way, the second is faster, the tenth is a machine, and each one
is *born sellable* (clean diligence, real retention hooks, low COGS) instead of retrofitted.

## The method (what's working here)

### 1. Documentation-first, plan-of-record
- **One source of truth** for vision/scope/principles (here: `PROJECT_PLAN.md`).
- **A session-resume contract** the build never violates (here: `PROGRESS.md` — read first, never
  redo done steps, update in the same session, push before ending).
- **Per-phase detailed plans** written just before each phase (plans go stale — write them late).

### 2. The build pipeline (per phase)
**brainstorm → detailed plan → adversarial review gate → build → human-readable docs.**
- Design interactively with the owner; lock decisions as a numbered contract (don't re-litigate).
- **Review gate:** a *different, stronger-reasoning* model does a scoped adversarial review of the
  plan (here: Fable 5 @ xhigh) and amends blocking findings *before* code.
- **Build** with per-step effort tiering (mechanical = low/medium; real design = high; live
  judgment = xhigh) and an auto-escalation rule when a step exceeds its spec.
- Every phase **ends with a human-readable doc update** — a phase isn't done until the plain-language
  guide reflects it.

### 3. Standing principles (adopt on day one)
- **Prime directive:** production is sacred — new work is purely additive, never regresses the
  live thing; prove it (byte-identical checks, CI green) every step.
- **Data & privacy principle:** the user owns their data, it's deletable, never mined; design the
  storage boundary so it can move client-side later.
- **Honest-failure:** the system degrades *visibly*, never silently-wrong (honest ledgers,
  source-down reporting, "insufficient data" beats a guess).

### 4. Build for a real first user (dogfood)
- Onboard an actual user (here: Borjan, then Ani) and run a **supervised live acceptance (UAT)**
  against real data. Dogfooding surfaces the gaps specs miss (e.g. field-size limits, data hygiene).
- **Lessons become rules:** generic lessons → the engine/docs; user-specific → the profile;
  environment frictions → the changelog.

### 5. AI-native architecture
- **Two-layer split:** cheap mechanical scripts *flag*; the capable model *decides* ("scripts flag,
  Claude decides"). Keeps COGS down and quality up.
- **Wrap the model** (Agent SDK / API), don't reinvent it; the app is a face on the skills.
- **Prompt-as-interaction-unit:** capture every tuned prompt in a **guided-flow library**; the app
  is a thin UI trigger over curated prompts (here: `assistant/GUIDED-FLOW.md`).
- **Observability + self-healing from the start:** progress output, health monitoring of external
  dependencies, honest telemetry (here: `HEALTH_MONITORING.md`).

### 6. Quality bars (non-negotiable)
- CI/validation green before merge; small, reviewed PRs; feature branches per phase.
- No secrets/PII in the repo; a defined no-PII discipline.
- Every externally-fragile dependency (scraped source, third-party API) has a health signal + a
  repair path.

### 7. The repeatable phase shape
engine/core → templates + guided setup → the AI companion (voice/KB/loop) → the app + client-side
store → platform + integrations + accounts/tiers → **GTM / marketing & sales prep** → run or sell.

## The starter kit — concrete reusable assets (with pointers)

The method above is the *how*; this is the *what to lift*. A deep pass over this repo (2026-07-18)
sorting every asset into **reusable → genericize** vs **product-specific → leave**. For the next
app, copy the left column, strip the domain nouns, keep the machinery. Together these are ~70% of a
new AI-native product's scaffolding before you write a line of domain logic.

### A. The documentation skeleton — lift the shapes, empty the content
The whole `docs/` system transfers as templates:
- **`PROJECT_PLAN.md`** — vision + standing principles + phase map + §3x parked-ideas + execution
  discipline. The single source of truth. *(Reusable structure; swap the product.)*
- **`PROGRESS.md`** — the session-resume contract (read-first, never-redo-done, update-in-session,
  push-before-end) + per-phase checklists + session log. **The biggest single reuse** — it's the
  multi-session-build discipline itself.
- **Per-phase `PHASE_N_PLAN.md`** + the **review-gate prompt** (see PHASE_3A_PLAN §11.1) + the
  **`*_ACCEPTANCE.md`** live-UAT runbook shape.
- **`ARCHITECTURE.md`**, **`*_CONFIG_SPEC.md`**, **`PLATFORM_GUIDE.md`** (plain-language guide),
  **`HEALTH_MONITORING.md`**, **`GUIDED-FLOW.md`** (prompt library), and this playbook +
  `BUSINESS_NOTES.md`. All shape-reusable.

### B. The layered config architecture — the crown jewel
A three-layer config system: **registry (capabilities) + templates (type presets) + instances
(the specific user/tenant) → one resolved effective config**, schema-validated in CI.
- **`core/profile_loader.py`** — the resolver: merges registry + template + instance, applies
  extends-chains, emits the effective config; strict validation with named errors/warnings.
- **`core/schema/*.yaml`** + **`core/validate.py`** — schema-driven validation wired to a **single
  CI required check** (compiles code + validates every template/instance + state integrity + skill
  frontmatter).
- **`core/paths.py`** — instance-namespaced state resolution (explicit → env → auto-pick), so the
  system is multi-tenant from day one.
- Directory layout: `catalog/` (registry) · `templates/<stream>/` (presets) · `profiles/<id>/`
  (instances) · `suggestions/` (staged write-back) · `assistant/` (companion package).
- **Genericize:** rename `profile`→`instance/tenant`, swap the domain fields in the schema, keep
  the merge/resolve/validate machinery verbatim.

### C. AI two-layer architecture + the companion binding
- **`core/scan.py` shape** — a *mechanical orchestrator* that emits structured JSON for a *model
  judgment* layer ("scripts flag, the model decides"); `--plan` dry-run, `--verbose` progress, an
  honest ledger. Reuse the split, not the board logic.
- **`core/compose_assistant.py` + `assistant/`** — bind a repo's config to a **claude.ai Project**:
  a PII-free config snapshot + generic doctrine composed into a **bootstrap (→ custom instructions)
  + full doc (→ Project knowledge)**, compose-date + config-hash stamped, idempotent. This
  "companion binding" is reusable for *any* claude.ai-Project-backed product.
- **`assistant/GUIDED-FLOW.md`** — the curated-prompt library (UI trigger → background prompt).
- **`skills/*/SKILL.md`** — frontmatter conventions + the router pattern (load only what the task
  needs) + the skill-audit discipline.

### D. State, data & external-integration patterns
- **`core/dedup.py`** — append-only last-wins JSONL event log with idempotent supersede + normalized
  matching. A reusable *event-log + provenance* pattern (swap the match keys).
- **`core/state_sync.py`** — git round-trip for instance state, union-merge on concurrent writes.
- **`core/secrets.py`** — the secret seam (resolve token via override → env, never in repo).
- **`core/provision_notion.py`** — idempotent **provision-or-adopt** of external resources with
  **instruct→verify-by-probe** (probe the API first; script what's scriptable, flag what isn't).
- **`core/notion_sync.py`** — typed external writes with **post-write assertion**, a
  **tokenless→pending-export** fallback (hand off to an MCP session), and **write-ownership
  partitioning** (two processes can't collide). Reusable for any external system of record.
- **`core/sweep.py`** — rate-limited periodic re-check of an accumulated queue (freshness/liveness).
- **`core/writeback.py`** — a consent-gated, PII-guarded, **staged + human-curated feedback loop**.

### E. External-dependency resilience
For any product standing on fragile external sources/APIs: **honest-failure** (report degraded,
never silently-wrong) + `fetch_evidence`-style telemetry + the **scheduled health-review + repair**
loop in `HEALTH_MONITORING.md` (Layer-1 signal emitter + Layer-2 diagnose/repair on a cadence).

### F. Process & quality artifacts
- The **Fable-5 adversarial review-gate prompt**, the **effort-tiering table**, the **no-PII
  denylist**, the **prime-directive byte-identical proof**, feature-branch-per-phase + small PRs +
  a single required CI check. All lift as-is.

### What does NOT transfer (product-specific — leave it)
`core/fetch_boards.py`, `render.py`, `check_links.py`, `linkedin_tripwire.py`, `salary.py`,
`core/data/seniority_lexicon.yaml`, the `catalog/` + `templates/` *content*, and the job-hunt
doctrine. The *shapes* around them (fetch→judge, registry+template+instance, voice/KB) reuse; the
domain logic is thrown away and rewritten. `migrate_state.py` / `parity_diff.py` are one-off
migration tools, but the *parity discipline* (prove byte-identical vs a baseline) reuses.

> **Turn this into an actual starter repo when app #2 begins:** copy A–F, delete the "does not
> transfer" list, empty the schema + docs of job-scout nouns, and you have a validated, CI-green,
> companion-bindable, multi-tenant skeleton on day one.

## Build *for the flip* (bake valuation in from day one)

A product is worth a multiple of **revenue × retention × defensibility**, discounted for risk
(see `BUSINESS_NOTES.md`). So design these in from the start rather than retrofitting:
- **A retention hook** (here: the compounding user-owned voice/KB) — the single biggest valuation lever.
- **Low, legible COGS-per-user** — track it as a first-class metric from user #1.
- **Clean diligence** — no ToS/legal landmines (prefer official APIs / user-owned data exports over
  scraping where possible); reduce founder-dependency (docs, scripts, no tribal knowledge).
- **A B2B/white-label path** — lower churn, higher WTP, more sellable than churny consumers.
- **Instrumentation for the data buyers want:** MRR, churn, cohort retention, CAC, COGS — from the
  first paying user, because that data *is* the valuation.

## Parked (far-out)
- **Our own flip marketplace** — once we've flipped a few apps the same way, a marketplace/brand
  around the method itself. Note only; no action.
