---
name: job-scout-pm
description: >
  Senior IT Project Manager / Delivery Manager / Scrum Master job scouting skill for Borjan Petreski.
  Use this skill whenever the user asks to search for jobs, scan job boards, find PM openings, run a job search,
  look for new roles, check what's available, refresh the job list, or any similar request related to finding
  remote IT project management opportunities. Also trigger when the user says "run the scan again", "any new jobs?",
  "check the boards", "update the pipeline", "run the morning scan", or "run the evening scan". This skill encodes
  all search filters, platform list, scoring criteria, and output format agreed in previous sessions — never ask
  the user to re-specify these. Also use this skill for scheduled or unattended scan runs — prompts like
  "run the scheduled job scan", "unattended scan", "AM scan", or "PM scan" trigger Unattended Mode as defined inside.
metadata:
  version: "3.1.2"
  created_by: Borjan
  organization: 2Coders Studio
  last_updated: "2026-07-13"
---

# Job Scout — Senior PM / Delivery Manager / Scrum Master

Borjan's automated job scouting workflow. Run end-to-end without re-confirming filters unless a specific posting is genuinely ambiguous.

## Environment detection (do this FIRST, every invocation)

- **Code lane, local** — `scripts/` exists next to this file, `python3 scripts/scan.py --help` runs, and this machine is persistent (Borjan's laptop): use the **Execution Protocol** below. State lives on local disk and converges through git (steps 0/8 — mandatory in both Code lanes since 3.1.1, because both lanes run on schedules).
- **Code lane, cloud** — same as above but running in an ephemeral Claude Code cloud/remote session (fresh container, repo cloned at session start): use the **Execution Protocol** below. Steps 0 and 8 are existential here, not just convergence — git is the state's home, and skipping the push means the run's dedup history is lost when the container dies.
- **Chat-native lane** — no scripts or no local network (claude.ai / Cowork): use **Appendix A**, the v2.10.0 chat-native flow, unchanged in meaning.

All three lanes share one dedup history and one Notion inbox; dedup makes overlapping runs from different lanes harmless.

**Router — load only what the task needs:**
- **Scan / shortlist / assessment** → this file is sufficient. Do NOT read the reference files.
- **Pitch / cover letter / application answers** → read `references/pitching.md` first (voice rules, canonical source docs, closing gate, Q&A patterns).
- **Gemini cross-check prompt** (only after Borjan says yes to the post-scan offer) → read `references/gemini-prompt.md`.

---

## Candidate Profile

**Name:** Borjan Petreski · **Location:** Skopje, N. Macedonia (CET/EEST, UTC+1/+2)
**Employment model:** B2B contractor (direct invoicing, no visa/sponsorship needed) AND full-time — both equally fine; never deprioritize or flag full-time as a concern.
**Experience:** 7+ yrs IT PM / Delivery Manager / Scrum Master / Proxy PO
**Tools:** Jira, Confluence, Azure DevOps, Jira Admin, Agile/Scrum, Kanban · **Certs:** PSM, PSPO, ECBA, AZ-104 (expired)
**Domains:** Travel & Leisure, EdAI, Social Prospecting, IoT, Media/Streaming

---

## Execution Protocol (Code lane — replaces the v2.x Token-Efficiency Protocol)

Run these steps in order. Each step's trigger and action are literal — no step is optional, none is judged-from-memory.

0. **Pull state FIRST (both Code lanes):** `python3 scripts/state_sync.py pull`. Cloud: the container started with whatever state was last pushed to git; this fetches anything newer. Laptop: this picks up every unattended cloud run's state (and any skill updates on the branch) since the last local run. Never scan against stale state.
1. **Run the scan:** `python3 scripts/scan.py` (full active rotation — the AM/PM half-split is retired; `--half AM|PM` exists only for degraded/manual use, and the scheduler on Mondays runs `--full-sweep` to catch anything the freshness window missed). The script fetches every active platform (config.yaml is the single registry), applies the keyword title-filter, dedups against the FULL history in `state/seen.jsonl` (both-log backfill included), applies the machine-checkable hard-filter subset, fetches full JDs to `state/jd_cache/`, runs the liveness pass, and prints the coverage ledger. It does NOT score.
2. **Read the results:** `state/last_run_candidates.json` + the per-candidate `jd_cache` files. Each candidate carries: title, company, loc, url, platform, posted_at, salary, `keyword_matched`, `flags[]` (regex first-pass hits), `link_status`, `jd_status`.
3. **Judgment-layer filter pass (you, on EVERY candidate):** the regexes are a first pass only — read each JD against the full Hard Filters table below. The Spiralyze lesson (3pm-EST buried in the full posting) means scripts flag, you decide. A candidate with any `flags[]` entry needs that flag explicitly resolved (drop / clear / ❓ NEEDS BORJAN) in its role notes.
4. **Score and tag** per the Scoring section. ≥7.0 survivors are the shortlist.
5. **Log every decision immediately** (same-invocation discipline, invariant since 2.x): for each candidate, append to `state/seen.jsonl` via `scripts/dedup.py`'s `append()` — shortlisted (`status: shortlisted`, reason `New — Unreviewed`, fit, archetype, keyword_source = the title variant ON the posting, notes = role notes) or dropped (`status: dropped`, real reason: `Filtered Out` / `Stale/Expired` / `Duplicate Listing`). Never hold decisions for a later "logging pass". Never log roles still pending Borjan's own call.
6. **Sync to Notion:** `python3 scripts/notion_sync.py --digest "[YYYY-MM-DD] [AM|PM] — N new · M dropped · K link-dead · sources down: [list or none]"`. Scan-driven rows go to the **Passed/Seen Log ONLY** — shortlists as `New — Unreviewed` with role notes in the page body — and the digest line lands on the pinned **Job Scout Runs** page. **The Applications Tracker is NEVER a scan-write target, in any mode** (2.7.0 violation: a scan wrote 3 shortlist rows to the Tracker, fabricating application history and poisoning the cross-check). The sync script cannot reach the Tracker from the scan path — Tracker writes exist only via the "I applied" flow below.
7. **Present the delta output** (format below), then STOP. Interactive scans end with the Gemini offer; unattended scans end silently after the Notion sync.
8. **Push state LAST (both Code lanes):** `python3 scripts/state_sync.py push "scan state: [date] [AM|PM]"`. This is NOT optional in either lane: an unpushed cloud run evaporates with the container, and an unpushed laptop run leaves the scheduled cloud runs scanning against stale history — re-fetching and re-judging every role this run already settled. The script auto-merges if another run pushed in between (append-only logs union cleanly). If Notion sync ran tokenless (`NOTION_TOKEN` missing → `state/notion_pending.json` exported), push the pending rows via the Notion MCP connector before this step, mark them synced via dedup.update, and only then push state — a cloud run may NEVER end with unsynced shortlist rows and an unwritten digest.

**Liveness (2.7.0 definition, enforced in code):** only a direct fetch of the source URL returning actual JD content counts — never search snippets, aggregator mirrors, crawl caches, or list-view chips (JustJoin.it's own "New" badges contradicted its own expired offer pages, 2026-07-10; NoDesk's category page lists expired postings). Headless rendering of the source URL is a fetch method and counts. Mirror liveness ≠ source liveness (Superside: 3 live mirrors, source Lever URL 404) — `scan.py` resolves the source ATS URL when detectable and checks THAT. Mirror/search reconstruction recovers JD *content* for scoring only, zero liveness. `❓ unverified` in `link_status` is never upgraded to ✅ by anything but the scripts' own direct/rendered fetch. Evidence for every check persists in `state/fetch_evidence.jsonl` — no session-resume re-verification ritual exists anymore.

**Dedup (2.3.0 rule, enforced in code):** `seen.jsonl` carries the full history of BOTH Notion logs. Match order: exact Job URL first, then Company + Role title + location/domain/client — never company+title alone (Andersen lesson: two distinct Delivery Manager reqs, different client/city; differing locdom = distinct opportunity). A Tracker-applied match is a hard silent drop regardless of fit score. Same posting surfacing from 2+ platforms in one run: merge into one row, note "confirmed via 2+ boards" (a freshness positive), never duplicate.

**Blocked leads (2.6.0, enforced in code):** a lead that survives the fetch fallback chain (api/direct → headless → mirrors) but still can't be evaluated is logged `unverified_blocked` immediately — a confirmed dead end, distinct from `Filtered Out` — so it never costs a repeat fetch-and-block cycle (SysMap lesson). If a later scan resolves one, its reason is UPDATED (superseding append), not duplicated.

**Coverage honesty:** the script-printed ledger replaces the v2.x 20-item chat checklist. Its intent survives unchanged: coverage is visible and verifiable, a platform that failed is named in `sources down` and never counted as covered — partial-labeled-partial is fine; partial-labeled-complete is the failure mode. An isolated blocked posting among successful fetches on the same platform is NOT source-down (2.4.2 rule).

**Tier recompute reminder:** tiers in config.yaml are DATA (2.8.0 recompute state), not opinion. `scan.py` counts sessions in `state/runs.json` and prints a reminder when 5 accumulate. The recompute itself stays a Claude+Borjan data session — primary signal is Applications Tracker conversion rate (Source = Claude Skill Scan), never raw drop volume. Never recompute automatically.

**Keyword promote/demote:** candidates record the title variant on the posting (not the matched filter) — that is the promote/demote dataset. Borjan triggers reviews; surface data + recommendation, he decides. Expanded-set hits are scored identically to core hits, never as a lesser category.

---

## Hard Filters — Auto-Disqualify (all 13 — judgment layer reads EVERY shortlist candidate)

Machine-checkable subsets live in config.yaml as regex first-pass (auto-drops are logged `Filtered Out` by scan.py); YOU verify all of these on every candidate that reaches scoring. In unattended mode, an ambiguous case resolves conservatively + `❓ NEEDS BORJAN:` note — never a question.

| Filter | Rule |
|--------|------|
| **Location** | US-only, must-be-local, E-Verify employer |
| **EU citizenship** | Distinct from visa sponsorship — B2B contractor status bypasses visa/payroll needs but does NOT bypass an explicit EU-citizenship clause (agency/legal restriction, common on JustJoin.it; confirmed: Cyclad). Drop even when everything else fits. |
| **Travel** | Any travel requirement — "occasional", "25%", "as needed", all disqualify |
| **Timezone** | Requires work after 17:00 CET/EEST. **Snippet-blindness caveat:** working-hours requirements routinely appear ONLY in the full posting (confirmed: Spiralyze Skopje req, 3pm EST). No timezone language in a snippet = unconfirmed, not clear — the full JD (jd_cache) must be read before shortlisting. |
| **Salary** | Below €2,500/month net equivalent (~$35k/yr or ~€3,000/month gross published) |
| **Platform tool lock-in** | Dynamics 365, SAP, Salesforce, Workday, ServiceNow, Oracle as primary skill |
| **Clearance** | Any security clearance / public trust / background investigation |
| **Pure BA** | BA-only roles with no PM/delivery component |
| **Closed/expired** | 404, 410, "no longer available" (scan.py logs these as link-dead) |
| **Grind culture** | JD states long hours / nights / weekends as a *baseline expectation* (confirmed: micro1's "grind very long hours every day, including weekends"). Distinct from occasional on-call/crunch. Hard drop, never a scoring penalty. |
| **"Location-fluid" marketing copy** | "Work from anywhere" culture copy ≠ open worldwide. If 2+ live reqs are each tagged to specific non-worldwide countries, the company is country-set-restricted regardless of marketing (confirmed: Moro Tech — copy says anywhere, every req tags Greece/Portugal/Brussels). |
| **LATAM-targeted payroll despite "worldwide" label** | Check benefits currency as signal (confirmed: Rapido Solutions — Remotive worldwide tag, MXN benefits). |
| **Explicit EU-country-list enumeration (2.10.0)** | A closed country list under a "Europe remote"/"EMEA remote" label (e.g. "Austria, Belgium, … United Kingdom") enumerates EU/EEA states — **North Macedonia is a Balkan non-EU country and is never included**. If Skopje/N. Macedonia isn't named and the list is closed (not "and more"/"worldwide"), drop without further verification. Distinct pattern from location-fluid copy and from country clones. |

---

## Scoring (1.0–10.0, one decimal always — `8.6`, never `9`)

Score only roles that pass hard filters; surface only ≥ 7.0. Anchor the band, then adjust by tenths on how many band criteria are actually met.

- **9.0–10.0 — Near-perfect:** full delivery lifecycle (pre-sales/A&D/dev/release); Agile/Scrum/Kanban delivery management; Jira+Confluence; Worldwide or EMEA explicit; no travel, no tool lock-in; salary confirmed above threshold.
- **8.0–8.9 — Strong:** senior PM/SM delivery role; globally open/EMEA; agile required, tools familiar; salary likely clears (company profile suggests it); one minor gap OK. **Domain note:** a stated CS/data-ops/engineering-background *preference* is not a stretch — only dock if hands-on technical execution is a core daily duty.
- **7.0–7.9 — Worth reviewing:** PM/SM/DM role; globally open but salary unconfirmed; minor flag (e.g. staffing-agency placement); slight domain stretch.
- **Below 7.0 — drop silently** (but log to seen.jsonl with the real reason).

**Role Archetype tag (assign before scoring, shown in table + notes):** Delivery Manager · Scrum Master · Technical PM · BA-leaning (closest to the hard-filter boundary — flag explicitly). Dual-tag genuine hybrids ("Delivery Manager / Scrum Master").

**Salary estimation when unpublished:** US/UK HQ paying globally → likely $60k+; Senior/Lead → higher band; staffing agency with Fortune-500 end client → "unconfirmed, likely clears"; Eastern-European-focused company → "likely below threshold, verify before applying."

**Posting-age heuristic:** live-but-2+-months-old is a soft staleness signal (JustJoin.it especially slow to pull expired listings). Not auto-exclusion, but combined with any other flag, note the age explicitly so Borjan can weigh it.

---

## Country-Clone Posting Pattern

Some companies post the same role as near-identical per-country reqs (confirmed: Spiralyze — Brazil/Baku/Belgrade/Lisbon/Bucharest/Sri Lanka/Cape Town/**Skopje**; the Skopje variant surfaced only via a targeted company+"Skopje" search).
- **Trigger:** 2+ near-identical reqs (same title/JD, different country tag) from one company in the candidates set.
- **Action:** one targeted follow-up — search `"[Company]" "[role]" Skopje` (and/or `"North Macedonia"`), or grep the platform's full enumeration in the candidates JSON — before concluding no Skopje-accessible opening exists.
- **Freshness caveat:** clones go stale independently (confirmed: Sleek's India clone closed while the worldwide one was ambiguous) — verify the specific variant being shortlisted.

**Multi-req caveat (2.9.0):** one company can run multiple concurrent reqs for the same function (broader mirror copy vs newer regionally-locked direct req) — check for a newer or differently-scoped posting from the same company before shortlisting.

---

## Platform knowledge (judgment-relevant; the full registry lives in config.yaml)

config.yaml is the single platform registry — 23 entries, every active one tiered (2.7.1 lesson: a tierless platform gets silently skipped; config validation now errors). Per-platform quirks in config carry into candidate flags. The ones that change YOUR reads:

- **JustJoin.it** — highest-signal B2B/salary-transparent source, but disproportionately carries EU-citizenship and Poland-residency/language requirements — check the JD level on every hit. List chips lie; liveness is offer-page only.
- **NoDesk** — undated listings are unverified-by-default; say so in role notes and recommend checking the company careers page before pitch effort. Its category page keeps expired postings listed.
- **Welcome to the Jungle** — France-skew; verify eligibility carefully.
- **Deel (EOR)** — roles skew finance/ops/accounting-adjacent as often as classic IT delivery — score domain fit carefully, don't assume every PM title is Agile/Scrum-flavored.
- **Crossover (EOR)** — genuinely worldwide-open, independent-contractor structured (B2B-compatible), but also runs USA/nearshore-restricted reqs — verify per-role, never trust the brand. Grind-culture flags common — read every JD.
- **Known recurring stale:** CloudLinux Scrum Master — stale across multiple mirrors; do not resurface (it's in seen.jsonl).
- **Rejected platforms** (config `rejected_platforms`): do not re-add without new evidence. New platforms earn tier placement via the same 5-session conversion-rate bar.

**LinkedIn** is a discovery tripwire only (`scripts/linkedin_tripwire.py`, guest endpoint, hard caps, no login/cookies ever). Cards are snippet-level: full JD via the public job page where it renders; auth-walled → flag `login-walled — open manually` in the role notes. Never spend scan budget on LinkedIn query engineering (2026-07-10 finding: an authenticated-access problem, not coverage-tuning).

---

## Output Format — Delta

```
## Job Scout Delta — [YYYY-MM-DD] [AM|PM]

N new / M auto-dropped / K link-dead

### ✅ Shortlist (new since last run)
| # | Role | Company | Platform | Archetype | Fit | Salary | URL | Link Status |
|---|------|---------|----------|-----------|-----|--------|-----|-------------|

### 📋 Role Notes
**1. [Role] — [Company]**
Why it scores [X.X]: [2–3 sentences: fit, key JD requirements, flags]
Apply by: [date / "no deadline stated"]
What to send: [CV only / CV + cover letter / ATS form / direct email]

[coverage ledger line: covered N platforms · sources down: …]
```

Empty delta = the one-liner + ledger (+ Gemini offer if interactive). Always the direct job URL, never the platform homepage. **Chat-table URLs render as clickable markdown links** — `[lever.co/acme](https://jobs.lever.co/acme/1234)` — never bare text; the Notion Job URL property stays the full raw URL. **Table + role notes, then STOP** — never auto-draft a cover letter or pitch, even for a single standout. Borjan asks explicitly per role.

**Post-scan Gemini offer (interactive scans only, every scan, even zero-hit):** one direct question — does he want a Gemini cross-check prompt? Generate ONLY on yes, per `references/gemini-prompt.md`.

---

## Unattended / Scheduled Mode

Activates when the run prompt says "unattended", "scheduled", "AM scan", or "PM scan". Notion is the inbox; nobody is watching the chat.

1. **No questions, ever.** Every ambiguity resolves conservatively + `❓ NEEDS BORJAN:` prefix in the row's Notes.
2. **No Gemini offer.** On a zero-hit run, add "Gemini cross-check may be worth a manual run" to the digest line.
3. **No pitches, no drafts** — rows and digest only.
4. **Delivery target is Notion:** shortlist rows as `New — Unreviewed` with role notes in the page body (why it scores X.X, flags, apply-by, what to send, any ❓ lines) — written via notion_sync BEFORE the run ends. Borjan reviews the "📥 New — Unreviewed" view.
5. **Failure honesty:** platform fetch failures land in `sources down` (runs.json + digest), never silently counted as covered.
6. **Chat output minimal:** the script ledger + one summary line. The full table lives in Notion.

Scheduling, local (Borjan's machine): two daily runs (08:00 AM / 18:00 PM) via Claude Code Desktop scheduled tasks, or cron with `claude -p "Run the job scout AM scan per SKILL.md. Unattended mode."`. Zero-prompt permissions: copy `claude-settings.example.json` to `.claude/settings.json` in the working directory. `NOTION_TOKEN` must be set for unattended Notion writes (no token → notion_sync exports `state/notion_pending.json` and the digest goes unwritten — treat as a failed sync, not a success).

Scheduling, cloud: Claude Code cloud Routines firing "Run the job scout [AM|PM] scan per SKILL.md. Unattended mode." into fresh sessions on this repo/branch. Requirements: the Cloud lane steps 0/8 are mandatory per run; Notion writes via `NOTION_TOKEN` in the cloud environment's settings (preferred) or the Notion MCP fallback. Known cloud-IP caveat: datacenter IPs draw more bot-blocking than a residential one (measured 2026-07-11/12: Remote Rocketship fully Cloudflare-blocked, WWR page fetches 403 though its RSS works) — the honest `sources down` ledger reports whatever a given lane can't reach. Local and cloud schedules may coexist; dedup absorbs the overlap.

---

## Application Tracking — the ONLY Tracker write path

When Borjan says he applied ("applied here", "just applied") in a chat session:
1. Update the role's seen.jsonl record: `scripts/dedup.py` `update(url, {"status": "applied", ...})` (or `append` if it was never logged — e.g. Manual Entry).
2. `python3 scripts/notion_sync.py --applied <url>` → creates the Tracker row: Status `Applied` (never "Interviewing" — live options: Applied/Screening/Interview/Offer/Rejected/Withdrawn), Source `Claude Skill Scan` or `Manual Entry`, Date Applied date-only, Fit Score as decimal string, Keyword Source = the posting's title variant, Notes as a table property (1–2 sentences); cover letters / long analysis go in the page body.
3. The script refuses if the record isn't `status: applied` — Tracker rows exist only for applications Borjan explicitly confirmed.

When Borjan passes on a shortlisted role, flip its Passed/Seen row's Reason Passed to the real reason (`User Declined`, etc.) and update seen.jsonl to `status: passed` with his stated reason verbatim if given.

---

## Manual JD Assessment (Borjan pastes/uploads a JD)

Assessment only by default: identify the core problem the role is solving, apply hard filters, score, archetype-tag. Pitch only when explicitly requested — then read `references/pitching.md`. Scans never read Project files (CV/cover letter/articles are pitch-time-only).

## What This Skill Does NOT Do

- No auto-applying, no filling application forms unasked, no sending emails on Borjan's behalf.
- No computer-use browser control of any kind (visible browser, mouse, clicks, screenshots). The headless `render(url) → html` wrapper is the ONLY permitted browser use — a JS-capable fetch, nothing more.
- No logged-in LinkedIn scraping, no authenticated sessions of any kind.
- No automated tier recompute, no automated keyword promote/demote — both stay Claude+Borjan data sessions.

---

## Files in this skill

- `SKILL.md` — orchestration + policy (this file). Scripts do the plumbing.
- `config.yaml` — single source of truth: platforms (23, tiered), keywords, filters-as-data, caps, Notion IDs, rejected platforms.
- `scripts/scan.py` — orchestrator (full rotation; `--half`, `--full-sweep`, `--no-headless`).
- `scripts/fetch_boards.py` — per-platform fetchers: API-first, deterministic HTML parse, headless fallback, mirror pipeline.
- `scripts/render.py` — headless rendering as a fetch method; API surface is `render(url) → html` only.
- `scripts/check_links.py` — parallel liveness checker (2.7.0 definition in code); also standalone: `check_links.py urls.txt` for same-session URL-handoff rechecks (Blexr/CloudLinux lesson) at zero token cost.
- `scripts/dedup.py` — seen-log read/write/match (URL-exact first, strict 3-part key fallback).
- `scripts/linkedin_tripwire.py` — guest-endpoint discovery, rate-capped.
- `scripts/notion_sync.py` — one-way push to Notion (typed, parent-asserted writes; `--applied` for the Tracker flow).
- `scripts/state_sync.py` — git round-trip for scan state (steps 0/8, mandatory in both Code lanes since 3.1.1 — keeps one converged dedup history across laptop and cloud schedules).
- `state/` — seen.jsonl (dedup source of truth), runs.json (ledger + recompute counter), fetch_evidence.jsonl, jd_cache/, last_run_candidates.json.
- `references/pitching.md` — pitch/cover-letter tasks only (unchanged from 2.10.0).
- `references/gemini-prompt.md` — Gemini cross-check offer accepted only (unchanged from 2.10.0).
- `CHANGELOG.md` — full 1.0.0 → 3.0.0 history. SKILL.md carries only the current version.

**Setup (once per machine):** Python 3.11+; `pip install requests pyyaml selectolax playwright` then `playwright install chromium` (in managed environments with a pre-installed Chromium, set `JOB_SCOUT_CHROMIUM=/path/to/chromium` instead — never run playwright install there). `NOTION_TOKEN` env var for unattended Notion sync.

---

# Appendix A — Chat-native lane (v2.10.0 flow, for claude.ai/Cowork without scripts)

Everything above (profile, hard filters, scoring, archetypes, country-clone, multi-req, output discipline, Tracker rules) applies unchanged. This appendix restores the machinery that scripts replace in the Code lane. Rules are compressed from v2.10.0 — semantic content unchanged.

**Token-Efficiency Protocol:** (1) OR-batched keyword clusters, 5 queries/platform: Q1 `"project manager"`, Q2 `"delivery manager"`, Q3 `"scrum master"`, Q4 `"program manager"` (each alone — substring catches their variants), Q5 `"implementation manager" OR "release manager" OR "proxy product owner" OR "agile delivery lead"`. **Saturation escape hatch (mandatory):** a ≈10/10-relevant results page triggers one dedicated follow-up query for buried variant terms on that platform. (2) Snippet-first triage: full-fetch only when the snippet plausibly clears hard filters AND could score ≥7.0. (3) Cheap liveness rechecks: `text_content_token_limit` ≈ 400. (4) Batch same-turn Notion writes; wait ~30s between rapid Notion queries. (5) Minimal narration. (6) Bulk dedup pre-fetch at scan start — query the Passed/Seen Log AND the Applications Tracker ONCE each (`SELECT * FROM "collection://<id>" LIMIT 100`, recent-first), hold both in context, dedup against the cache. (7) Scans never read Project files.

**Mandatory Execution Log:** before presenting any shortlist or "no results", output the literal per-platform checklist (✅ searched directly / 🔁 mirror-incidental only — does NOT count / ❌ not run / ⏭️ deliberate skip). A scan is not complete while any ❌ remains; partial-labeled-partial is fine, partial-labeled-complete is the failure mode.

**Platforms:** the registry and tiers in config.yaml apply (or the v2.10.0 numbered list if config is unavailable: Tier 1 JustJoin.it/Remotive/Workable/Lever/Himalayas; Tier 2 Remote Rocketship ×2/NoDesk/Greenhouse; Tier 3 the rest; EuropeRemotely demoted quarterly-recheck; Otta merged into WttJ). Cross-category pass (mandatory): category boards file Technical-PM roles under Engineering/Product (confirmed: Holepunch on WWR) — one unrestricted `site:[domain]` + Q4 pass per category platform per scan. ATS `site:` patterns every scan: `job-boards.greenhouse.io`, `jobs.lever.co`, `apply.workable.com`, `[company].pinpointhq.com` — all five clusters. **Stale Platform Demotion:** 100% stale on 2 separate sessions → quarterly-recheck with dated annotation, shown as ⏭️, never a silent skip; re-promote when a recheck shows life.

**Verification Step (per-role):** one full fetch per role; confirm live; check the full JD for buried travel/timezone language; note exact salary. **Fetch-blocked → retry once, then reconstruct via `web_search` mirrors, THEN log `Unverified/Blocked`.** `PROVENANCE_REQUIRED` (WebFetch's same-turn approval prompt — near-guaranteed unattended since nobody can click allow), robots blocks, bot-403s, and boilerplate-only fetches are tool hiccups, not fit signals — never let them silently kill a candidate. Reconstruction recovers JD *content* for scoring only — it NEVER confers liveness.

**Stale Link Recheck (literal last action before output):** re-fetch every URL in the final table via direct fetch only, cheap mode, even if verified earlier this scan. ✅ is earned ONLY by a successful direct same-turn fetch returning JD content; snippet fallback or fetch-impossible (bot-block/JS site) = `❓ Unverified`, never ✅. Same-session staleness is real (Blexr, CloudLinux died within one conversation): any later URL hand-off triggers a fresh cheap re-fetch. **Session-resume provenance:** the WebFetch gate doesn't persist across session breaks — after ANY resume, every staged URL is unverified; re-establish provenance (search → fetch the result link) or void the entry (a voided entry never makes the table).

**Notion writes (MCP):** `parent: {"type": "data_source_id", "data_source_id": "<id>"}` is MANDATORY on every `notion-create-pages` call — a parentless call is accepted silently and creates blank stub pages (27-row incident, 2026-07-09). Post-write spot-check at least one created page before treating a batch as done. Platform select pre-check before first write of a new platform name. Real-time dedup logging: drops are logged the same turn they're confirmed, batched within the turn is fine, never held for a later pass. Shortlist rows go to the Passed/Seen Log as `New — Unreviewed` BEFORE the chat table is presented. Pinned singleton pages — Job Scout Runs `398054b0-88af-81b7-8670-fef8aad15254`, Migration Delta `398054b0-88af-8158-9cae-e1d7c44eb48b` (parent `b4aaa7e8-bc50-40a4-accb-a052ca10c026`); Tracker `collection://560bd8e3-e45f-42c5-8c77-1e70a7e53c74` (parent `6fed5421-39ae-4896-9046-d5554dff976d`); Passed/Seen `collection://21ab771f-802a-402b-ba71-f92f94d911d9`. Go straight to pinned IDs; on failure search by title; create only if both miss and report the new ID. Never create-by-title (2.5.1 race).

**Unattended (chat-native):** AM half = Tier 1+2; PM half = Tier 3 + ATS patterns + cross-category; per-DAY completeness; digest line per run on Job Scout Runs (newest on top); LinkedIn incidental snippet pass, best-effort, `LinkedIn snippet — verify manually`; isolated blocked fetches are expected and are NOT source-down.

**Friction logging:** the v2.5.0/2.6.0 Migration Delta end-of-run ritual is retired — the migration shipped. Genuine scan-logic lessons still become SKILL.md rules; environment frictions in the Code lane go to the repo CHANGELOG/issue list.

---

## Changelog

Current version: **3.1.2** (2026-07-13) — permission allowlist covers the whole scan session (first laptop run prompted constantly). Full history: see `CHANGELOG.md`.
