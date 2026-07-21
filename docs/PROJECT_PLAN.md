# Job Scout Platform — Project Plan

> Master plan for evolving `job-scout-pm` (a single-person, single-role skill) into a
> profile-agnostic job-search platform. This document is the entry point: it defines the
> vision, the phase boundaries, what is explicitly out of scope per phase, and the
> execution discipline for multi-session builds. Architecture details live in
> [ARCHITECTURE.md](ARCHITECTURE.md); the profile/template configuration contract lives in
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md); live build state lives in
> [PROGRESS.md](PROGRESS.md).

Status: **living document — source of truth for the vision** · Created: 2026-07-13 ·
Vision expanded 2026-07-17 (Phase 3 companion brainstorm)

---

## 1. Vision (end goal, NOT the next phase)

A career platform — on laptop, mobile, and web — that finds you the right jobs **and helps
you actually land them**, in your own voice, without ever mining your data. Two halves:

**The scanner (built — Phases 1–2).** You install it, pick what kind of job you're after,
tune the criteria on a screen; it scans job boards on a schedule, keeps a clean live
shortlist, and retires postings that die. Claude does the scanning judgment.

**The companion (Phase 3 onward).** The shortlist is where the scanner ends and the
companion begins. The companion is built on **two assets that are genuinely yours and grow
every time you use it**:

- **Your voice** — learned from things you've actually written (cover letters, articles,
  anything with your fingerprint on it), or built through guided questions if you have
  none. Distilled into a reusable profile so every draft sounds like *you*, not like an AI.
- **Your knowledge base** — your real experience, projects, past answers, domain facts.
  The source of *honest* answers: it never invents experience; when it doesn't know, it
  says so, you fill the gap, and the base grows.

On top of those two assets, the companion: **drafts applications** in your voice and
records them; **walks you through interviews** (reads the JD, predicts questions, maps your
real experience onto the role's gaps); **debriefs** after and turns honest feedback into
next-time improvement; **keeps your CV sharp** (assesses it, flags when it's stale, guides
the rewrite, ingests "delta" updates); and **helps you write and publish** (blog posts,
articles) — which makes you a stronger candidate *and* feeds fresh voice + knowledge back
into the loop. **Claude is the engine; your data is the store — never the other way round.**

**The product around it.** The end state is a real product: accounts with a one-time setup
(Claude, Notion/your store, connectors), a proper client-side data store (not Notion, not a
Claude Project — see the data principle in §1a), and **free vs paid tiers** (free = light,
unscheduled; paid = deeper models, scheduled scans, weekly-deep passes). Multi-tenant from
the storage up, so it serves many users — with Borjan as account #1, carried in verbatim.

Everything below is staged so each phase ships something usable on its own, and nothing in
an early phase has to be thrown away later. The phase count is deliberately open — we'd
rather add a phase than cram or drop a piece of this.

## 1a. Standing principles (two co-equal constraints)

Everything in every phase is built under both of these. Neither is negotiable for a
convenience.

1. **Prime directive — `borjan-pm` and the scanner are production and sacred.** Borjan uses
   the scanner daily; it must keep working, unchanged in behavior, through every later
   phase. New work is additive; state/history is never destructively migrated; the Tracker
   write firewall (the scanner never writes the Applications Tracker) is never weakened.
   (Full statement: PHASE_2_PLAN §0a.)
2. **Data & privacy principle — your data is yours, and we don't mine it.** The user owns
   their CV, voice, and knowledge base; they can delete any of it at any time; it is used
   only to serve *their own* applications, never for training or any secondary use. The
   destination is **client-side storage** (on the user's device / under the user's control),
   with **Claude called as a stateless engine** (the API doesn't train on inputs by default)
   — never a server-side vault. Honest interim: Phase 3 prototypes on a claude.ai Project +
   Notion, which *are* server-side; that is a knowing, consented compromise for the trial
   (Borjan, his own data), and moving off it to the client-side store is a **planned Phase 4
   deliverable, not a maybe** (the `secrets.py` seam and the "storage adapter boundary" in
   ARCHITECTURE §8 already anticipate it). We build toward strict GDPR compliance from here.

## 2. What exists today (the starting asset)

`job-scout-pm` v3.1.2 — a working, scheduled, three-lane scanning system for one profile
(Borjan, Senior PM / Delivery Manager / Scrum Master, remote, salary-floored):

- **Scripts** (~2,000 lines, already mostly generic): orchestrator, per-platform
  fetchers with API→direct→headless→mirror fallback, liveness checker with evidence log,
  dedup over an append-only history, headless renderer, Notion sync, git state sync.
- **`config.yaml`**: 23-platform registry with tiers, fetch modes, quirks — but with
  PM-specific search URLs and keywords baked in, plus Borjan-specific filter values.
- **`SKILL.md`**: the policy/judgment layer — 13 hard filters, scoring bands, archetype
  tags, platform knowledge, output discipline — with Borjan's candidate profile and
  PM-specific rules woven through it.
- **State + Notion**: `seen.jsonl` dedup history, Applications Tracker + Passed/Seen Log
  databases, pinned digest page, git-hosted state convergence across laptop and cloud.

The core insight driving this plan: **the scripts are already ~90% profile-agnostic; the
profile is smeared across `config.yaml` and `SKILL.md`.** The work is separation, not a
rewrite.

## 3. Phase map

| Phase | Deliverable | Runs where | Status |
|-------|-------------|-----------|--------|
| **0** | This documentation set | — | ✅ built |
| **1** | **Core engine extraction**: profile-agnostic `core/`, platform catalog, profile config schema, `borjan-pm` as the first profile, **shortlist liveness sweep**, parity cutover | Claude Code (laptop + cloud), unchanged lanes | ✅ built |
| **2** | **Template library + setup interview**: role templates with subvariants, a conversational setup skill that provisions a new profile end-to-end (config + Notion databases + schedule) | Claude Code | ✅ built |
| **3** | **Application Companion**: learn the user's voice + build their knowledge base, then draft applications, run interview prep + debrief, keep the CV sharp, and coach writing — the shortlist role-by-role apply loop and everything downstream. Staged **3a → 3b → 3c**. | claude.ai Project (+ Notion MCP), storage option (a) | next |
| **4** | **The app + client-side store**: a desktop/web app that drives Claude (Agent SDK / API) — install, options screens mirroring setup, run/schedule control, shortlist + companion views — and **migrates storage to the client-side/GDPR store (option b)** off Notion + Claude Project | Desktop / local web | after 3 |
| **5** | **Platform + integrations**: mobile, accounts + one-time setup, free/paid tiers, hosted scanning, and the heavy integrations (scoped email OAuth ingest, LinkedIn *export* ingest) | Mobile + laptop + web | after 4 |

### Phase 1 — Core engine extraction (the next build)

**Goal:** one unchanging engine, N profiles. The engine reads a profile config at run
start; nothing role- or person-specific remains in engine code or the generic skill.

Scope:

1. **Repo restructure** to the target layout (see ARCHITECTURE.md §2): `core/`,
   `catalog/`, `templates/`, `profiles/`, `skills/`.
2. **Three-layer config split** (ARCHITECTURE.md §3): engine code / shared platform
   catalog with parameterized search URLs / per-profile config. Every value the current
   system hardcodes for PM/Borjan becomes a profile field: keywords, work model, salary
   (value + currency + gross|net + per month|day|year|hour), location & eligibility,
   timezone window, travel tolerance, filter toggles, scoring rubric inputs, archetypes,
   platform tiers (tiers are per-profile conversion data, not global truth), Notion
   targets, schedule.
3. **Generic scan skill** (`skills/job-scout-run/`): the SKILL.md judgment layer rewritten
   to read filters/scoring/profile facts from the profile config instead of stating them
   inline. Hard-won generic lessons (liveness definition, dedup rules, coverage honesty,
   country-clone pattern, snippet-blindness, Tracker write firewall) stay in the skill —
   they are engine policy, not profile data.
4. **Validator stays in core**: config/schema validation, liveness verification, dedup,
   state integrity, coverage ledger — all engine responsibilities, identical for every
   profile.
5. **Shortlist liveness sweep (new feature)**: every scan run re-checks the liveness of
   accumulated `New — Unreviewed` shortlist entries and retires the ones that died since
   they were shortlisted (see ARCHITECTURE.md §6). This is what makes "collect for a few
   days, apply later" safe.
6. **Parity cutover for `borjan-pm`**: the existing scan keeps running untouched until
   the new engine, fed by `profiles/borjan-pm/`, reproduces its behavior (same platforms
   fetched, same dedup decisions, same Notion writes). Then the schedules point at the
   new engine and `job-scout-pm/` is reduced to a frozen archive. Strangler pattern — no
   flag-day rewrite, no scan downtime.

**Acceptance criteria:**

- A second demo profile (e.g. `fe-react-engineer`, non-provisioned/dry-run) passes config
  validation and produces a coherent scan plan (correct catalog URLs, keywords, filters)
  with **zero engine-code changes** — the proof of abstraction.
- `borjan-pm` on the new engine: one full rotation produces the same coverage ledger
  shape, dedups correctly against the existing `seen.jsonl`, and writes to the same
  Notion databases. Existing laptop + cloud schedules keep working after cutover.
- Liveness sweep: a seeded stale entry in New — Unreviewed is detected and retired
  (Notion status flipped + seen.jsonl updated) on the next run.
- CI updated to validate `core/` + all profiles instead of `job-scout-pm/`.
- No feature regressions: unattended mode, state sync (steps 0/8), tokenless Notion
  fallback, tripwire caps, evidence logging all preserved.

**Out of scope for Phase 1:** templates UI/interview, application assistant, FE app,
multi-user concurrency beyond profile-namespaced state, salary tax engines (gross↔net
stays a per-profile ratio, see PROFILE_CONFIG_SPEC.md §5).

### Phase 2 — Template library + setup interview

> **Detailed execution plan (plan of record for the build): [PHASE_2_PLAN.md](PHASE_2_PLAN.md).**
> Brainstormed + expanded 2026-07-15 — the scope below is the original sketch; where PHASE_2_PLAN
> refines it (broad ~12-stream taxonomy, CV-driven templater, per-stream tier rotation, seniority/
> employment-type/effort schema fields, opt-in write-back, deferred scheduling), that document wins.

**Goal:** a new user (or Borjan trying a new stream) goes from nothing to a running,
scheduled profile in one guided session.

Scope:

1. **Role templates** (`templates/`): prepared starting points per stream with
   subvariants — e.g. `software-engineering/` → frontend (react, angular, vue), backend
   (node, python, java, .net), fullstack, mobile; `project-management/` → delivery
   manager, scrum master, technical PM (the current profile becomes this template's
   reference implementation); `design/`, `qa/`, `data/` as the library grows. A template
   contributes: keyword sets (core + expanded), platform category slugs for the catalog's
   URL patterns, default archetypes, scoring rubric hints, and suggested filter defaults.
   Spec: PROFILE_CONFIG_SPEC.md §6.
2. **Setup interview skill** (`skills/job-scout-setup/`): conversational flow in Claude
   Code — pick stream → pick/refine subvariant → set every profile variable with
   presented options (work model: remote/hybrid/on-site; salary: value, currency,
   gross/net, per period; location & eligibility; timezone window; schedule) → provision
   Notion databases (Tracker + Passed/Seen + Runs page created programmatically) → write
   `profiles/<id>/profile.yaml` → validate → offer a first dry run and schedule setup.
3. **Notion provisioning** in core: the database schemas the current system assumes
   become a provisioning script so any new profile gets its own inbox/tracker.

**Acceptance criteria:** starting from a clean checkout with no profile, the interview
produces a valid, scheduled, Notion-provisioned profile for a role that is *not* PM
(target: React engineer), and its first scan run completes with an honest coverage
ledger. The interview never asks for something a template default could prefill —
defaults presented, overridable.

### Phase 3 — Application Companion

> **Detailed execution plan (plan of record for the build): [PHASE_3_PLAN.md](PHASE_3_PLAN.md).**
> Brainstormed 2026-07-17. The scope below is the vision-level account; PHASE_3_PLAN details
> the build and locks the design decisions.

**Goal:** split the "help me apply" half out of the scanner entirely — and grow it into the
companion described in §1. The scanner ends at a Notion shortlist; the companion starts from
it and builds, over time, the user's **voice** and **knowledge base**, then uses them to
draft, interview-prep, debrief, and keep the CV sharp.

**Substrate for Phase 3 (honest):** a **claude.ai Claude Project + the Notion MCP connector**,
storage **option (a)** — a knowing, consented server-side interim per the §1a data principle.
Because the companion lives on claude.ai it cannot read repo files or run `core/*.py`, so
**Notion is the only bridge back to the scanner** (the scanner reads Notion at scan start for
dedup; the companion writes the Tracker + resolves shortlist rows — the write firewall holds).
The whole thing is prototyped conversationally here; the client-side store, real UI, and heavy
integrations are Phase 4/5, but the **data model is designed now to lift into them unchanged**.

**The durable data model (survives every substrate).** Five user-owned entities:
1. **Voice profile** — how the user writes, distilled to a reusable form.
2. **Knowledge base** — real experience, projects, past answers, domain facts; the source of honest answers.
3. **Application log** — every question asked + answer given, per role.
4. **Interview records** — prep notes + how it went + what to fix.
5. **CV state** — current version, age, gaps, and the deltas that update it.

**Staged 3a → 3b → 3c:**

- **3a — Voice + knowledge base + the apply loop (the UAT milestone).** Build the voice
  (from the user's writing, or guided questions if none — with a "does it sound like you"
  meter the *user* judges, not a fake percentage; voice-only docs are shredded right after
  extraction, domain docs kept by default and deletable). Stand up the knowledge base. Run
  the per-role apply loop for real: re-verify the posting → draft in the user's voice →
  capture the Q&A → the honest "I don't know that — you tell me → now it's in your KB"
  growth step → record the application. **This is the chunk tested against real jobs right
  after a scan.**
- **3b — The interview lifecycle.** On a flip to *Interview*: read the JD, predict likely
  questions, surface useful keywords, and map the user's real KB experience onto the role's
  gaps ("haven't done X, but did adjacent Y — here's the honest bridge"). After: a debrief
  the user optionally fills in → honest, constructive feedback → the KB grows. Plus
  **paste-an-email-and-I'll-flip-the-status** (manual now; scoped OAuth auto-ingest is Phase 5).
- **3c — The CV doctor + writing coach.** Assess the CV; flag it if stale (>6 months); guide
  the rewrite with targeted questions; ingest a "delta" document (Borjan will hand over the
  self-review prompt he uses at his job for this — parked in §3x). And co-write blog posts /
  articles in the user's voice, teaching sharper writing and presentation — output that both
  strengthens the candidate and loops back as fresh voice + knowledge material.

**Acceptance:** Borjan's own real loop after a live scan — the companion learns his voice,
drafts a real application in it, records it, and the next scan dedups it — plus a portability
pass proving the package isn't Borjan-shaped (a second profile, e.g. `ani-backend-java`).
No scanner code changes; the Tracker firewall and the data principle hold throughout.

#### Interstitial — Platform Health & Self-Healing (built between 3a and 3b)

**A cross-cutting scanner-ops capability, scheduled for a full build right after 3a acceptance
and before 3b** (Borjan, 2026-07-18: "we should fully build this before continuing with 3b …
this should be here early so it gets clearly buffed as we move in higher phases"). Board rot is
the scanner's slowest inevitable failure mode; the engine should measure its own health
continuously and honestly, and Claude should diagnose + repair on a cadence — before erosion
costs real jobs. Design (Layer-1 `core/health.py` emits trend/severity signals from the existing
`runs.json` + `fetch_evidence.jsonl` telemetry; Layer-2 scheduled Claude "health review" fetches
suspect boards, diagnoses selector/endpoint/slug/bot-wall drift, and repairs the catalog through
the validator; a `health_review_due` counter reuses the recompute mechanism) and the honest-
failure floor it builds on are in the **living seed [HEALTH_MONITORING.md](HEALTH_MONITORING.md)**.
It is **cross-cutting and gets reinforced each phase** — new platforms ship health baselines,
multi-profile health separates platform vs config faults, Phase 4 surfaces a health view + keeps
the time-series, Phase 5 extends monitoring to every new integration/connector. Built via the
standard pipeline (brainstorm → detailed plan → Fable 5 gate → Opus 4.8 build); prime directive
holds (repairs land in the catalog through CI, never ad-hoc scanner edits).

> **🟡 Near-term build LANDED (2026-07-20): Layers 1 + 1.5 + the Layer-2 cue shipped.**
> `core/health.py` (pure `compute_health()` → SELECTOR_SUSPECT / DOWN_STREAK / YIELD_COLLAPSE /
> NEVER_PRODUCED / SYSTEMIC), the per-platform health telemetry it reads (`platform_stats` with
> `raw` + `http_ok` in `runs.json`, so the silent 200-parses-0 selector break is now visible),
> in-scan self-healing (retry-with-backoff + direct→headless escalation, always reported as
> `✚ healed[…]`), the `health_review_due` counter, the `job-scout-run` skill wiring for the
> Layer-2 diagnose-and-repair review, and a `tests/unit_health.py` behavioral suite. Detailed
> build record: **[PHASE_3_HEALTH_PLAN.md](PHASE_3_HEALTH_PLAN.md)**. Layer-2-runtime (in-app
> self-repair on the user's own instance) stays deferred to **Phase 4+** — it needs the embedded
> LLM. Additive: `borjan-pm` resolved config + what the scan resolves/scans are unchanged.

### Phase 4 — The app + client-side store

**Goal:** what Phases 2–3 do conversationally, done through screens — for users who will
never open a terminal — **and** the move off the interim server-side substrate to the
client-side/GDPR store the §1a data principle requires. The app wraps Claude (Agent SDK /
API) rather than replacing it.

Scope (high-level; gets its own spec when Phase 3 ships):

1. Desktop app (Electron/Tauri shell, or local web app) embedding the **Claude Agent SDK /
   API** as the execution backend — the "install and set up" button performs what the setup
   phase did manually: clone/update, check prerequisites, run the setup flow.
2. Screens mirror the setup interview and the companion 1:1 (stream/subvariant picker,
   criteria form from PROFILE_CONFIG_SPEC.md, schedule picker, the voice "sounds-like-you"
   meter, the knowledge-base manager, the apply/interview/CV views) — the skills are the
   single source of logic; the app is a face on them.
3. Run control + shortlist view: trigger/observe scans, render the delta table, surface
   `❓ NEEDS <user>`-class flags.
4. **Storage option (b) — the client-side store.** Migrate the voice profile, knowledge
   base, application log, interview records, and CV state off Notion + the Claude Project
   into a store on the user's side, with Claude called statelessly. Everything deletable;
   nothing mined. This is the phase that makes the §1a principle literally true (Phase 3's
   `secrets.py` seam + ARCHITECTURE §8 storage-adapter boundary are the hooks it lands on).
5. **Prompt-driven wizard over a curated prompt library (Borjan, 2026-07-18).** The app is
   not freeform chat: the user sees a **simple action** — a button, a plain question, "Next",
   "Yes" — and it fires a **curated, battle-tested prompt in the background.** The prompt is
   the unit of interaction; the UI is a thin trigger over it. Those prompts are captured *as
   they are tuned* in **[assistant/GUIDED-FLOW.md](../assistant/GUIDED-FLOW.md)** (current +
   retroactive + future), so Phase 4 wires UI triggers to proven prompts instead of
   re-inventing them. Each entry is a versioned asset; the button label is the Action, the
   background call is the Prompt.
6. **Tappable-UX spec from Ani's first companion run (Borjan, 2026-07-19)** — concrete
   requirements for the item-2 screens, aimed at minimal typing (Gen-Z/Alpha), captured in
   [ANI_FIRST_RUN_FEEDBACK.md §3](ANI_FIRST_RUN_FEEDBACK.md): **sliders** for English-level /
   sentence-complexity / formality (reused at the voice-meter and each tuning step to
   re-generate); **tap-to-edit KB** — confirm/remove/extend a skill, a self-assessed skill-level
   slider the assistant pre-sets, assistant-suggested related skills; a **salary field** (number
   + net/gross + monthly/hourly + $/€) with gross↔net via country estimates (an LLM/API ping —
   already demonstrated in Cowork); **proceed-as-buttons** that write the tracker status directly.
   The companion-side doctrine for these already shipped (assistant/ modules, 2026-07-19); Phase 4
   is where they become actual controls. *The app doesn't exist yet — these build when Phase 4 does,
   which is gated on Phase 3 (companion) shipping.*
7. **Platform settings screen — user-facing health outcomes (Borjan, 2026-07-20).** A screen
   surfacing *this user's* per-board health: scan count, yield over time, live/off status, last-
   produced date. When the health check descopes a board (dead/unrecoverable — a persistent
   DOWN_STREAK/NEVER_PRODUCED that Layer-2 couldn't repair), the board is turned **off for that
   user's instance and the user is notified with the plain-language reason.** The user can **re-enable
   a descoped board anyway** — a board may have yielded nothing simply because there were no openings
   then, not because it's broken — which **restarts that board's health count** (clears the stale
   streak/baseline). Same precedence as Layer-2-runtime: user override supersedes the auto-descope
   for their instance; a later shipped fix that repairs the board expires the override; the descope is
   per-user instance state, never a repo catalog edit. **The health thresholds themselves stay
   system-wide + immutable — the app exposes the outcome (on/off + analytics + re-enable), never the
   knobs.** Detail: [HEALTH_MONITORING.md](HEALTH_MONITORING.md) "In-app platform settings"; the
   engine-side "restart a board's health count" primitive is parked until auto-descope (this item)
   creates something to restart.

**Design constraint imposed now (so Phases 1–3 stay compatible):** every setup and run
operation must be scriptable/headless — no step may exist only as a human-readable
instruction. If a human must click something (e.g. paste a Notion token), the flow exposes
it as a discrete, promptable step. The Phase 2 interview and the Phase 3 companion composer
are built against this from the start — and every tuned prompt is banked in
[assistant/GUIDED-FLOW.md](../assistant/GUIDED-FLOW.md).

### Phase 5 — Platform + integrations

The full product: mobile + laptop + web, **accounts with a one-time setup** (Claude, the
user's store, connectors), **free vs paid tiers** (§1 — free = light/unscheduled; paid =
deeper models, scheduling, weekly-deep passes), and hosted scanning. Plus the heavy
integrations that need the app to exist first:

- **Email status ingest (scoped OAuth).** Read-only, filtered to job-related senders, fully
  opt-in — auto-detect rejections / next-step invites and flip the tracker. (Phase 3 does
  this by paste; Phase 5 automates it.)
- **LinkedIn *export* ingest.** Never scraping (ToS-hostile, fragile, gray) — the user's own
  LinkedIn data export, uploaded and ingested to enrich the CV + knowledge base. GDPR-clean
  because it's the user's own data, user-initiated.

Standing rule carried from Phase 1: nothing in Phases 1–4 may assume single-tenancy in a way
that is expensive to unwind — hence profile-namespaced state, per-profile targets, and the
storage-adapter boundary from the start.

#### Design decision — hosted scanning splits **ingestion** from **matching** (2026-07-19)

**Problem.** Today each profile's scan does its own board fetches. Hosted scanning runs many
profiles per cycle, so the naïve approach — N profiles each fetching independently — is
**O(boards × tenants)** requests and hammers the same hosts N times over, inviting per-host
soft-blocks / rate-limits. Borjan raised this and proposed "one heavy run that carries all
profiles and separates results later."

**Decision.** Adopt the *intent* of that proposal, but as a **layer split, not a monolith** — a
single co-mingled multi-profile run risks cross-tenant leakage (state, scoring, Notion targets,
eventual PII), which the whole architecture is built to prevent. Instead:

- **Ingestion (shared, once per cycle):** a polite, **per-host rate-limited** crawler pulls each
  board's listings once into a **shared postings corpus with a TTL**. One well-behaved crawler per
  domain — the structural fix for soft-blocks (not just throttling).
- **Matching (per-tenant, cheap, trivially parallel):** each profile's run becomes a local pass
  over the corpus — keyword → freshness → dedup → hard-filter → score → shortlist → sync to *its
  own* Notion. No network, no shared-host contention, isolation fully preserved.

Fetch cost drops from **O(boards × tenants)** to **O(boards)**.

**Why the codebase already leans this way (seams to reuse):**
- The listing fetch is already **broad-pull + local keyword filter** (`scan.py` triage:
  fetch board → `_keyword_match` on titles locally) — the expensive network step is largely
  profile-agnostic already.
- `catalog/platforms.yaml` is already the **shared ingest definition**; per-profile `tiers`/
  selection is the tenant-specific part — clean seam.
- `jd_cache/` already exists per profile → promote to a **shared, URL-keyed, TTL'd JD store** so
  two tenants shortlisting the same posting fetch the full JD once (the other per-URL net cost).
- `sweep.py` is already rate-limited — same discipline, applied to ingestion.

**Pieces to add (Phase 5 build):** shared postings corpus (store + TTL); shared URL-keyed JD
cache; per-host crawler pool (token bucket per domain, concurrency cap, backoff); crawl scope =
**union of active tenants' catalog resolutions**; **per-run isolated scratch/temp dirs** — in the
2026-07-19 two-profile parallel test the concurrent subagents shared one scratchpad root and a
scratch log was silently overwritten mid-run (recovered from git-tracked profile state, no data
harm, but a hosted many-runs-in-parallel setup must give each run its own scratch namespace).

**Tradeoffs accepted:** freshness becomes TTL-bounded, not real-time (fine for postings — set
per-board TTL); a shared corpus store to operate (small — public text); tenants keep independent
cadence/keywords/tiers, reading the corpus at their scheduled time instead of hitting the network.

**Status:** decision captured; **build in Phase 5**. Not needed earlier — for the handful of
profiles in Phases 3–4, staggering run starts is sufficient.

### Phase 6 — GTM / launch (marketing & sales prep)

**After the product is built, a dedicated go-to-market phase** (Borjan, 2026-07-18: "phase
latest + 1 for marketing and sales preparation"): positioning + pricing, the sales/marketing
materials (site, deck, one-pagers, demo), advertising + social, and — depending on the chosen
path (§ business notes) — white-label/B2B sales collateral or a marketplace-flip listing package.
The strategy that feeds it is captured early and refreshed with real numbers in
**[BUSINESS_NOTES.md](BUSINESS_NOTES.md)**; the repeatable build/sell method is
**[BUILD_AND_FLIP_PLAYBOOK.md](BUILD_AND_FLIP_PLAYBOOK.md)**. Scope firms up once there's traction
data (MRR, retention, COGS) — every GTM decision hinges on it.

## 3x. Parked ideas & inputs to collect (so nothing is lost)

Captured here the moment they come up, with a phase pointer — even the far-out ones. This is
the "nothing gets summarized-away" list.

| Idea / input | Where it lands | Notes |
|---|---|---|
| **Delta self-review prompt** (Borjan's) | 3c (CV doctor) | Borjan will hand over the skill/prompt he used on his business Claude to generate a "what I did this period" delta. Doubles as a personal performance-review aid → the companion can *generate* it for any user to run at their job. **Ask Borjan for it when 3c is built.** |
| **"Sounds-like-you" voice meter** | 3a | Not a fake percentage — coverage of how the user actually writes (rhythm, go-to phrases, English level, real examples) + a blind draft-and-judge calibration; the user calls when it's good enough. |
| **Voice-only doc shredding** | 3a | If a user has only voice material (no domain docs), the companion asks for anything they've written, tells them plainly "these are deleted the moment I've learned your voice — never stored," extracts, shreds. Domain docs kept by default, deletable. |
| **Unknown-answer → KB growth** | 3a | Honest "I don't have that from what you've given me" → user supplies it → Claude tightens the wording → stored → KB deepens. The KB's main growth engine. |
| **Writing/interview coaching as a goal, not a side effect** | 3c / later | Teaching the user to write and present better is an explicit product value, not just a way to harvest voice material. |
| **Email auto-ingest (scoped OAuth)** | 5 | Read-only, job-sender-filtered, opt-in. Paste-based in 3b. |
| **LinkedIn export ingest** | 5 | User's own data export, never scraping. |
| **Free vs paid tiers / accounts / one-time setup** | 5 | Already shaped by the `run.effort` entitlement axis (ARCHITECTURE §7a) and the D18 secret/account seam. Pricing instinct + open-source-or-not TBD (Borjan: "more in Phase 4"). |
| **In-product ads (web-platform route)** | 6 / tier design | If web-platform/free-tier: an ad surface as a free-user revenue lever — weigh against the premium/privacy positioning ("we don't mine you"). Later-phase decision. See [BUSINESS_NOTES.md](BUSINESS_NOTES.md). |
| **Monetization & valuation strategy** | 6 (GTM) | White-label/B2B as the primary wedge, consumer SaaS as demo, flip-after-traction; valuation = f(revenue, retention, defensibility), not code. Living in [BUSINESS_NOTES.md](BUSINESS_NOTES.md). |
| **Reusable build-and-flip framework** | meta / cross-product | The disciplined method itself, extracted to reuse on the next app (build → flip → repeat; maybe eventually our own flip marketplace — Borjan). Living in [BUILD_AND_FLIP_PLAYBOOK.md](BUILD_AND_FLIP_PLAYBOOK.md). |
| **Structured interview debrief scorecard** (2026-07-18) | 3b | The post-interview debrief is a fixed, comparable template — difficulty, questions asked, honest self-rating, red/green flags about the company, one fix for next time — not freeform notes. Comparable records across interviews let the companion surface patterns ("you consistently struggle with system-design openers"). Decide the template while 3b is being planned; near-zero cost at planning time. |
| **Thank-you + follow-up drafting in the apply loop** (2026-07-18) | 3a/3b | Two in-voice drafting tasks over assets 3a already builds: a thank-you note after an interview, and a polite follow-up when an application has sat silent past a threshold (trigger = date check on the application log). Follow-ups measurably lift response rates and nobody likes writing them — a perfect in-your-voice task. |
| **JD-vs-KB gap checklist at drafting time** (2026-07-18) | 3a | When drafting an application, show honestly what the knowledge base covers, what's adjacent, and what's missing for this JD. Makes each application more honest and feeds the existing "I don't know that → you tell me → KB grows" loop. |
| **`target_seniority.strict` → mechanical drop** (2026-07-19) | 3b / engine follow-up | The one "declared hard but only judgment-enforced" gap left after the 2026-07-19 enforcement pass ([ENFORCEMENT_COVERAGE.md](ENFORCEMENT_COVERAGE.md)). When `strict: true`, a confidently out-of-band posting could Filter Out mechanically (mirror the `employment_mismatch` toggle) using the existing `seniority_detected`. Guard against over-drop: title-scoped only (a "Lead" in a JD body ≠ a lead role). Small, buildable now — parked to keep the enforcement PR focused. |
| ✅ **Duplicate Passed/Seen rows from dedup twins** (2026-07-20, FIXED same day) | engine follow-up — **done** | A posting the user reviewed + `User Declined` (shortlist row) could also carry a mechanically-dropped `Filtered Out` twin row in the Passed/Seen Log — TWO Notion rows, one URL, conflicting reasons (found on Vazco + TT MS). `reconcile` applied both in Notion order (last-wins), so local state could flip to `Filtered Out` even though the user actively declined. **Fixed (both halves):** (a) the sync CREATE path is now idempotent-by-URL (`find_page_by_url` before create — leave a resolved row untouched, refresh a live one in place, only create when no row exists) so new twins can't form; (b) `reconcile_resolutions_from_passed_seen` now ranks reasons per URL (`_REASON_PRIORITY`: user resolution > mechanical) so existing twins resolve deterministically regardless of row order. Proven offline by `sims/twin_row_dedup.py`. |
| **Language barrier stated only in the application form** (2026-07-20) | 3b / judgment doctrine | Addepto's JD is English-only (Fluent English C1/C2) but the apply FORM asked Polish-fluency — a real barrier no scanner reaches (it's behind the apply flow). Not mechanically fixable; documented as a residual gap in [ENFORCEMENT_COVERAGE.md](ENFORCEMENT_COVERAGE.md) + the run skill so judgment surfaces it at apply time. Seeded here so it isn't mistaken for a detector bug later. |
| **Robust language detection beyond the stopword heuristic** (2026-07-19) | 4/5 (engine hardening) | The 2026-07-19 `detect_language()` covers en/pl/de/es/fr/it/nl/pt via function-word frequency + diacritics — good enough for the common EU markets, conservative (unknown = no flag). A fuller/library-grade detector (more languages, mixed-language JDs, higher precision) is a later hardening step; the `search.languages` config + flag/drop contract already generalize to it. |
| **Over-constraint nudge → surface in the app + configurable threshold** (2026-07-19) | 4 | The scan now emits `drop_by_param` + a ≥40% over-constraint `drop_nudge` in the ledger/runs.json ([ENFORCEMENT_COVERAGE.md](ENFORCEMENT_COVERAGE.md) balance rule). Phase 4 should surface this in the run/shortlist view ("filter X dropped 53% — relax?") with a one-tap relax, and make the threshold configurable per profile. CLI/telemetry exists now; the UI + knob are Phase 4. |
| **App-UX from Ani's first run** (2026-07-19) | 4 (scope §6) | Sliders (English-level / sentence-complexity / formality), tap-to-edit KB, salary net/gross calculator, proceed-as-buttons. Detail in [ANI_FIRST_RUN_FEEDBACK.md §3](ANI_FIRST_RUN_FEEDBACK.md); companion-side doctrine already shipped (assistant/ modules 2026-07-19); UI is Phase 4. |
| **Growth tracking — "Fitbit for the job search"** (2026-07-18) | 4 (app views) | Longitudinal charts from data the five entities already accumulate: applications/week, response rate, interview conversion, KB growth, voice maturity. Job hunting is demoralizing; visible progress is honest encouragement and a churn-fighter. No MVP work — the data accrues on its own until the app renders it. |
| **"Always-low, never-collapsed" health signal** (2026-07-20) | health-build follow-up | `YIELD_COLLAPSE`/`SELECTOR_SUSPECT` both need a known-good trailing baseline to fall from — a board that's undercounted since before any good baseline existed (always "1," always "4," never higher) is invisible to every current signal. Found live twice in one manual sweep ([HEALTH_LOG.md](../docs/HEALTH_LOG.md) "Low-yield sweep"): Himalayas' pagination silently capped at 20/page while the code assumed 100 (4.5x undercount), Dynamite Jobs rendered postings as `<h2 href>` instead of `<a>` (16x undercount) — both `http_ok: true`, both looked perfectly healthy. Candidate shape: flag a Tier 1/2 board whose yield has *never once* exceeded some small absolute floor across its whole history, independent of trend. Not built — the right floor value needs real per-platform volume data this build doesn't have yet. Detail in [HEALTH_MONITORING.md](HEALTH_MONITORING.md) "Known blind spot." |
| **Full architecture-quality review, 8 uncovered dimensions** (2026-07-21) | scheduled per CLAUDE.md DoD #5 | The 2026-07-21 audit was real but scoped to the bug it was triggered by ("does the code do what it claims") — Borjan asked directly whether it also covered SOLID/design-patterns/best-practices broadly and the honest answer was no. Scoped the full follow-up in **[ARCHITECTURE_QUALITY_SCOPE.md](ARCHITECTURE_QUALITY_SCOPE.md)**: the SOLID letters beyond Single Responsibility, deliberate design-pattern-fit evaluation, module boundary/file-size appropriateness (`scan.py`/`fetch_boards.py` are the largest), whole-system coupling/cohesion, extensibility stress-testing (not assumed), naming/consistency conventions, performance/algorithmic complexity, testing-architecture strategy, and security posture beyond ad-hoc checks. `CLAUDE.md` gained DoD #5 (a periodic, judgment-gated — not automatic — cadence for this: natural phase boundaries or ~10 core/-touching sessions since the last pass). Not run yet — scoped now, intended to run as its own dedicated session per Borjan's request. |
| **Board-fetcher DRY: shared per-board fetch/down/note helper** (2026-07-21) | engine follow-up | Full-`core/` architecture audit (CLAUDE.md DoD #4, first run): `fetch_greenhouse`/`fetch_lever`/`fetch_workable`/`fetch_pinpoint` each hand-duplicate the identical "loop boards → try/except → build down-list → `_down` vs `_ok` threshold" pattern. Not cosmetic — the duplication is exactly how `fetch_workable` silently diverged (called `requests.post()` directly instead of the shared `_get`/`_post` retry wrapper, so a single transient error dropped the whole board with no retry; fixed same session by extracting `_request`/`_post`). A shared `_fetch_per_board(boards, fetch_one)` helper would make that class of drift structurally impossible instead of relying on each fetcher staying hand-in-sync. Buildable now; not done this session to keep the audit-fix PR focused on bugs, not refactors. |
| **Notion REST plumbing DRY: shared client between notion_sync.py and provision_notion.py** (2026-07-21) | engine follow-up | Same audit: `_headers()`/`_req()` (backoff on 429/5xx) is copy-pasted near-verbatim between `core/notion_sync.py` and `core/provision_notion.py`, kept in sync only by an unenforced comment ("MUST match notion_sync.py"). A shared `core/notion_client.py` (or similar) would remove the drift risk. Buildable now; deferred to keep this session's fix scope to genuine bugs. |
| **state_sync.py multi-round rebase-conflict handling** (2026-07-21) | engine follow-up | Same audit: `_resolve_conflicts()` handles exactly one round of rebase conflicts; a multi-commit divergence producing a SECOND conflict stop (possibly on a state file the first pass never saw) gets the generic "non-state files" abort message even when it's really an unhandled state-file conflict, discarding the first pass's merge work. The documented "auto-merges if another run pushed in between" claim only holds for single-round races. Real but rare (needs a multi-commit divergence, not just a simple race) and risky to fix quickly given it's git-rebase-flow logic — deferred rather than rushed. |
| **Write-back staging: real name/employer detection** (2026-07-21) | engine follow-up | `core/writeback.py`'s `_is_generic_term` PII guard only mechanically blocks email/URL-shaped values — it cannot distinguish a person's name ("Sarah Connor") from a legitimate archetype ("Technical PM"), since both are title-cased 1-3 word phrases in this codebase's own real data. No safe regex fix exists (tightening it would also reject real archetypes). The actual "never names" guarantee today is a PROCESS control (the setup skill only stages CV-obvious tech terms; a human curator reviews every entry before it can reach a template, D6). Docstrings corrected to stop overclaiming what's mechanically enforced (2026-07-21). A real fix needs name-detection (a small NER pass or a curated denylist), not a stricter regex — buildable later, not this session. |
| **dedup.py `norm_url` query-string stripping — Deel `ashby_jid` risk (known, already reviewed)** (2026-07-21, cross-checked against 2026-07-20) | not actioned — documented only | Full audit flagged `norm_url()`'s unconditional `[?#].*$` strip as a theoretical risk for platforms that encode job identity ONLY in the query string — confirmed real for Deel specifically (`careers/position/?ashby_jid=...`, `core/fetch_boards.py` :458). But the 2026-07-20 dedup-key-fix session already examined this exact behavior (2 Deel URL-key changes, both reviewed, "no new merge") and it was already query-collapsing under the OLD code too — not a regression, not new information. Left untouched rather than re-litigating a recent deliberate call without asking first; noting here so it isn't rediscovered as a fresh bug later. |
| **Notion sync/reconcile hardening bundle** (2026-07-21, full architecture-quality pass) | engine follow-up — DEFERRED (live daily-critical path) | Seven findings on the two most production-critical Notion modules (`notion_sync.py`/`provision_notion.py`), deliberately NOT rushed into the review PR per the scope doc's "Notion sync = defer-trigger." (a) **Reason/property vocabulary has no single source of truth** — the 7 reason strings live as `provision_notion.REASON_OPTIONS` + `notion_sync.VALID_REASONS` + prose in `compose_assistant.py` + split across `_RESOLVED_LOCAL_STATUS`/`_REASON_PRIORITY`, and Notion property NAMES (`"Reason Passed"`, `"Job URL"`, …) are stringly-typed literals repeated across both modules; a rename/added reason drifts silently and writes get coerced to `Filtered Out`. Fix: a shared `core/notion_vocab.py` (reasons + property names), `VALID_REASONS = set(REASONS)`. (b) **`typed_create_page` verifies strictly less than `_patch_verified`** — the CREATE path asserts only Role-title + parent, not the select/rich_text properties, so a silently-dropped `Reason Passed`/`Platform` select on create is marked synced (the July `_patch_verified` generalization was folded into the 3 PATCH paths but not create). Fix: run the same per-property comparison after the title/parent check (additive — can only turn a silent drop into a loud failure). (c) **Redundant re-GET**: `find_page_by_url` returns only the id, forcing `_current_reason` to GET the same page again — one wasted round-trip on every sweep/applied-flip/idempotent-create; have it return `(id, reason)`. (d) **`reconcile_applied_from_tracker` is O(T) PS-queries-per-tracker-row** (`flip_passed_seen_to_applied` per URL) while its sibling paginates the Passed/Seen log once — share one `{norm_url: (id, reason)}` snapshot. (e) `append_digest`'s status guard is per-element AFTER `s.json()` (`notion_sync.py:313`) — check `status==200` before `.json()`. (f) dead code: `notion_sync._unsynced_records` reimplements the never-called `dedup.unsynced()` — delete + call the canonical one. Each needs a sim (the pagination one especially — see the sim-fidelity item). Tracker firewall verified intact throughout the pass; the vocab refactor must not make a Tracker `ds_id` reachable from a scan builder. |
| **`scan.py` decomposition — extract detectors + phase helpers** (2026-07-21, architecture pass §3) | engine follow-up — DEFERRED (production orchestrator) | Two medium refactors on the daily-run path, seeded not rushed. (a) **`run_scan` is a ~475-line God function** owning ~13 sequential stages (reconcile → gap-compute → fetch → triage → JD reads → liveness → salary → annotate → opt-in-drop → sweep → cache → JSON → ledger) — the pure detectors are already extracted+unit-tested, but the pipeline STAGES aren't testable in isolation. Extract `_triage`/`_read_jds`/`_liveness`/`_annotate`/`_emit_and_log`, each taking/returning the candidate list; `run_scan` becomes the sequence (behavior-preserving, output byte-identical). (b) **The pure detectors + their ~13 module constants (`scan.py:94-316`, ~220 lines) → `core/detectors.py`** — this is the one split that genuinely reduces coupling (the dependency is strictly `run_scan → detectors`, never reverse) rather than just relocating lines; `tests/unit_detectors.py`'s import updates with it. Do (b) then (a). |
| **Candidate record schema + sweep uses source_url** (2026-07-21, architecture pass §4) | engine follow-up | (a) **The enriched candidate emitted to `last_run_candidates.json` — the scanner↔skill (and Phase-4 FE) contract — has NO declared schema**: ~15 keys (`keyword_matched`, `flags`, `source_url`, `jd_status`, `salary_assessment`, `seniority_detected`, `company_prior`, …) accrete imperatively across `run_scan`; the skill/FE must reverse-engineer them from control flow. Seed a documented `TypedDict`/`schema/candidate.schema.*` (the base 8-field shape is already centralized in `fetch_boards._cand`; this is the enriched superset). Natural to do alongside Phase 4's FE contract. (b) **`source_url` (the declared "liveness authority", `scan.py:562-583`) is never persisted to the seen record**, so `sweep.run_sweep` openly re-checks the plain Job URL instead (`sweep.py:93-95`) — for a mirror/aggregator row where `source_url != url` the sweep verifies liveness against a *less* authoritative URL than the original scan did. Documented compromise today, not a hidden bug; the real fix is adding `source_url` to `dedup.make_seen_record`'s shape (now that the constructor exists) and having the sweep prefer `rec.get("source_url") or rec["url"]`. |
| **Test/sim fidelity hardening** (2026-07-21, architecture pass §8) | test-infra follow-up | Structural gaps the pass found (the two highest-value pure-logic gaps — `salary.py` and `state_sync` mergers — were CLOSED in the review PR; these remain). (a) **Sims structurally can't catch a Notion pagination bug**: all three fake-Notion fixtures return a single page (`has_more: False`), so the `start_cursor`/`next_cursor` advance in both reconcile loops (`notion_sync.py:507-522`, `597-614`) is executed by no test — a regression that drops page-2 rows (silent under-reconcile) or loops forever passes every sim. Add a two-page fake fixture. (b) **No fake models Notion's rich_text `text.content`→`plain_text` round-trip** (fakes `.update()` the sent dict verbatim), so a *successful* rich_text verification would falsely fail — latent, masked only because the one rich_text sim case tests the drop, not a green write; it'll bite the moment someone adds a green rich_text assertion. (c) `reconcile_new_tracker_box`'s fake GET hard-codes returning only `Reason Passed` — harden it to echo stored properties generically (as `twin_row_dedup` already does) so it can't rot if the flip stamps a second property. (d) `compose_assistant.pii_hits`/`_config_hash` are pure but untested — a PII-detection guardrail with no characterization test. |
| **`HARVEST_SPECS` → catalog (close the SSR "config not code" gap)** (2026-07-21, architecture pass §5) | engine follow-up | Extensibility stress-test verdict: "config not code" holds for values/categories/tiers/regex-shaped filters and for choosing among existing fetch strategies, but quietly breaks for a *new kind of thing*. The highest-leverage fix: `fetch_boards.HARVEST_SPECS` (the per-board HTML link-harvest regex/`base`/`company_idx`/`min_hyphens`, `fetch_boards.py:513-536`) lives in ENGINE code, so even a plain new SSR board needs a code edit — moving it into `catalog/platforms.yaml` (which the catalog header already implies is where "fetch strategy" lives) would make a new static-HTML board pure config. Two other extensibility limits are inherent and acceptable (documented, not seeded as bugs): a new fetch *mechanism* (GraphQL-only / multi-step auth) is necessarily a new `HANDLERS` function, and a new non-regex filter *TYPE* (numeric/aggregate, like salary or closed-location) is necessarily a new typed structure in `_compile_hard_filters` + a new apply block in `scan.hard_filter` — the filter *types* are a closed engine set, only their values/patterns are config. |
| **Minor perf + consistency notes** (2026-07-21, architecture pass §6/§7) | engine follow-up — low priority | Small, individually-marginal items surfaced by the pass, bundled so none is lost. **Perf (all cache-mitigated, low urgency):** `detect_seniority` re-sorts the lexicon + rebuilds `\bterm\b` patterns per candidate (`scan.py:266`); the closed-location detector builds `\b{country}\b` per country per candidate (`scan.py:340`); `check_links._markers_for` recomputes each platform host per URL (`check_links.py:125-132`) — each wants its static data hoisted/precompiled once (mirrors the `stated_language_requirement` precompile done in the review PR). **Consistency:** the salary range separator `[-–—to]+` (`salary.py:22`) is a char-class that also matches a lone `t`/`o` — latent only (a spurious match still needs a trailing number), worth `(?:-|–|—|to)`; the desktop `UA` string is duplicated verbatim in `check_links.py`+`linkedin_tripwire.py`; `check_links`'s `deferred` dict is mutated from worker threads unlocked (GIL-safe by distinct-URL keys, but every other shared dict there is locked — worth a one-line rationale comment); `dedup.role_family`/`company_index` are scan-serving query helpers parked in `dedup` (defensible next to `norm_company`, note only). |
| **Agency mode — operator console over multi-profile** (2026-07-18) | 5/6 | The platform is already multi-profile with namespaced state; a career-services operator (outplacement firm, bootcamp, coaching agency) running 20 candidates is architecturally just 20 profiles. Add an operator console (cross-profile run health, per-candidate status, pipeline view) + per-candidate reporting → turns the white-label thesis from "license the engine" into a concrete product for the buyers with the best economics (annual contracts, low churn). Name it in the Phase 5 scope when Phase 5 is planned. |
| **Self-healing after scan** | health build (Layer 1.5/2); **runtime → Phase 4+** | Layer-1.5 in-scan mechanical recovery (retry/backoff, direct→headless, endpoint failover) + Layer-2 dev-side catalog repair. **Plus Borjan's Layer-2-runtime (Phase 4+):** the app heals ITSELF at run time via an in-app Claude call — fetch-layer-only, validate-before-adopt, per-user override, reported, bounded COGS, opt-in telemetry back, vetted-release-supersedes — so users get improved results without waiting for an app update. Design in [HEALTH_MONITORING.md](HEALTH_MONITORING.md). |
| **AI-provider-agnostic / BYO-key** | seam now (ARCH §7b); tiers Phase 4/5 | Provider-adapter seam so users can bring their own LLM key (COGS→user, charge for software — the pricing lever vs the wrapper/COGS problem). Claude stays the tuned default; not a defensibility play. [ARCHITECTURE §7b](ARCHITECTURE.md) + [BUSINESS_NOTES](BUSINESS_NOTES.md). |
| **Geo-fit is per-profile metadata, NOT a platform rejection** (2026-07-20, Borjan) | engine follow-up (platform-level resolver); back-fill catalog geo_skew | **Decision that reframes every "US-dominated → reject" call.** A board's geographic/eligibility skew is a property to *resolve per profile*, never a reason to drop the board globally. Same board, opposite verdict: a `us`-skewed board is real signal for a US-based / US-targeting / relocation-eligible profile and noise for an EU-only-by-choice profile; symmetric for `eu` boards vs a US-only profile. Fit is resolved against the profile's **target markets** (`search.regions_acceptable`) + **eligibility** (`candidate.eligibility`), which can differ from physical location (Skopje→EU/Worldwide; India→EU/US-via-relocation; US-based→US). Some boards' fit runs on a *non-region* axis entirely (Relocate.me = visa-sponsorship/relocation → `candidate.eligibility.needs_visa_sponsorship`). **Already half-built:** the ROW-level filters do this today — `us_only` is skipped for a US candidate, `closed_location_list` keys off `candidate.location_match_terms` (profile_loader.py:18). **What's missing (the seed):** a PLATFORM-level scan/skip resolver that reads a board's `geo_skew` against the profile's markets+eligibility, so an EU-only profile doesn't waste a fetch on a 100%-US board while a US/relocation profile does scan it. `geo_skew: worldwide\|eu\|us` metadata added to `catalog/platforms.yaml` (documented in its header); carried on the 3 boards added this session; **back-filling the existing 28 entries + building the resolver is the follow-up.** Corollary: the legacy `rejected_platforms` US-dominated entries (Wellfound, Built In, Remote.co) should be *revisited* under this logic during Borjan's next platform-by-platform pass — most are geo_skew candidates, not true rejects. |
| **Board-coverage audit vs. a 20-board reference list** (2026-07-20) | 3 added to catalog now (`active:false`+`unverified`); smoke tests + Key Values decision are Phase 2 §3.2 | Borjan asked whether 4 boards were covered; **decision (per the geo-fit reframe above): add 3, hold 1.** **Y Combinator "Work at a Startup"** (id 29, `geo_skew: worldwide`) — anonymous static fetch, no login wall, role+location URL axes, genuine EU/remote *and* US PM signal live (Cogram/Berlin, Alguna/EMEA alongside SF/NY); serves both the project-management and software-engineering streams. **Dice** (id 30, `geo_skew: us`) — **added, not rejected** (supersedes the initial "reject like Built In" read): a live "Europe" search returned overwhelmingly US staffing postings, i.e. genuinely US-skewed *inventory* — which is exactly what `geo_skew: us` + the per-profile resolver is for (scan for US/relocation profiles, skip for borjan-pm). **Relocate.me** (id 31, `geo_skew: worldwide`, fetch `headless`) — **added for Borjan to manually verify + possibly fix next session**; distinguishing axis is visa-sponsorship/relocation (→ `candidate.eligibility`), not region; no clean PM bucket (broad "Manager" catch-all, title filter narrows), JS-rendered, curated "Global Move" feed paywalled ($15/mo) but the free listing is enumerable. **Key Values** — the one genuine reject: **not a postings aggregator at all** (own tagline "find engineering teams that share your values" — per-company culture pages, no PM/SM/DM category, no listing-churn feed); same shape as Contra's "not a job board" rejection. This is a *structure* reject, not a *geo* one, so the reframe above doesn't change it. All 3 adds ship `active:false`+`status:unverified` (out of tier-coverage until a live smoke test flips them). Open Phase 2 question still standing: whether `catalog/platforms.yaml` grows its own `rejected_platforms`/`geo_skew`-aware section as source-of-truth moves off the legacy `job-scout-pm/config.yaml`. |
| **New-stream/new-subvariant coverage discovery — can it be autoheal'd?** (2026-07-21, Borjan) | Phase 4+ design question; not buildable safely today | Borjan asked directly: when a genuinely new user arrives with a new stream/role/subvariant, does the platform catalog "just work," and can any of the gap-filling be autoheal'd — both for THIS repo and adapting itself across other platforms? Honest current-state answer, checked against the real code (not assumed): a brand-new STREAM (one no platform's `catalog/platforms.yaml` `categories` dict has ever mapped) resolves every category-gated platform to `active: false` ("does not serve this stream") — honestly reported in the coverage ledger (never silent), but ZERO platforms auto-activate and nothing auto-discovers a URL for it. A new SUBVARIANT of an EXISTING stream inherits that stream's platforms automatically (`categories` is keyed by stream, not subvariant) with no extension needed — confirmed this session (Remote Rocketship: no `platform_slugs` override exists anywhere for it). **Why the gap-filling itself isn't safely automatable today, demonstrated live this same session**: filling a stream gap requires (a) finding a plausible category URL/slug (sitemap-crawling or guessing), then (b) semantically judging whether the content returned is ACTUALLY on-topic — a script can't do (b). Remote Rocketship's bug was a URL that returned HTTP 200 with real-looking postings that were completely off-category; Arc.dev's `sales`/`hr`/`technical-support`/`blog-writing` slug guesses (same session) silently fell back to an unrelated generic feed rather than erroring — a naive automated "try a slug, keep it if it returns content" heal would have shipped WRONG data in both cases, exactly the failure mode the "scripts flag, Claude decides" design principle exists to prevent. This is a genuinely different problem from the BUILT Layer-1.5 self-healing (retry/backoff, direct→headless escalation — recovers a FETCH failure on an already-known-correct URL) and the SPEC'd Layer-2-runtime (repairs a CONFIRMED degradation on a board already in the catalog) in [HEALTH_MONITORING.md](HEALTH_MONITORING.md) — neither covers *discovering* coverage for a stream that's never existed in the catalog before. **What COULD be safely mechanized** (a flag, not a fix — matching the already-filed "always-low, never-collapsed" signal idea above): at profile-creation time, print how many catalog platforms actually resolve active for the new stream vs. a typical existing stream, as a nudge to run a manual (or Claude-assisted) coverage pass — not to auto-guess URLs. Not built — same reasoning as the always-low signal above, needs real per-stream expected-coverage baselines this build doesn't have yet. **Process fix already made this session** (not deferred): `docs/HEALTH_LOG.md`'s "How a review works" step 5 now says explicitly to run the whole generalization checklist (stream/region/fetch/subvariant completeness) unprompted the moment ANY platform fix ships, not only when asked — this was already written as a standing rule before today and still needed Borjan's prompt to trigger it on Remote Rocketship, which is the actual gap: application discipline, not a missing rule. |
| **Real-CV-driven self-heal — local AND global** (2026-07-21, Borjan) | Phase 4+ (needs real multi-user CV intake — doesn't exist yet); extends the existing Layer-2-runtime design (row above) | Borjan: "when we start getting CVs in from actual people, we need to use them to self-heal the app locally on the device but also globally in the repo." Not buildable now — no CV-intake pipeline, no multi-user surface exists yet — but it's a concrete NEW validation signal for the self-healing design already scoped in [HEALTH_MONITORING.md](HEALTH_MONITORING.md): today Layer-2-runtime's "confirmed degradation" trigger is fetch-health telemetry only (source_down, yield collapse). Real CVs flowing through real users' scans add a second, higher-signal trigger — e.g. a KB/CV that should plausibly match a stream/board producing suspiciously few or zero matches for THAT user is itself evidence of a coverage gap, independent of whether `health.py`'s mechanical signals happen to fire. **Local**: a per-user/per-device repair (the Layer-2-runtime per-user override already designed — fetch-layer-only, validate-before-adopt, reported) — the user's own instance improves immediately from their own data, no waiting for a release. **Global**: the existing "opt-in telemetry loop, vetted fixes fold into the shipped catalog, a newer shipped fix supersedes/expires the override" precedence (already designed, same doc) is exactly the mechanism that turns one user's local repair into a benefit for everyone once reviewed — CVs would just be a richer input to what gets proposed for that fold-in. No new design needed beyond what's already scoped; this is confirmation the existing design has a concrete, valuable trigger source once real users exist. Revisit when Phase 4's CV/multi-user intake is being built. |

## 4. Execution discipline (multi-session builds)

The build will span many sessions and two lanes (laptop + cloud). Same rules that got
v3.x shipped:

- **[PROGRESS.md](PROGRESS.md) is the session-resume contract.** Read first on every
  session start; never redo ✅ steps; update it in the same session as the work; every
  session ends with a state push. Per-phase build checklists live there, not here.
- **GitHub flow**: feature branches per phase (`claude/job-scout-<phase>-…`), PRs to
  `main`, CI green before merge. CI grows with the repo (Phase 1 swaps the audit target
  from `job-scout-pm/` to `core/` + profiles).
- **The live scan is production.** Until Phase 1 cutover, nothing may break
  `job-scout-pm/` — the daily schedules run against `main`. Cutover is a deliberate,
  reversible switch (schedules re-pointed, old path archived, not deleted).
- **Lessons become rules**: generic scan-logic lessons go to the engine skill/docs;
  profile-specific ones to the profile; environment frictions to the changelog. Same
  friction-logging culture as v2.x/v3.x.
- **Every phase ends with human-readable documentation** (standing rule, adopted at the
  close of Phase 2): the final step of every phase execution/build plan is updating
  [PLATFORM_GUIDE.md](PLATFORM_GUIDE.md) — the plain-language account of what was built,
  why, how it works, and what using it looks like — plus any affected reference docs.
  A phase is not done until the guide reflects it; seed this step into every future
  phase checklist (Phase 3+) when the checklist is created.
- **Bank every tuned prompt in the guided-flow library** (standing rule, adopted 2026-07-18):
  whenever a user-facing step's prompt is fine-tuned through dogfooding/QA, capture it in
  [assistant/GUIDED-FLOW.md](../assistant/GUIDED-FLOW.md) as a `{simple action → background
  prompt}` entry — current, retroactive, and future. The prompts are the app's golden path;
  Phase 4 wires UI triggers to them (a button label is the Action, the background call is the
  Prompt) instead of re-inventing them. Nothing evaporates in chat.

## 5. Open questions

**Phase 1–3 questions — settled.** The original five (profile identity, salary
normalization, second template, assistant data boundary, FE shell) are resolved: profiles
live in-repo under `profiles/`; per-profile gross↔net ratio with country presets, no tax
engine; backend-java was the first dogfooded non-PM stream (Ani); the companion data
boundary is strict — the companion reaches the scanner only via Notion, CV/PII never enters
the repo (§1a). FE shell stays open until Phase 4.

**Parked for Phase 4 (Borjan: "more in Phase 4").** The product-layer questions are
deliberately deferred until the app phase, when they actually bite:

1. **Client-side store** — the concrete storage choice for option (b) (local DB / file
   vault / encrypted bundle) and the migration path off Notion + Claude Project.
2. **Pricing + tiers** — where the free/paid line sits, what each tier unlocks (models,
   scheduling, weekly-deep), and the billing mechanism.
3. **Distribution** — open-source or not; desktop-first vs web-first; self-host vs hosted.
4. **Accounts + connectors** — the one-time setup UX for Claude API + the user's store +
   connectors, and multi-tenant boundaries.

Borjan will bring more vision into Phase 4; capture it in §1/§3x when it lands.
