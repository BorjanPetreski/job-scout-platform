# Job Scout Platform — The Guide

> The human-readable documentation for this project: what it is, why it exists, what has
> been built so far, how it works, how we built it, and what using it actually looks
> like. If you are new to the repo — or coming back after months away — **start here.**
> The planning/engineering companions are [PROJECT_PLAN.md](PROJECT_PLAN.md) (vision +
> phases), [ARCHITECTURE.md](ARCHITECTURE.md) (technical structure),
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md) (configuration contract), and
> [PROGRESS.md](PROGRESS.md) (the live build log).

Status: current as of **end of Phase 2** · Written: 2026-07-17

---

## 1. What this is

The Job Scout Platform is a job-search machine driven by Claude. You tell it once what
kind of job you want — role, seniority, remote or not, salary floor, deal-breakers — and
it scans dozens of job boards on a schedule, filters out everything that doesn't fit,
verifies that the postings it likes are actually still live, scores the survivors with
real judgment (reading the full job description, not just the title), and keeps a clean
shortlist waiting for you in Notion. You review the shortlist when you have time; the
platform never applies to anything on your behalf.

It started as a personal tool for one person (Borjan, searching for Senior PM / Delivery
Manager roles) and has been rebuilt into a **profile-agnostic platform**: one engine, any
number of people, any role — a React engineer, a Java backend developer, a product
designer, a recruiter — each with their own profile, their own filters, and their own
Notion workspace.

## 2. Why it exists — the purpose

Job searching has a grind problem. The actual work is:

- checking the same 20+ job boards every day, because good remote roles get buried fast;
- reading past the title, because titles lie ("Scrum Master" that is really a BA role,
  "remote" that is really hybrid-in-Warsaw);
- filtering the same deal-breakers over and over (salary below your floor, EU-citizens-only
  clauses, tool lock-in you don't want, grind-culture red flags);
- discovering that the great posting you saved on Tuesday was already dead by Friday;
- and remembering what you already saw, so you don't re-read the same 90 stale postings
  every morning.

All of that is exactly the kind of work an LLM with scripts around it does well — and the
part that matters (deciding, applying, interviewing) stays with the human. The purpose of
the platform is to **reduce a daily hour of board-crawling to a five-minute review of a
trustworthy shortlist**, for anyone, in any role, without ever pretending to be the
candidate: no auto-apply, no logged-in scraping, no fabricated experience in application
materials. Ever.

## 3. The goal

The end-state vision (Phase 5) is a real product: install it on a laptop or phone, pick
the kind of job you're looking for, tune the criteria on a screen, and the platform scans
on a schedule, maintains your live shortlist, and then coaches you through applying to
each role — Claude doing the scanning judgment and the application coaching, you doing
the deciding.

The road there is staged so every phase ships something genuinely usable on its own:

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | The planning/documentation set | ✅ done |
| 1 | **The engine** — profile-agnostic core, platform catalog, first real profile (`borjan-pm`), shortlist liveness sweep, production cutover | ✅ built & live (schedule re-point is the last cutover step) |
| 2 | **Templates + onboarding** — a 22-template role library, a CV-driven setup interview, automated Notion provisioning, a real second user onboarded | ✅ built & live-tested |
| 3 | **Application Assistant** — a Claude Project that walks you through the shortlist, drafts answers in your voice, records applications | next |
| 4 | **Companion app** — screens instead of conversation, wrapping the same engine via the Claude Agent SDK | after 2/3 |
| 5 | The laptop + mobile platform (accounts, hosted scanning) | vision |

## 4. What has been built (Phases 0–2)

### Phase 0 — the plan (2026-07-13)

Four planning documents (project plan, architecture, config spec, progress log) that
defined the vision, the phase boundaries, and the execution discipline before any code
moved. The key architectural insight, written down before the build started: the v3
scanner's ~2,000 lines of scripts were already ~90% profile-agnostic — **the person and
the role were smeared across the config and the skill text, and the work was separation,
not a rewrite.**

### Phase 1 — the engine extraction (2026-07-13 → 07-14)

The single-person `job-scout-pm` v3.1.2 scanner was pulled apart into three cleanly
separated layers (see §6 below): a profile-agnostic **engine** (`core/`, 18 Python
modules), a shared **platform catalog** (`catalog/platforms.yaml`), and per-person
**profiles** (`profiles/<id>/profile.yaml`). Borjan's setup became the first profile,
`borjan-pm`, proven **key-for-key identical** to the old system by a parity script and
back-to-back live runs before anything switched over. A brand-new feature landed in the
same phase: the **shortlist liveness sweep**, which re-checks every not-yet-reviewed
shortlist row on every run and retires the ones that died — the thing that makes
"collect for a few days, apply later" safe. The legacy scanner was then frozen as an
archive (`job-scout-pm/`), and the new engine became production. A one-command-per-step
[cutover runbook](CUTOVER.md) and a [laptop-lane guide](LAPTOP_LANE.md) document the
operational side.

### Phase 2 — templates, onboarding, provisioning (2026-07-15 → 07-17)

Phase 2 turned "one engine, one profile" into "anyone can onboard":

- **A template library** — 22 role templates across 11 streams (software engineering,
  AI/ML, QA, data, design/UX, product management, marketing, sales, people/HR,
  IT support, content writing). A template is a prepared starting point for a role:
  keyword sets, archetypes, scoring rubric text, salary-estimation heuristics (text
  only — deliberately **no** shipped salary numbers, which would always be stale or
  wrong for the reader's country), per-stream platform tier ordering, and
  seniority-title vocabulary ("medior" → mid, "SDE II" → mid, "staff engineer" → staff).
- **The setup interview ("the templater")** — `skills/job-scout-setup/`: a conversational
  onboarding that reads your CV (in-session only — **the CV is never written to the
  repo**), classifies you to the nearest template, tailors it to your real experience and
  goals within strict guardrails, asks only the questions a template default can't
  answer, and finishes with a validated, ready-to-scan profile.
- **Notion provisioning** — `core/provision_notion.py`: creates your three Notion pieces
  (Applications Tracker, Passed/Seen Log, Runs digest page) programmatically under a
  parent page you share with it, idempotently (re-running adopts, never duplicates). The
  one thing the Notion API can't automate (creating the integration and the saved view)
  is handled honestly: the interview instructs you through it, then verifies by probe.
- **New search dimensions**, wired end-to-end: target seniority (soft scoring by default —
  off-target roles are deprioritized with a note, not hidden — with an optional strict
  mode), employment type (full-time / part-time / contract / B2B / freelance, hard filter
  with an `any` escape), optional salary floor (unset = judgment-time estimation, never an
  auto-drop), and FTE pro-rating for part-time targets (a €3,000 full-time floor compares
  as €1,500 at 0.5 FTE).
- **Catalog growth** — 23 → 28 platforms. New stream-appropriate boards (ai-jobs.net,
  icrunchdata, Dribbble, ProBlogger…) entered as researched-but-inactive until a live
  smoke test verified each one; four passed and are active (only Behance remains
  unverified — its jobs load via a path the fetchers can't capture yet), and boards that declare
  categories are now **stream-gated** (a design board never gets fetched for a Java
  profile). Category mappings were live-verified where the platform actually supports
  them — including a real find: JustJoin.it's Java category was being resolved through
  the generic JavaScript slug, and fixing it took a live Java scan from 94 to 319
  candidates.
- **An opt-in learning loop** — with the user's consent, generic (never personal)
  keyword/archetype discoveries from an onboarding are staged in `suggestions/` for a
  human curator to review into the templates. PII is refused by the guard regardless of
  consent.
- **The proof** — a real second user, **Ani Petreska** (Senior Java/Spring Boot engineer,
  returning from a break, deliberately targeting mid-level part-time roles to survey the
  market), was onboarded end-to-end through the interview: CV read, classified to
  `backend-java`, provisioned live in Notion, scanned, judged. Her scan produced an
  honest coverage ledger, correct soft-seniority behavior (44 of 46 senior+ roles
  surfaced-with-a-note rather than hidden), correct employment-type filtering, and —
  after the JustJoin fix — **8 genuinely matching mid-level remote Java roles in her
  Notion inbox**. Throughout all of Phase 2, `borjan-pm` (the production profile) was
  verified behaviorally identical at every step.

## 5. How it works — a scan's life in plain language

What actually happens when a scan runs for a profile:

1. **Pull state.** The profile's history lives in git; the run starts by syncing it, so
   the laptop lane and the cloud lane always agree on what's been seen.
2. **Load + validate.** The profile is loaded, resolved against its template and the
   catalog, and strictly validated. An invalid profile refuses to run with a named
   error — the engine never guesses.
3. **Fetch.** Every active platform in the profile's tiers is enumerated using the
   catalog's URL patterns and the profile's stream/category. Each platform has a
   fallback chain (API → direct fetch → headless browser → mirrors) and documented
   quirks. Platforms that are down get *reported* as down — never silently skipped.
4. **Filter, cheaply first.** Title keyword matching, dedup against the full history
   (nothing you've already seen comes back), then the machine-checkable hard filters
   (below salary floor when one is set, closed location lists that don't include you,
   etc.). Every auto-drop is logged with a reason.
5. **Verify liveness.** Every candidate's actual posting URL is fetched; only a direct
   fetch of the source counts as "live". Dead and unverifiable postings are marked
   honestly — an unverifiable posting is flagged, not trusted.
6. **Sweep the shortlist.** Everything still sitting unreviewed in your Notion inbox
   from previous runs gets re-checked (at most once per 24h per row); rows that died
   are flipped to `Stale/Expired` — visibly retired, never deleted.
7. **Judge.** This is where Claude, not scripts, takes over: every surviving candidate
   gets a full-JD read against the profile's filters, learned lessons (`filter_notes`),
   and scoring rubric. Scripts flag; Claude decides. Scores at or above the profile's
   threshold get shortlisted.
8. **Deliver.** Shortlisted roles land in the profile's Notion **Passed/Seen Log** as
   `New — Unreviewed` with role notes and a fit score; a digest line summarizes the run
   on the **Runs page**; the coverage ledger says exactly which platforms were covered
   and which were down. Drops are recorded with reasons.
9. **Push state.** History, evidence, and decisions are committed back to git.

Three standing safety rules, engine law for every profile: the scanner **never writes
the Applications Tracker** (only a human saying "I applied" does), it **never
auto-applies or scrapes behind logins**, and it **never invents experience** in any
drafted application material.

The whole thing runs in two lanes that converge through git and dedup: **cloud**
(scheduled Claude Code sessions, always-on) and **laptop** (better network coverage —
residential IPs reach boards that block cloud IPs). You can also run it attended and
just talk to it: "run the scan", "I applied to <url>", "why was this dropped?".

## 6. The architecture in one idea

Every piece of knowledge in the system lives in exactly one of three layers, sorted by
one litmus test — *"would a React engineer in Lisbon need this line changed?"*

| Layer | What lives there | Example |
|-------|------------------|---------|
| **Engine** (`core/`, run skill) — true for everyone | fetch fallback chain, liveness definition, dedup rules, coverage honesty, the Tracker write-firewall | "only a direct fetch of the source URL counts as live" |
| **Catalog** (`catalog/platforms.yaml`) — true for everyone using a given board | fetch mode, URL patterns, category slugs per stream, quirks, expired markers | "JustJoin.it list chips lie; fetch the posting page" |
| **Profile** (`profiles/<id>/profile.yaml`) — true for one person | keywords, salary floor, seniority target, employment types, location/citizenship, timezone window, platform tiers, Notion IDs, learned lessons | "EU-citizenship clauses drop even though B2B bypasses visa" |

Templates sit between catalog and profile: a template is a *partial* profile for a role
(the role-generic 80%), and onboarding turns template + your CV + your answers into a
full profile. After that the profile is yours — template updates never silently rewrite
it.

## 7. How we built it — the working method

This project is built by Claude in many sessions across two machines, with Borjan
steering. The method matters as much as the code:

- **PROGRESS.md is the contract between sessions.** Every session starts by reading it,
  never redoes a ✅ step, updates it in the same session as the work, and pushes before
  ending. Plans are written to be executed by a *later* session cold.
- **Plan → adversarial review → build.** Phase 2 was brainstormed interactively (23
  locked decisions, D1–D23 in [PHASE_2_PLAN.md](PHASE_2_PLAN.md)), then a scoped
  adversarial review gate hunted structural gaps in the plan before any build step (it
  found 10, including one that would have broken production), then the build executed
  the amended checklist step by step. Model choice followed the work: the most capable
  model on plan review, an efficient one on well-specified execution.
- **The prime directive: production is sacred.** `borjan-pm` is Borjan's live, daily job
  search. Every phase is purely additive — after every single step, the production
  profile was verified to validate and scan identically. No step was allowed to take it
  offline, and its state history (the most valuable asset) is never regenerated.
- **Strangler pattern, no flag-day.** The new engine ran in parallel and had to prove
  parity (a diff script plus back-to-back live runs producing identical results) before
  the schedules were re-pointed and the legacy scanner was frozen — not deleted.
- **Dogfooding is the QA.** Borjan kept using the scanner for his real search during the
  entire build; Ani's onboarding was a real onboarding, not a fixture. Running it in
  anger is what surfaced the JustJoin Java category bug, the Polish-JD detector, the
  bot-blocked-boards pattern, and the tier-honesty fix.
- **Lessons become rules.** Every friction gets written down where it belongs: generic
  scan lessons into the engine skill, board quirks into the catalog, personal lessons
  into the profile's `filter_notes`, environment gotchas into the docs. Nothing is
  learned twice.
- **Honesty over polish, everywhere.** The coverage ledger reports what was *not*
  scanned. Unverifiable postings are flagged, not assumed live. Unverified boards are
  marked unverified. Templates that the catalog can't fully serve yet say so. This is a
  product principle, not a style choice: a shortlist is only useful if you can trust it.
- **CI guards the contract.** Every PR validates the schema, every template, every
  catalog entry, every profile (including dry-run `--plan` smoke tests for the six demo
  fixture profiles), and the suggestions staging format. Since Phase 2 closes: each
  phase's build checklist ends with a human-readable documentation step — a phase isn't
  done until this guide reflects it.

## 8. Example — Maia gets a job scout

*Maia is the worked example we've used since the first planning session: a React
engineer in Lisbon. Everything below is exactly what the platform does today (Phase 2);
steps marked → Phase 3/4 are where the roadmap picks up. For the real-world version of
this story with live numbers, see Ani's onboarding in §4.*

**Day 1 — onboarding (one conversation, ~15 minutes).**

Maia opens Claude Code in the repo and says: *"Set up job scouting for me — here's my
CV."* The setup interview takes it from there:

1. **Reads the CV in-session** (it is never stored): six years of frontend work, React,
   TypeScript, Next.js, a design-systems stint, currently in Lisbon.
2. **Classifies her** to `software-engineering / frontend-react` and offers the
   neighbors (`fullstack-js`) as a secondary target — Maia says React is the focus, no
   secondary.
3. **Asks consent** to stage anonymized, generic learnings from her setup (say, a
   keyword the template lacked) for template review. She says yes. Nothing personal
   ever enters that channel — the guard refuses PII regardless.
4. **Tailors the template within guardrails**: reweights the template's keyword sets
   toward React/Next.js/TypeScript (it may add CV-obvious tech terms; it may *not*
   invent new filter types), sets `target_seniority: senior` (soft — senior roles score
   highest, staff+ get a note), `employment_type: [full_time, b2b]`, `work_model:
   [remote]`.
5. **Asks only what templates can't know**, in the posture she picks (quick
   confirmations vs. full field-by-field): her salary floor (she gives €3,200 gross/
   month — the platform never invents one), her location terms ("Portugal, Lisbon" — so
   a posting restricted to a country list that excludes Portugal auto-drops), timezone
   comfort, travel tolerance.
6. **Provisions her Notion**: walks her through creating a Notion integration token and
   sharing a parent page (the one genuinely manual step — the interview instructs, then
   verifies by probing), then creates her Applications Tracker, Passed/Seen Log, and
   Runs page programmatically and writes the IDs into her profile.
7. **Validates and dry-runs**: `profiles/maia-fe-react/profile.yaml` passes strict
   validation, and `--plan` prints her rotation — JustJoin.it's JavaScript category,
   Remotive's software-development feed, Himalayas, the ATS boards (Lever, Workable,
   Greenhouse), and the rest of the frontend tier ordering — with her keywords and
   filters resolved. Then the first live scan runs while she watches.

**Day 1, twenty minutes later.** The scan covers ~20 platforms, reports two boards down
(honestly, in the ledger), and the judgment pass puts **seven roles scoring 7.0+** into
her Notion **📥 New — Unreviewed** view — each with a fit score, archetype, and a short
note on why it fits and what to verify. A senior-staff role at a US company is there
too, deprioritized with a note ("above target seniority — still shown"). Forty postings
were dropped with logged reasons (below floor, EU-list-excludes-Portugal, WordPress-only,
already-dead links); she can audit every one.

**Every day after.** Scans run on her schedule (written into her profile; wiring the
cron/Routine is the documented manual step for now — → Phase 4 makes it a toggle). Dedup
means she only ever sees what's *new*; the sweep quietly retires shortlist rows that
died before she got to them — so when she sits down on Saturday to apply, everything in
the inbox is real, live, and pre-vetted. When she applies somewhere, she tells the
scanner *"I applied to <url>"* — the only path that ever writes her Applications
Tracker. When she notices a pattern ("agencies reposting the same role under three
names"), it becomes a `filter_note` in her profile — her scanner gets personally smarter
without touching anyone else's.

**Soon (→ Phase 3).** Saturday's applying session becomes assisted: a Claude Project
reads her shortlist, walks it role by role, re-verifies the key facts, and drafts
application answers in her own voice from her CV and past answers — honestly flagging
any gap instead of papering over it. She decides; it records.

## 9. Where everything lives

```
core/                     the engine — 18 profile-agnostic Python modules
catalog/platforms.yaml    28 platforms: fetch modes, URL patterns, quirks, category slugs
templates/                22 role templates across 11 streams
profiles/                 per-person config + state (borjan-pm, ani-backend-java, 6 demo fixtures)
skills/job-scout-run/     the scan skill: execution protocol + judgment policy
skills/job-scout-setup/   the onboarding interview / templater
suggestions/              staged (consented, non-PII) template enrichments awaiting review
job-scout-pm/             the frozen v3 archive — the system this platform grew out of
docs/                     this guide + the planning set + runbooks
```

Doc map: [PROJECT_PLAN.md](PROJECT_PLAN.md) — vision and phases ·
[ARCHITECTURE.md](ARCHITECTURE.md) — layers, pipeline, contracts ·
[PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md) — every config field and option set ·
[PHASE_2_PLAN.md](PHASE_2_PLAN.md) — the Phase 2 design contract (D1–D23) ·
[PROGRESS.md](PROGRESS.md) — the live build log (read first when resuming) ·
[CUTOVER.md](CUTOVER.md) / [LAPTOP_LANE.md](LAPTOP_LANE.md) — operations runbooks.

## 10. Glossary

- **Profile** — one person's complete search definition + their private state/history.
- **Template** — a role's prepared starting point; becomes a profile at onboarding.
- **Stream / subvariant** — the role taxonomy (e.g. `software-engineering` / `backend-java`).
- **Catalog** — the shared registry of job boards and how to fetch them.
- **Tier** — a profile's platform priority grouping (tier 1 = best converters), seeded
  per-stream by the template, then tuned by real results.
- **Coverage ledger** — the per-run honest account of which platforms were scanned,
  which were down, and which were skipped and why.
- **Liveness** — "the posting's own URL still serves the posting." Mirrors never count.
- **Sweep** — the per-run re-check that retires shortlisted-but-now-dead postings.
- **Judgment pass** — Claude's full-JD read and scoring of every filter survivor.
- **Unattended mode** — scheduled runs: no questions, conservative resolution of
  ambiguity (`❓ NEEDS <user>` flags), Notion as the inbox.
- **Prime directive** — production profiles are sacred; every change is additive and
  verified against them.
