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
