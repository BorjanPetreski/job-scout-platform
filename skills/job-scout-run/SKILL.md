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
  version: "4.6.1"
  status: "production — core engine live; legacy job-scout-pm frozen as the v3 archive (2026-07-14). Phase 3a additive: scan-start Tracker-read reconciliation (token-gated, read-only, borjan-pm behavior unchanged when tokenless). 4.5.0: work-arrangement detection + opt-in hard-eligibility drops (hybrid-when-remote, full-time-when-part-time). 4.6.0: generalized non-target-language detection (configurable search.languages, multi-language) + opt-in language_mismatch drop; per-param drop telemetry + over-constraint nudge (a hard filter can't silently zero results). Profile-gated, borjan-pm resolved-config byte-identical. 4.6.1: fixed a silent JD-text-extraction degradation (missing selectolax fed raw CSS/JS to every text detector) + added requirements.txt + a SessionStart hook so cloud/web sessions install deps automatically."
  created_by: Borjan
  organization: 2Coders Studio
  last_updated: "2026-07-20"
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
  say the profile has no pitch pack yet and offer plain drafting. **Honesty-check before
  drafting any answer** (screening questions included): read the profile's reference
  docs first; draft the closest HONEST adjacent-experience answer if one exists; say
  "insufficient data" and flag the domain gap explicitly if none does — never invent
  experience to smooth over a gap. The pitching pack carries the full procedure.
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
   **Scan-start reconciliation (3a.4, D8):** with `NOTION_TOKEN` set, the scan first READS
   the profile's Applications Tracker and back-fills any matching seen.jsonl record to
   `applied` — so a role the Application Companion (Phase 3a, claude.ai side) recorded as
   applied dedups this run and exits the sweep's scope. It is READ-ONLY on the Tracker (the
   firewall holds), token-gated (tokenless → an honest ledger skip line), and idempotent; it
   changes nothing about what the scan fetches, filters, scores, or writes as shortlist rows.
2. **Read the results:** `profiles/<id>/state/last_run_candidates.json` + the
   per-candidate JD cache files. Each candidate carries: title, company, loc, url,
   platform, posted_at, salary, `keyword_matched`, `flags[]` (regex first-pass hits +
   the computed flags below), `salary_assessment` (clears / below_floor / borderline /
   unparseable — metadata, never a machine drop), `link_status`, `jd_status`. Computed
   annotations added at scan time (4.1 — all ADDITIVE, all "scripts flag, you decide"):
   - `non_target_language` flag (+ `language_note`): the JD's dominant language is known and
     NOT in the profile's `search.languages` (default `[en]`; may be multi, e.g. `[de, en]`) —
     a local-hire / apply-wall signal (JustJoin.it Polish-only JD/ATS lesson, generalized). A
     drop when `hard_filters.language_mismatch: drop`; else judge it.
   - `start_date_passed` flag (+ `start_date_note`): the JD's own stated start/target
     month is already past — the soft posting-age signal escalated to explicit ⚠️
     (Cyclad "still listed live, start already gone"). Verify freshness before shortlisting.
   - `missing_company` flag: the source gave no Company (data-quality note; reference it
     by role+platform and try to recover the company from the JD).
   - `company_prior` list + `applied_variant_saturation` flag: prior seen/applied reqs
     from the SAME company — see the Country-Clone section.
   - `seniority_detected` (+ `seniority_off_target` flag): the band the posting's TITLE
     maps to via the resolved seniority lexicon, set only when the profile targets bands
     (`search.target_seniority`). Off-target is a SOFT signal — resolve it per D7 below.
   - `employment_detected` (+ `employment_off_target` flag): employment types the posting
     states plainly, set only when the profile constrains `search.employment_type` (and
     `any` isn't the escape). Off-target = a stated type outside the accept set — see D8 below.
     **Part-time guard:** an explicit `full_time` (without `part_time`) is off-target even when
     `b2b`/`contract` co-occurs — "Full-time B2B" is full-time HOURS, not part-time availability.
   - `work_arrangement_detected` (+ `work_arrangement_mismatch` flag): remote/hybrid/on_site the
     posting states (the platform's structured loc tag — "City (hybrid)" — wins over body prose),
     set only when the profile opts into `hard_filters.work_arrangement`. Mismatch = hybrid/on-site
     with no remote offered, for a remote-only `search.work_model` — a hard eligibility miss.
   - **NOTE — engine may have already dropped the machine-certain ones.** When the profile sets
     `hard_filters.work_arrangement: drop` and/or `employment_mismatch: drop`, the scan itself Filters
     Out loc-tagged hybrid/on-site (remote-only profile) and JD-stated full-time (part-time profile)
     BEFORE they reach you — logged `Filtered Out` in seen.jsonl, never in the candidates JSON. Those
     modes are opt-in; a profile in `flag` mode still hands you the flag to resolve (below).
3. **Judgment-layer filter pass (you, on EVERY candidate):** the regexes are a first
   pass only — read each JD against the profile's full filter set (Hard Filters
   section below) plus the profile's `filter_notes`. The Spiralyze lesson (3pm-EST
   buried in the full posting) means scripts flag, you decide. **A candidate with ANY `flags[]`
   entry MUST have that flag explicitly resolved** (drop / clear / ❓ NEEDS USER) in its role
   notes — a hard-eligibility flag (`work_arrangement_mismatch`, `non_target_language`,
   `employment_off_target`) left unresolved is a bug: never shortlist a flagged candidate without
   stating why the flag doesn't disqualify. Ani's first run leaked hybrid + full-time + Polish
   roles precisely because flagged candidates were shortlisted on fit alone.
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
| **Salary** | Below the profile's floor (use `salary_assessment` + the template's estimation heuristics for unpublished). Borderline = verify, never auto-drop. **Floorless (D20):** when the profile sets no floor, `salary_assessment` is `unparseable` by design — there is NO machine floor; judge salary ENTIRELY from the posting via the template's `salary_estimation_heuristics`, never an auto-drop. **Part-time (D22):** when a floor IS set for a part-time target it is already pro-rated by `fte_fraction` in `salary_assessment` — compare against the pro-rated figure the script reports. |
| **Tool lock-in** | `tool_lockin_drop` list as PRIMARY skill. |
| **Clearance** | Any security clearance / public trust, when `clearance: drop`. |
| **Role exclusions** | `role_exclusion_terms` describing the role's core (e.g. pure-BA for the PM stream) — flagged by scripts, decided by you. |
| **Closed/expired** | 404/410/"no longer available" (scan.py logs these as link-dead). |
| **Grind culture** | Long hours/nights/weekends as a *baseline expectation*, when `grind_culture: drop`. Distinct from occasional on-call. Hard drop, never a scoring penalty. |
| **"Location-fluid" marketing copy** | "Work from anywhere" culture copy ≠ open worldwide. If 2+ live reqs are each tagged to specific countries that exclude the candidate, the company is country-set-restricted regardless of marketing (Moro Tech lesson). |
| **Regional-payroll mismatch** | Benefits/payroll currency signals a target region that excludes the candidate despite a "worldwide" label (Rapido Solutions lesson: MXN benefits under a worldwide tag). |
| **Closed location list** | A closed country list under a "remote in <region>" label that does not name any of the profile's `location_match_terms` — drop without further verification (enforced first-pass by the detector). |
| **Non-target-language JD / ATS** | `non_target_language` flag: the JD (and usually the application form) is in a language NOT in the profile's `search.languages` (default `[en]`; may be multi, e.g. `[de, en]` keeps both) — a local-hire signal the keyword/location filters miss. `hard_filters.language_mismatch: drop` pre-filters these mechanically; otherwise verify the applicant can actually complete the application. |
| **Target seniority (D7)** | Only when the profile sets `search.target_seniority`. Map the posting's stated level to a band (the scan's `seniority_detected` is the first pass; read the JD's own wording too via the resolved lexicon incl. the template's `seniority_titles` — "medior"→mid, "SDE II"→mid, etc.). **`strict: false` (default) = SOFT:** in-band = full score; well-ABOVE the target band (e.g. `staff` for a `mid` target) = deprioritize **with a one-line note** ("senior-of-target — likely over-levelled"); below-band = flag, judge. **`strict: true` = HARD:** a confidently out-of-band posting is a drop, logged `Filtered Out (seniority: <detected> not in <bands>)`. `seniority_off_target` is the scan's soft hint — never a mechanical drop on its own. |
| **Employment type (D8)** | Only when `search.employment_type.accept` is set and does NOT contain `any`. The posting's employment type must be in the accept set. Use `employment_detected` as the first pass, but confirm from the JD (the marker may sit only in the body). A posting whose stated type is confidently outside the accept set is a drop, logged `Filtered Out (employment: <detected> not in <accept>)`. **Part-time guard:** for a profile that accepts `part_time`, an explicit FULL-TIME posting is off-target even on a B2B/contract vehicle ("Full-time B2B" = full-time hours) — don't let a `contract` accept-match mask it. Unstated type is NOT a drop — judge it. `employment_mismatch: drop` makes the engine pre-drop these; caveat (D8): a hard employment filter thins sparse boards — the user's informed choice; `any` is the escape. |
| **Work arrangement (D-remote)** | Only when the profile opts into `hard_filters.work_arrangement` (`flag` or `drop`). The posting's arrangement must satisfy `search.work_model`. The platform's structured loc tag ("Kraków (hybrid)", "Warszawa (remote)" on JustJoin.it) is authoritative; "X days in office / on-site" in the JD is the same signal. Hybrid/on-site for a remote-only profile = a hard eligibility miss (you can't work a Poland-hybrid desk remotely from Skopje) → drop, logged `Filtered Out (work arrangement <detected> vs work_model <remote>)`. "Remote or hybrid" that genuinely offers remote is NOT a mismatch. In `drop` mode the engine pre-filters the loc-tagged cases; in `flag` mode `work_arrangement_mismatch` is yours to resolve. |

## Scoring

Bands come from the profile's template (`scoring.bands` — stream-specific criteria for
9.0–10.0 / 8.0–8.9 / 7.0–7.9). One decimal always (`8.6`, never `9`). Score only roles
that pass hard filters; surface only ≥ `scoring.surface_threshold`; below-threshold
drops are logged with the real reason. Salary estimation for unpublished postings uses
the template's `salary_estimation_heuristics`. **Posting-age heuristic:**
live-but-2+-months-old is a soft staleness signal — combined with any other flag, note
the age explicitly. **Stated-start-date escalation:** when the scan sets
`start_date_passed` (the JD's own start/target month is already gone), that soft signal
is now an explicit ⚠️ — re-verify the posting is genuinely current and note it in the
role notes even if the link still checks live (Cyclad: listed live, start already past).

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
- **Cross-check against already-applied variants (location-agnostic):** the 3-part
  dedup key treats every country tag as distinct BY DESIGN, so a Belgrade variant of a
  role you already applied to in Skopje/Warszawa is NOT auto-suppressed. Each candidate
  carries `company_prior` (prior reqs from the same company, with status) — when 2+ of
  them are `applied` and share the candidate's role-family, the scan sets
  `applied_variant_saturation`. Treat that as a strong dedup-drop signal (the user
  already pursued this role at other locations), but confirm the JD is genuinely the
  same opportunity first — a same-company role that is genuinely different scope still
  stands (the Krakow-PM case: different role, correctly kept).
- **Surface prior history, don't re-ask:** whenever a candidate has `company_prior`,
  prepend a one-line note to its role notes listing the other reqs and their status
  (e.g. "Andersen also has: DM-Skopje [Applied], DM-Warszawa [Applied], DM-Belgrade
  [Declined]") so the user never has to ask "is this a variant of one I applied to?".

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

## Run effort / model tier (design-and-defer — NOT wired yet, D9/D10)

The profile may carry `run.effort` (`fast`|`mid`|`high`) and an optional
`run.effort_by_run_type` (e.g. `{daily: fast, weekly_deep: high}`). These are **recorded
and documented in Phase 2 but NOT yet wired to actual model selection** — today every run
uses whatever model the session/scheduler launched with. Do not change your behavior based
on `run.effort`; it is forward-declared config.

- **Mapping (design target):** `fast → Haiku`, `mid → Sonnet`, `high → Opus`. Entitlement-
  shaped: free tier = `fast` + unscheduled; paid tiers unlock `mid`/`high` + a weekly deep
  sweep + scheduling.
- **Two-stage judgment (design target):** the capable path splits the judgment pass into a
  cheap-model **triage** of the raw candidate list (obvious drops / clear-keeps) and a
  capable-model **deep read** of the shortlist survivors, via subagent delegation at the
  chosen model. `effort_by_run_type` lets a frequent cheap daily sweep coexist with a
  capable weekly deep sweep.
- **Why deferred:** model-at-launch belongs with the scheduler (also deferred, D12) — the
  scheduler picks the launch model per run type, and/or the judgment step spawns a subagent
  at the chosen model. Phase 2 ships the schema + this design only; the wiring lands with
  scheduling. See PHASE_2_PLAN §7 / ARCHITECTURE "Effort / model tier".

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
- `core/salary.py` — parsing/normalization behind `salary_assessment` (floorless + FTE pro-rating).
- `core/data/seniority_lexicon.yaml` — base title→band lexicon (D21), extended per stream by
  templates' `seniority_titles`; resolved into the config for `target_seniority` judgment.
- `core/validate.py` — platform-wide validator (CI). `core/migrate_state.py` — legacy
  state migration (cutover step).
- `profiles/<id>/state/` — seen.jsonl, runs.json, fetch_evidence.jsonl, sweep.json,
  jd_cache/, last_run_candidates.json.

**Setup (once per machine):** Python 3.11+; `pip install -r requirements.txt` then
`playwright install chromium` (in managed environments with a pre-installed Chromium,
set `JOB_SCOUT_CHROMIUM=/path/to/chromium` instead — never run playwright install
there). Claude Code cloud/web sessions do this automatically via the `SessionStart`
hook (`.claude/settings.json` → `.claude/hooks/session-start.sh`) — a missing
`selectolax` otherwise degrades JD-text extraction silently (2026-07-20 finding, see
`core/fetch_boards.py`'s `_visible_text()`). `NOTION_TOKEN` env var for unattended
Notion sync.

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
(recent-first, LIMIT 100), hold both in context, **and cache each row's page ID/URL
from that one pull.** A later status flip (stale, applied, declined) is then a single
`update` on the cached page ID — never re-query Job-URL→page-ID per decision (that
query→flip-per-row pattern draws repeated 429s even at ~30s spacing). (7) Scans never
read Project files.

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
`output.notion` block carries all IDs — **read them from the profile every run; never
trust an ID cached in memory across sessions** (a one-character-stale data-source ID
caused a 404 — memory IDs drift, the profile is the source of truth). Go straight to the
profile's IDs; on a 404/failure re-read the profile then search by title; create only if
both miss and report the new ID. Never create-by-title.

**Unattended (chat-native):** per-DAY completeness across the tier split; digest line
per run on the profile's Runs page (newest on top); LinkedIn incidental snippet pass,
best-effort; isolated blocked fetches are expected and are NOT source-down.

---

## Changelog

**4.4.0** (2026-07-18) — Phase 3a step 3a.4: the ONE permitted scanner change — a scan-start
**Application-Tracker reconciliation**. With `NOTION_TOKEN` set, `core/scan.py` READS the
Tracker before dedup/sweep and back-fills matching seen.jsonl records to `applied`, so a role
the Application Companion recorded as applied dedups on the next scan and leaves the sweep's
scope (the D8 cross-process dedup handoff). Plus a read-before-write guard in
`notion_sync.apply_sweep_update` (flip only rows still `New — Unreviewed`, never clobber a
companion-resolved `User Declined`/`User Applied Elsewhere` row). READ-ONLY on the Tracker
(firewall intact), token-gated (tokenless = honest ledger skip, byte-identical behavior),
idempotent. No change to what a scan fetches, filters, scores, or writes as shortlist rows.

**4.3.0** (2026-07-16) — Phase 2 step 2.8: documented the `run.effort` / model-tier mapping
(fast→Haiku, mid→Sonnet, high→Opus), the two-stage judgment design (cheap triage → capable
shortlist read via subagent), and the entitlement shape. Design-and-defer (D10): recorded +
documented only, NOT wired to model selection — that lands with the deferred scheduler. No
runtime behavior change.

**4.2.0** (2026-07-16) — Phase 2 judgment-layer wiring (step 2.2), additive. New profile
fields become behavior: `target_seniority` (soft scoring / `strict` hard drop via the
resolved seniority lexicon — base `core/data/seniority_lexicon.yaml` + template
`seniority_titles`), `employment_type` (hard accept-set filter with the `any` escape),
floorless salary judgment (no floor → estimate entirely from the posting via the
template heuristics) and part-time floor pro-rating by `fte_fraction`. scan.py adds the
cheap `seniority_detected`/`employment_detected` annotations (both fire ONLY when the
profile sets the field — a profile that sets neither, e.g. `borjan-pm`, is unchanged).

**4.1.0** (2026-07-14) — post-cutover lessons fed back from the first attended run on the
new engine. Engine: computed candidate annotations (`non_english_jd` Polish-only-JD
detector, `start_date_passed` stated-start-in-past detector, `missing_company`
data-quality flag, `company_prior` prior-reqs surface + `applied_variant_saturation`
location-agnostic country-clone check). Skill: non-English-JD hard filter, prior-history
surfacing instead of re-asking, Notion page-ID caching to kill the query→flip 429s,
memory-ID re-verification rule, honesty-check step in the pitch router. Legacy
`job-scout-pm/` frozen as the v3 archive; parity CI gate retired (tiers now living data).

**4.0.0** (2026-07-13) — Phase 1 extraction: one engine, N profiles. Everything
user/stream-specific moved to catalog + templates + profiles; shortlist liveness
sweep added; salary normalization added. Lineage: job-scout-pm 1.0.0 → 3.1.2
(see `job-scout-pm/CHANGELOG.md` — frozen as the v3 archive at cutover).
