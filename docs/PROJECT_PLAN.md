# Job Scout Platform — Project Plan

> Master plan for evolving `job-scout-pm` (a single-person, single-role skill) into a
> profile-agnostic job-search platform. This document is the entry point: it defines the
> vision, the phase boundaries, what is explicitly out of scope per phase, and the
> execution discipline for multi-session builds. Architecture details live in
> [ARCHITECTURE.md](ARCHITECTURE.md); the profile/template configuration contract lives in
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md); live build state lives in
> [PROGRESS.md](PROGRESS.md).

Status: **draft for Borjan's review** · Created: 2026-07-13

---

## 1. Vision (end goal, NOT the next phase)

A job-searching platform usable on laptop and mobile: a person installs it, picks what
kind of job they are looking for, tunes the search criteria on a screen, and the platform
scans job boards on a schedule, keeps a clean live shortlist, and then coaches them
through applying to each role — with Claude doing the scanning judgment and the
application coaching.

Everything below is staged so each phase ships something usable on its own, and nothing
in an early phase has to be thrown away later.

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
| **0** | This documentation set | — | this PR |
| **1** | **Core engine extraction**: profile-agnostic `core/`, platform catalog, profile config schema, `borjan-pm` as the first profile, **shortlist liveness sweep**, parity cutover | Claude Code (laptop + cloud), unchanged lanes | next |
| **2** | **Template library + setup interview**: role templates with subvariants, a conversational setup skill that provisions a new profile end-to-end (config + Notion databases + schedule) | Claude Code | after 1 |
| **3** | **Application Assistant**: a Claude Projects package that walks the user through the shortlist role-by-role, drafts answers from user data, and tracks applications | claude.ai Project (+ Notion MCP) | after 1 (parallel to 2 possible) |
| **4** | **Setup/companion FE app**: a desktop app that drives Claude Code (Agent SDK) in the background — install, options screens mirroring the setup interview, run/schedule control, shortlist view | Desktop (laptop) | after 2 |
| **5** | Mobile + laptop platform (the end goal) | TBD | out of scope — vision only |

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

### Phase 3 — Application Assistant (Claude Projects)

**Goal:** split the "help me apply" half out of the scanner entirely. The scanner ends at
a Notion shortlist; the assistant starts from it.

Scope:

1. **`assistant/` package**: Claude Project instructions (evolving
   `references/pitching.md` into a standalone, profile-parameterized package) + a setup
   guide: create a claude.ai Project, add the instructions, upload user data (CV, cover
   letter bank, articles, past answers), connect Notion MCP.
2. **Workflow**: user opens the Project → assistant reads the profile's
   `New — Unreviewed` view → walks the list one-by-one → user opens the posting →
   assistant re-verifies key facts, helps decide (apply/pass), drafts answers and
   application materials in the user's voice from Project data → on "applied", writes the
   Tracker row and flips the Passed/Seen status; on "pass", records the real reason.
3. **Shared Notion contract** (ARCHITECTURE.md §5): statuses, fields, and write-ownership
   rules formalized so scanner and assistant never fight over rows. The invariant
   survives: **the scanner never writes the Tracker; the assistant is the only
   application-recording path** (plus the existing "I applied" chat flow).

**Acceptance criteria:** a full loop on real data — scan shortlists a role → assistant
session reviews it, drafts the application answers, records the application → next scan
run dedups it as Tracker-applied. No scanner code involved in the assistant session.

### Phase 4 — Setup/companion FE app

**Goal:** what Phase 2 does conversationally, done through screens — for users who will
never open a terminal. The app wraps Claude Code rather than replacing it.

Scope (high-level; gets its own spec when Phase 2 ships):

1. Desktop app (Electron/Tauri shell, or local web app) embedding the **Claude Agent
   SDK** as the execution backend — the app's "install and set up" button performs what
   this repo's setup phase did manually: clone/update the repo, check prerequisites,
   run the setup flow.
2. Screens mirror the setup interview 1:1 (stream picker with template suggestions,
   criteria form with the option sets from PROFILE_CONFIG_SPEC.md, schedule picker) —
   the interview skill is the single source of setup logic; the app is a face on it.
3. Run control + shortlist view: trigger/observe scans, render the delta table, deep-link
   into Notion, surface `❓ NEEDS BORJAN`-class flags.

**Design constraint imposed now (so Phases 1–3 stay compatible):** every setup and run
operation must be scriptable/headless — no step may exist only as a human-readable
instruction. If a human must click something (e.g. paste a Notion token), the flow must
expose it as a discrete, promptable step. Phase 2's interview is built against this
constraint from the start.

### Phase 5 — Platform (vision only)

Mobile + laptop product, accounts, hosted scanning. Not planned here beyond one rule:
nothing in Phases 1–4 may assume single-tenancy in a way that is expensive to unwind —
hence profile-namespaced state and per-profile Notion targets from Phase 1.

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

## 5. Open questions for Borjan

1. **Profile identity**: Phase 1 keeps profiles as directories in this repo. OK, or
   should user profiles live outside the repo (separate private repo / local-only) from
   the start? (Default adopted: in-repo under `profiles/`, since state sync already
   rides git and the repo is private.)
2. **Salary normalization**: gross↔net conversion is country-dependent. Default adopted:
   per-profile ratio field with a documented default, no tax engine (§5 of the config
   spec). Good enough?
3. **Second template to build first** in Phase 2: React/frontend engineer (as in your
   example), or another stream you want to dogfood?
4. **Assistant data boundary**: the Claude Project holds CV/answers; the repo holds
   config/state. Any user data you'd want mirrored into the repo (encrypted or not), or
   strict separation (default adopted: strict — scans never read Project files, the
   assistant never reads repo state except via Notion)?
5. **FE app shell** preference for Phase 4 (Electron vs Tauri vs local web) — can stay
   open until Phase 2 ships.
