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
| **Growth tracking — "Fitbit for the job search"** (2026-07-18) | 4 (app views) | Longitudinal charts from data the five entities already accumulate: applications/week, response rate, interview conversion, KB growth, voice maturity. Job hunting is demoralizing; visible progress is honest encouragement and a churn-fighter. No MVP work — the data accrues on its own until the app renders it. |
| **Agency mode — operator console over multi-profile** (2026-07-18) | 5/6 | The platform is already multi-profile with namespaced state; a career-services operator (outplacement firm, bootcamp, coaching agency) running 20 candidates is architecturally just 20 profiles. Add an operator console (cross-profile run health, per-candidate status, pipeline view) + per-candidate reporting → turns the white-label thesis from "license the engine" into a concrete product for the buyers with the best economics (annual contracts, low churn). Name it in the Phase 5 scope when Phase 5 is planned. |

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
