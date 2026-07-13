---
name: job-scout-run
description: >
  Profile-driven job scouting engine (the generic successor to job-scout-pm). Use this
  skill whenever the user asks to search for jobs, scan job boards, run a job search,
  look for new roles, check what's available, refresh the job list, run the morning or
  evening scan, or any similar request — for ANY configured profile under profiles/.
  All search filters, platforms, scoring criteria and output format come from the
  active profile's resolved configuration — never ask the user to re-specify them.
  Also use for scheduled/unattended runs: prompts like "run the scheduled job scan",
  "unattended scan", "AM scan", or "PM scan" trigger Unattended Mode as defined inside.
metadata:
  version: "4.0.0"
  status: pre-cutover — job-scout-pm/SKILL.md v3.1.2 remains production until Phase 1 step 1.12
  created_by: Borjan
  organization: 2Coders Studio
  last_updated: "2026-07-13"
---

# Job Scout — generic run skill (one engine, N profiles)

Automated job-scouting workflow. Run end-to-end without re-confirming filters unless a
specific posting is genuinely ambiguous.

## Profile resolution (do this FIRST, every invocation)

Every run operates on exactly ONE profile: `profiles/<id>/profile.yaml`.
- If the user names one ("scan for borjan-pm", "run the React profile") → use it.
- If exactly one profile exists → use it silently.
- Otherwise ask ONCE which profile to run (interactive) or refuse with a named error
  (unattended — never guess whose pipeline to touch).

`python3 core/scan.py --profile <id> --plan` prints the resolved plan (platforms,
keywords, filters) without fetching — use it to sanity-check an unfamiliar profile.
**Everything user-specific in this document — filters, salary floor, location terms,
keywords, tiers, Notion targets, archetypes, scoring bands — comes from the profile's
resolved config, never from this file.** The profile's `filter_notes` block carries
that user's learned lessons; read it before judging candidates.

## Environment detection (SECOND)

- **Code lane, local** — `core/` exists at repo root, `python3 core/scan.py --help`
  runs, persistent machine: use the **Execution Protocol** below.
- **Code lane, cloud** — same, but an ephemeral Claude Code cloud session: same
  protocol; steps 0 and 8 are existential (git is the state's home — an unpushed run
  evaporates with the container).
- **Chat-native lane** — no scripts or no local network (claude.ai / Cowork):
  use **Appendix A**.

All lanes share ONE dedup history and ONE Notion inbox **per profile**; dedup makes
overlapping runs from different lanes harmless. Profiles never share state.

**Router — load only what the task needs:**
- **Scan / shortlist / assessment** → this file + the profile. Nothing else.
- **Pitch / cover letter / application answers** → read
  `profiles/<id>/references/pitching.md` if present (the user's voice pack); if absent,
  say the profile has no pitch pack yet and offer plain drafting.
- **Gemini cross-check prompt** → `profiles/<id>/references/gemini-prompt.md`, only
  after the user says yes to the post-scan offer.

---

## Execution Protocol (Code lanes)

Run these steps in order. Each step's trigger and action are literal — no step is
optional, none is judged-from-memory. `<id>` = the active profile.

0. **Pull state FIRST:** `python3 core/state_sync.py pull --profile <id>`. Never scan
   against stale state.
1. **Run the scan:** `python3 core/scan.py --profile <id>` (full active rotation;
   `--half AM|PM` for degraded/manual use; the scheduler runs `--full-sweep` on the
   profile's weekly sweep day). The script fetches every active platform (the catalog
   registry resolved through the profile), applies the keyword title-filter, dedups
   against the FULL history in `profiles/<id>/state/seen.jsonl`, applies the
   machine-checkable hard-filter subset, fetches full JDs to the JD cache, runs the
   liveness pass, **runs the shortlist liveness sweep** (re-checks accumulated
   `New — Unreviewed` rows; confident-stale rows are retired with a queued Notion flip
   — see the sweep section), and prints the coverage ledger. It does NOT score.
2. **Read the results:** `profiles/<id>/state/last_run_candidates.json` + the
   per-candidate JD cache files. Each candidate carries: title, company, loc, url,
   platform, posted_at, salary, `keyword_matched`, `flags[]` (regex first-pass hits),
   `salary_assessment` (clears / below_floor / borderline / unparseable — metadata,
   never a machine drop), `link_status`, `jd_status`.
3. **Judgment-layer filter pass (you, on EVERY candidate):** the regexes are a first
   pass only — read each JD against the profile's full filter set (Hard Filters
   section below) plus the profile's `filter_notes`. The Spiralyze lesson (3pm-EST
   buried in the full posting) means scripts flag, you decide. A candidate with any
   `flags[]` entry needs that flag explicitly resolved (drop / clear / ❓ NEEDS USER)
   in its role notes.
4. **Score and tag** per the profile's scoring bands (`scoring.bands` in the resolved
   config — stream-specific, template-provided). Candidates at or above
   `scoring.surface_threshold` are the shortlist. Assign the archetype tag (from the
   profile's archetype list) BEFORE scoring; dual-tag genuine hybrids.
5. **Log every decision immediately** (same-invocation discipline): for each candidate,
   append to seen.jsonl via `core/dedup.py append()` — shortlisted (`status:
   shortlisted`, reason `New — Unreviewed`, fit, archetype, keyword_source = the title
   variant ON the posting, notes = role notes) or dropped (`status: dropped`, real
   reason: `Filtered Out` / `Stale/Expired` / `Duplicate Listing`). Never hold
   decisions for a later "logging pass". Never log roles still pending the user's own
   call.
6. **Sync to Notion:** `python3 core/notion_sync.py --profile <id> --digest
   "[YYYY-MM-DD] [AM|PM] — N new · M dropped · K link-dead · S went stale (sweep) ·
   sources down: [list or none]"`. Scan-driven rows go to the profile's **Passed/Seen
   Log ONLY** — shortlists as `New — Unreviewed` with role notes in the page body;
   sweep retirements as IN-PLACE updates (flip, never duplicate). **The Applications
   Tracker is NEVER a scan-write target, in any mode** — the sync script cannot reach
   the Tracker from the scan path; Tracker writes exist only via the "I applied" flow.
7. **Present the delta output** (format below), then STOP. Interactive scans end with
   the Gemini offer (only if the profile has a gemini-prompt reference); unattended
   scans end silently after the Notion sync.
8. **Push state LAST:** `python3 core/state_sync.py push --profile <id> "scan state
   [<id>]: [date] [AM|PM]"`. NOT optional in either lane. The script auto-merges if
   another run pushed in between. If Notion sync ran tokenless (`NOTION_TOKEN` missing
   → `state/notion_pending.json` exported), push the pending rows AND updates via the
   Notion MCP connector first, mark them synced via dedup.update, and only then push
   state — a cloud run may NEVER end with unsynced shortlist rows and an unwritten
   digest.

**Liveness (2.7.0 definition, enforced in code):** only a direct fetch of the source
URL returning actual JD content counts — never search snippets, aggregator mirrors,
crawl caches, or list-view chips. Headless rendering of the source URL is a fetch
method and counts. Mirror liveness ≠ source liveness — `scan.py` resolves the source
ATS URL when detectable and checks THAT. Mirror/search reconstruction recovers JD
*content* for scoring only, zero liveness. `❓ unverified` in `link_status` is never
upgraded to ✅ by anything but the scripts' own direct/rendered fetch. Evidence for
every check persists in `state/fetch_evidence.jsonl`.

**Shortlist liveness sweep (4.0):** the user may collect for days before applying, so
every scan re-checks accumulated `New — Unreviewed` rows (at most once per
`sweep.recheck_interval_h`, default 24h). Confident-stale → seen.jsonl superseded to
`Stale/Expired` + the Notion row FLIPPED in place (flag, not delete). Unverifiable
twice in a row → `❓ check manually` escalation in the row's notes. The digest line
reports `S went stale`. Sweep counters are in the ledger and candidates JSON.

**Dedup (2.3.0 rule, enforced in code):** match order: exact Job URL first, then
Company + Role title + location/domain — never company+title alone (Andersen lesson:
differing locdom = distinct opportunity). A Tracker-applied match is a hard silent
drop regardless of fit score. Same posting from 2+ platforms in one run: merge into
one row, note "confirmed via 2+ boards", never duplicate.

**Blocked leads (2.6.0, enforced in code):** a lead that survives the fetch fallback
chain but still can't be evaluated is logged `unverified_blocked` immediately — a
confirmed dead end, distinct from `Filtered Out`. If a later scan resolves one, its
reason is UPDATED (superseding append), not duplicated.

**Coverage honesty:** the script-printed ledger is authoritative: a platform that
failed is named in `sources down` and never counted as covered; a platform with no
category mapping for the profile's stream is listed as skipped, never silent.
Partial-labeled-partial is fine; partial-labeled-complete is the failure mode.

**Tier recompute reminder:** tiers are PER-PROFILE DATA (conversion-driven), not
opinion. `scan.py` counts sessions and prints a reminder when the recompute is due.
Primary signal is the profile's Applications Tracker conversion rate. Never recompute
automatically — it's a data session with the user.

**Keyword promote/demote:** candidates record the title variant ON the posting — that
is the promote/demote dataset. The user triggers reviews; surface data +
recommendation, they decide. Expanded-set hits score identically to core hits.

---

## Hard Filters — Auto-Disqualify (judgment layer reads EVERY shortlist candidate)

Machine-checkable subsets are compiled per profile (auto-drops logged `Filtered Out`
by scan.py); YOU verify ALL of these on every candidate that reaches scoring, using
the PROFILE's values. In unattended mode, an ambiguous case resolves conservatively +
`❓ NEEDS USER:` note — never a question.

| Filter type | Rule (values from profile) |
|-------------|---------------------------|
| **Location eligibility** | Roles restricted to a place the candidate isn't in (e.g. US-only/E-Verify for a non-US candidate). |
| **Citizenship** | An explicit citizenship clause the candidate doesn't hold (e.g. EU-citizenship for a non-EU candidate) — distinct from visa sponsorship; B2B status does NOT bypass it (Cyclad lesson, in borjan-pm's filter_notes). |
| **Travel** | Per `hard_filters.travel` — `none` means "occasional"/"25%"/"as needed" all disqualify. |
| **Timezone** | Work required after `timezone_window.latest_end_local` in the candidate's timezone. **Snippet-blindness caveat:** working-hours requirements routinely appear ONLY in the full posting — the full JD must be read before shortlisting. |
| **Salary** | Below the profile's floor (use `salary_assessment` + the template's estimation heuristics for unpublished). Borderline = verify, never auto-drop. |
| **Tool lock-in** | `tool_lockin_drop` list as PRIMARY skill. |
| **Clearance** | Any security clearance / public trust, when `clearance: drop`. |
| **Role exclusions** | `role_exclusion_terms` describing the role's core (e.g. pure-BA for the PM stream) — flagged by scripts, decided by you. |
| **Closed/expired** | 404/410/"no longer available" (scan.py logs these as link-dead). |
| **Grind culture** | Long hours/nights/weekends as a *baseline expectation*, when `grind_culture: drop`. Distinct from occasional on-call. Hard drop, never a scoring penalty. |
| **"Location-fluid" marketing copy** | "Work from anywhere" culture copy ≠ open worldwide. If 2+ live reqs are each tagged to specific countries that exclude the candidate, the company is country-set-restricted regardless of marketing (Moro Tech lesson). |
| **Regional-payroll mismatch** | Benefits/payroll currency signals a target region that excludes the candidate despite a "worldwide" label (Rapido Solutions lesson: MXN benefits under a worldwide tag). |
| **Closed location list** | A closed country list under a "remote in <region>" label that does not name any of the profile's `location_match_terms` — drop without further verification (enforced first-pass by the detector). |

## Scoring

Bands come from the profile's template (`scoring.bands` — stream-specific criteria for
9.0–10.0 / 8.0–8.9 / 7.0–7.9). One decimal always (`8.6`, never `9`). Score only roles
that pass hard filters; surface only ≥ `scoring.surface_threshold`; below-threshold
drops are logged with the real reason. Salary estimation for unpublished postings uses
the template's `salary_estimation_heuristics`. **Posting-age heuristic:**
live-but-2+-months-old is a soft staleness signal — combined with any other flag, note
the age explicitly.

## Country-Clone Posting Pattern

Some companies post the same role as near-identical per-country reqs (Spiralyze
lesson — the candidate-city variant surfaced only via a targeted company+city search).
- **Trigger:** 2+ near-identical reqs (same title/JD, different country tag) from one
  company in the candidates set.
- **Action:** one targeted follow-up — search `"[Company]" "[role]" [candidate city]`
  (and/or the candidate's country), or grep the platform's full enumeration in the
  candidates JSON — before concluding no accessible opening exists.
- **Freshness caveat:** clones go stale independently — verify the specific variant
  being shortlisted. **Multi-req caveat:** one company can run multiple concurrent
  reqs for the same function — check for a newer or differently-scoped posting from
  the same company before shortlisting.

## Platform knowledge

`catalog/platforms.yaml` is the registry; per-platform `quirks` fields carry the
judgment-relevant lessons (list chips lie on JustJoin.it; NoDesk keeps expired
postings listed; EOR boards mix domains; Crossover grind-culture flags; etc.) — the
quirks travel into platform notes on the ledger. Read them, believe them. LinkedIn is
a discovery tripwire only (guest endpoint, hard caps, no login/cookies ever;
auth-walled JDs → `login-walled — open manually`). Rejected platforms (template +
profile `rejected` lists) are do-NOT-re-add without new evidence; new platforms earn
tier placement via the 5-session conversion-rate bar.

---

## Output Format — Delta

```
## Job Scout Delta — <profile> — [YYYY-MM-DD] [AM|PM]

N new / M auto-dropped / K link-dead / S went stale (sweep)

### ✅ Shortlist (new since last run)
| # | Role | Company | Platform | Archetype | Fit | Salary | URL | Link Status |
|---|------|---------|----------|-----------|-----|--------|-----|-------------|

### 📋 Role Notes
**1. [Role] — [Company]**
Why it scores [X.X]: [2–3 sentences: fit, key JD requirements, flags]
Apply by: [date / "no deadline stated"]
What to send: [CV only / CV + cover letter / ATS form / direct email]

[coverage ledger line: covered N platforms · sources down: … · sweep: …]
```

Empty delta = the one-liner + ledger. Always the direct job URL, never the platform
homepage. Chat-table URLs render as clickable markdown links; the Notion Job URL
property stays the full raw URL. **Table + role notes, then STOP** — never auto-draft
a cover letter or pitch, even for a single standout. The user asks explicitly per role.

**Post-scan Gemini offer (interactive scans only, and only if the profile has
`references/gemini-prompt.md`):** one direct question — cross-check prompt wanted?
Generate ONLY on yes.

---

## Unattended / Scheduled Mode

Activates when the run prompt says "unattended", "scheduled", "AM scan", or "PM scan".
Notion is the inbox; nobody is watching the chat.

1. **No questions, ever.** Every ambiguity resolves conservatively + `❓ NEEDS USER:`
   prefix in the row's Notes.
2. **No Gemini offer.** On a zero-hit run, add "Gemini cross-check may be worth a
   manual run" to the digest line.
3. **No pitches, no drafts** — rows and digest only.
4. **Delivery target is the profile's Notion:** shortlist rows as `New — Unreviewed`
   with role notes in the page body, sweep flips applied, digest line written — BEFORE
   the run ends. The user reviews the "📥 New — Unreviewed" view.
5. **Failure honesty:** platform fetch failures land in `sources down`, never silently
   counted as covered.
6. **Chat output minimal:** the script ledger + one summary line.

Scheduling (local): per the profile's `schedule.runs` via Claude Code scheduled tasks
or cron with `claude -p "Run the job scout AM scan for <id> per
skills/job-scout-run/SKILL.md. Unattended mode."`. Zero-prompt permissions: copy
`claude-settings.example.json` to `.claude/settings.json`. `NOTION_TOKEN` must be set
for unattended Notion writes (no token → pending export = a FAILED sync, not a
success). Scheduling (cloud): Claude Code cloud Routines firing the same prompt into
fresh sessions on this repo. Cloud-IP caveat: datacenter IPs draw more bot-blocking —
the honest `sources down` ledger reports whatever a lane can't reach. Local and cloud
schedules may coexist; dedup absorbs the overlap.

---

## Application Tracking — the ONLY Tracker write path

When the user says they applied ("applied here", "just applied") in a chat session:
1. Update the role's seen.jsonl record: `core/dedup.py` `update(url, {"status":
   "applied", ...})` (or `append` if never logged — Manual Entry).
2. `python3 core/notion_sync.py --profile <id> --applied <url>` → creates the Tracker
   row: Status `Applied` (never "Interviewing"), Source `Claude Skill Scan` or `Manual
   Entry`, Date Applied date-only, Fit Score as decimal string, Keyword Source = the
   posting's title variant, Notes as a table property; long analysis in the page body.
3. The script refuses if the record isn't `status: applied` — Tracker rows exist only
   for applications the user explicitly confirmed.

When the user passes on a shortlisted role, flip its Passed/Seen row's Reason Passed
to the real reason (`User Declined`, etc.) and update seen.jsonl to `status: passed`
with their stated reason verbatim if given.

## Manual JD Assessment (user pastes/uploads a JD)

Assessment only by default: identify the core problem the role is solving, apply the
profile's hard filters, score, archetype-tag. Pitch only when explicitly requested.
Scans never read Claude Project files (CV/cover letters are pitch-time-only, and live
in the user's Project, not this repo).

## What This Skill Does NOT Do

- No auto-applying, no filling application forms unasked, no sending emails on the
  user's behalf.
- No computer-use browser control of any kind. The headless `render(url) → html`
  wrapper is the ONLY permitted browser use — a JS-capable fetch, nothing more.
- No logged-in LinkedIn scraping, no authenticated sessions of any kind.
- No automated tier recompute, no automated keyword promote/demote — both stay
  Claude+user data sessions.
- No cross-profile reads or writes, ever.

---

## Files

- `skills/job-scout-run/SKILL.md` — orchestration + policy (this file).
- `catalog/platforms.yaml` — shared platform registry (fetch modes, quirks, patterns).
- `templates/` — role templates; `profiles/<id>/profile.yaml` — the user's config.
- `core/scan.py` — orchestrator (`--profile`, `--plan`, `--half`, `--full-sweep`,
  `--no-headless`, `--no-sweep`).
- `core/profile_loader.py` — catalog+template+profile → effective config (strict).
- `core/fetch_boards.py` / `render.py` / `check_links.py` / `sweep.py` /
  `linkedin_tripwire.py` — fetch, liveness, shortlist sweep, tripwire.
- `core/dedup.py` / `state_sync.py` — seen-log semantics; git state round-trip.
- `core/notion_sync.py` — one-way Notion push (+ in-place sweep updates; `--applied`).
- `core/salary.py` — parsing/normalization behind `salary_assessment`.
- `core/validate.py` — platform-wide validator (CI). `core/migrate_state.py` — legacy
  state migration (cutover step).
- `profiles/<id>/state/` — seen.jsonl, runs.json, fetch_evidence.jsonl, sweep.json,
  jd_cache/, last_run_candidates.json.

**Setup (once per machine):** Python 3.11+; `pip install requests pyyaml selectolax
playwright` then `playwright install chromium` (in managed environments with a
pre-installed Chromium, set `JOB_SCOUT_CHROMIUM=/path/to/chromium` instead — never run
playwright install there). `NOTION_TOKEN` env var for unattended Notion sync.

---

# Appendix A — Chat-native lane (claude.ai/Cowork, no scripts)

Everything above (profile resolution, hard filters, scoring, archetypes,
country-clone, multi-req, output discipline, Tracker rules) applies unchanged. This
appendix restores what the scripts replace, compressed from v2.10.0 — semantic content
unchanged, parameterized by the profile.

**Token-Efficiency Protocol:** (1) OR-batched keyword clusters from the profile's
core+expanded sets, ~5 queries/platform, each core keyword alone (substring catches
variants), expanded set OR-batched as the last query. **Saturation escape hatch
(mandatory):** a ≈10/10-relevant results page triggers one dedicated follow-up query
for buried variant terms on that platform. (2) Snippet-first triage: full-fetch only
when the snippet plausibly clears hard filters AND could score ≥ the threshold.
(3) Cheap liveness rechecks (~400-token reads). (4) Batch same-turn Notion writes;
~30s between rapid Notion queries. (5) Minimal narration. (6) Bulk dedup pre-fetch at
scan start — query the profile's Passed/Seen Log AND Applications Tracker ONCE each
(recent-first, LIMIT 100), hold both in context. (7) Scans never read Project files.

**Mandatory Execution Log:** before presenting any shortlist or "no results", output
the literal per-platform checklist (✅ searched directly / 🔁 mirror-incidental only —
does NOT count / ❌ not run / ⏭️ deliberate skip). A scan is not complete while any ❌
remains.

**Platforms:** the catalog registry + the profile's tiers apply. Cross-category pass
(mandatory): category boards file roles under adjacent categories — one unrestricted
`site:[domain]` + title-keyword pass per category platform per scan. ATS `site:`
patterns every scan: `job-boards.greenhouse.io`, `jobs.lever.co`,
`apply.workable.com`, `[company].pinpointhq.com`. **Stale Platform Demotion:** 100%
stale on 2 separate sessions → quarterly-recheck with dated annotation, shown as ⏭️,
never a silent skip.

**Verification Step (per-role):** one full fetch per role; confirm live; check the
full JD for buried travel/timezone language; note exact salary. Fetch-blocked → retry
once, then reconstruct via `web_search` mirrors, THEN log `Unverified/Blocked`.
`PROVENANCE_REQUIRED`, robots blocks, bot-403s, and boilerplate-only fetches are tool
hiccups, not fit signals. Reconstruction recovers JD *content* for scoring only — it
NEVER confers liveness.

**Stale Link Recheck (literal last action before output):** re-fetch every URL in the
final table via direct fetch only, cheap mode. ✅ is earned ONLY by a successful
direct same-turn fetch returning JD content. **Session-resume provenance:** after ANY
resume, every staged URL is unverified; re-establish provenance or void the entry.

**Shortlist sweep (chat-native):** query the profile's Passed/Seen `New — Unreviewed`
rows; for rows older than the sweep interval, recheck liveness (same rules); flip
stale rows to `Stale/Expired` in place with a dated note — never delete, never
duplicate.

**Notion writes (MCP):** `parent: {"type": "data_source_id", "data_source_id":
"<id>"}` is MANDATORY on every create (parentless calls are accepted silently and
create blank stubs — 27-row incident). Post-write spot-check at least one created
page per batch. Platform select pre-check before first write of a new platform name.
Real-time dedup logging: drops logged the same turn they're confirmed. Shortlist rows
land in the Passed/Seen Log BEFORE the chat table is presented. The profile's
`output.notion` block carries all IDs — go straight to them; on failure search by
title; create only if both miss and report the new ID. Never create-by-title.

**Unattended (chat-native):** per-DAY completeness across the tier split; digest line
per run on the profile's Runs page (newest on top); LinkedIn incidental snippet pass,
best-effort; isolated blocked fetches are expected and are NOT source-down.

---

## Changelog

**4.0.0** (2026-07-13) — Phase 1 extraction: one engine, N profiles. Everything
user/stream-specific moved to catalog + templates + profiles; shortlist liveness
sweep added; salary normalization added. Lineage: job-scout-pm 1.0.0 → 3.1.2
(see `job-scout-pm/CHANGELOG.md` — frozen as the v3 archive at cutover).
