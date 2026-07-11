# job-scout-pm — Changelog

## 3.0.0 (2026-07-11) — Claude Code migration

Converted the skill from a chat-native, tool-call-per-step workflow into a
script-assisted pipeline for Claude Code: unrestricted local HTTP, local state,
scheduled unattended execution, delta output. Policy layer (v2.10.0 rules)
unchanged; plumbing replaced. Spec: jobscoutpm v3.0.0 SPEC r2.

### Added
- `scripts/scan.py` — full-rotation orchestrator (AM/PM half-split retired; `--half`
  kept for degraded use). Emits `state/last_run_candidates.json`; never scores.
- `scripts/fetch_boards.py` — per-platform fetchers, API-first with deterministic
  HTML parsing and headless-render fallback; structured `source_down` markers,
  no silent empty results.
- `scripts/render.py` — headless page rendering as a fetch method; entire API is
  `render(url) -> html` (computer-use ban is structural, per §0 policy).
- `scripts/check_links.py` — parallel liveness checker implementing the 2.7.0
  definition in code; every check persists evidence to `state/fetch_evidence.jsonl`.
- `scripts/dedup.py` — full-history dedup on append-only `state/seen.jsonl`
  (URL-exact first, strict 3-part key fallback; company-less rows are URL-only).
- `scripts/linkedin_tripwire.py` — guest-endpoint discovery, ≤10 requests/run,
  ≥3s delay, immediate stop on 429/999. No login, no cookies, ever.
- `scripts/notion_sync.py` — one-way local→Notion REST sync; typed write wrapper
  (hard-coded data-source parent + post-write assertion), generic Platform-select
  pre-check, run-digest append with anti-race; Tracker reachable ONLY via the
  interactive `--applied` flow. Tokenless fallback exports `notion_pending.json`
  for MCP push.
- `config.yaml` — single platform registry (23 entries, tiers mandatory per
  invariant #14), keywords-as-filters, machine-checkable hard-filter subset,
  caps, pinned Notion IDs, per-DB platform-name maps, rejected-platforms list.
- One-time backfill: 203 rows (188 Passed/Seen + 15 Tracker) imported into
  `seen.jsonl`, so local dedup starts with full history instead of a 100-row cache.
- `claude-settings.example.json` — scoped zero-prompt permission template
  (copy to `.claude/settings.json` on the scan machine).
- Notion Passed/Seen Log gained a "📥 New — Unreviewed" review view
  (filter Reason Passed = New — Unreviewed, newest first).

### Platform findings during migration (2026-07-11, all live-verified)
- **Himalayas**: HTML listing now 403s; NEW public API `/jobs/api` (offset/limit,
  ~100k jobs) adopted — better than the lost HTML path.
- **JustJoin.it**: API endpoint drifted to `/v2/user-panel/offers/by-cursor`
  (pagination param is `from`; category 15 = PM; perPage caps at 20).
- **Deel**: disabled Ashby's public posting API (REST and GraphQL both empty);
  full job set (224 postings) now parsed from careers-page embedded JSON.
- **Remotive**: REGRESSED post-delta — anonymous API is a 41-job stub (params
  ignored, 0 PM); category HTML masks companies and carries no per-job links even
  rendered. Enumeration effectively dead anonymously; per-job pages remain public.
  Flagged for next tier recompute.
- **Remote Rocketship**: Cloudflare now 403s list pages AND sitemap, direct and
  headless — degraded to honest source-down (was: per-job 403s only).
- **JustRemote**: listings lazy-load on scroll; headless snapshot carries zero
  postings; no API found — degraded to honest source-down.
- **Welcome to the Jungle**: rendered search results are Algolia/consent-gated;
  no anonymous enumeration channel — mirrors remain the path.
- **NoDesk**: category page keeps expired postings listed; posting pages show
  "Job Expired" (marker added). 15/16 harvested PM links were expired on arrival.
- **WWR**: category RSS 301s to nothing; all-jobs `/remote-jobs.rss` adopted
  (cross-category pass now inherent).
- **LinkedIn guest endpoint**: verified live; 46–52 cards per run under caps.

### Changed
- Liveness verification, dedup, hard-filter first pass, and coverage ledger moved
  from chat protocol into scripts; scoring/judgment stays with Claude in-session.
- Coverage ledger: script-printed + `state/runs.json` (with tier-recompute counter)
  replaces the 20-item chat checklist; partial-labeled-partial preserved.
- Session-resume provenance re-establishment retired — fetch evidence persists in
  `state/fetch_evidence.jsonl` outside the context window.
- Migration Delta end-of-run friction ritual retired — scripts log their own errors;
  `sources down` in the digest carries the honest-failure signal.

### Environment notes
- Behind a TLS-re-terminating agent proxy, Chromium's TLS 1.3 ClientHello gets
  reset — `render.py` caps that hop to TLS 1.2 when `HTTPS_PROXY` is set (lossless;
  no proxy → full TLS 1.3).
- Headless escalations in `check_links.py` batch through ONE browser; concurrent
  per-thread Chromium launches silently fail under load (found via 15 false
  Unverified/Blocked NoDesk leads; all re-resolved to Stale/Expired).

## 1.0.0 → 2.10.0 (migrated verbatim from v2.10.0 SKILL.md)

- **2.10.0** (2026-07-10) — Second platform-expansion round, full-budget sweep at Borjan's request: retested the 3 pending candidates from 2.9.0 fully (Built In, Rippling, Crossover) plus 8 new candidates (Wellfound, PowerToFly, Braintrust, Contra, FlexJobs, Jobspresso, Remote.co, and a second look at Built In/Rippling with targeted queries). Result: **Crossover confirmed and added** (#23, Tier 3, mirror-required via LinkedIn) — a live "Scrum Master, Upland" role explicitly "(Any country) — $60,000/year USD," corroborated by LinkedIn mirrors. Built In and Rippling both downgraded from "promising" to rejected on full retest — Built In is ~90%+ US-dominated despite good fetch reliability, Rippling's "EMEA"/"Global" titles are confirmed US-based-employee roles via the company's own Himalayas listing tags. All 8 new candidates rejected: Wellfound/PowerToFly/Braintrust are US-or-nearshore-only, Contra isn't a job board, FlexJobs is paywalled/high-volume-low-signal, Jobspresso is sparse and jurisdiction-restricted, Remote.co is US/Poland-dominated. Also captured a platform-agnostic scan-logic insight from FlexJobs testing (see the note after platform #23): explicit EU-country-list enumerations exclude North Macedonia even under "Europe remote" labels — treat as a hard filter, not a fluid marketing-copy case. 11 platforms tested this round, 1 added — the discipline of "test before adding, retest before trusting an earlier promising-but-unconfirmed lead" held up.
- **2.9.0** (2026-07-10) — Tested EOR/global-employer career pages as a new sourcing category (proposed after JustJoin.it negative-keywords and LinkedIn-formal-pass ideas both failed live testing — see 2026-07-10 addenda on the Claude Code Migration Delta LinkedIn entry). 6 companies tested: Deel confirmed live (1 EMEA "Project Manager, Accounting" role, verified via 3 mirrors) — added as platform #22, Tier 3, mirror-required (Ashby/JS-rendered, same discipline as Pinpoint HQ). Remote.com, Oyster, Multiplier, Velocity Global, Globalization Partners all tested clean-negative or inconclusive today — not added; Rippling produced one promising but unconfirmed lead (Himalayas link-bounce quirk, not necessarily dead) — flagged for a second-mirror recheck next session, not added yet. Rule going forward: EOR platforms get the same 5-session conversion-rate bar as everything else before earning a tier promotion.
- **2.8.0** (2026-07-10) — First data-driven tier recompute (5 logged sessions reached: 2026-07-09 AM/PM, 2026-07-10 AM/PM/PM-follow-up). Primary signal switched from raw drop-volume to Applications Tracker conversion rate (Source = Claude Skill Scan), since the Passed/Seen Log's "New — Unreviewed" flag only exists post-2.7.0 and undercounts earlier hits. Result: Himalayas promoted Tier 2 → Tier 1 (25% conversion, 2/8 — best of any platform) despite modest volume; JustJoin.it stays Tier 1 on volume + B2B salary-transparency value despite the lowest conversion rate of any high-volume platform (2%, 1/43); Tier 3's last-place ordering fully validated — 0% conversion across all 9 platforms combined (41 logged, 0 converted). Next recompute due after 5 more logged sessions.
- **2.7.1** (2026-07-10) — Hotfix: Pinpoint HQ (#21) was the only platform in the 20+1 rotation not assigned to any tier — it lived solely in the Mandatory ATS Search Patterns section, which no tier command cross-references. Result: a 2026-07-10 "run Tier 1+2" then "run Tier 3" session covered all 20 numbered platforms but silently never ran Pinpoint HQ, and Borjan had to catch the gap manually. Added Pinpoint HQ to Tier 3 so any tier-based run command now reaches it; cross-referenced at its ATS-pattern entry too. Greenhouse/Lever/Workable needed no fix — they're ATS patterns AND tier platforms (Tier 1/2), so tier commands already reached them.
- **2.7.0** (2026-07-10) — Four mandatory-behavior corrections from the 2026-07-10 full-scan post-mortem. (1) **Shortlist Destination hard rule (new section):** shortlisted roles are written to the Passed/Seen Log with Reason Passed = `New — Unreviewed` BEFORE the output table is presented — same real-time discipline as drop logging; the Applications Tracker is NEVER written by a scan, in any mode — Tracker rows exist only when Borjan confirms an actual application (violation: the 2026-07-10 scan wrote its 3 shortlist rows to the Tracker, fabricating application history and poisoning the 2.3.0 cross-check). (2) **Liveness definition tightened:** only a direct, same-turn fetch of the source URL returning JD content counts as liveness — search snippets, aggregator mirrors, careers-page crawl caches, and platform list-view chips/counters never do; the final stale-link recheck must be direct fetches only, and any snippet fallback or fetch-impossible case (bot-block/JS site) yields Link Status `❓ Unverified`, never ✅; Verification Step #6 search reconstruction explicitly scoped to JD content only, zero liveness (failure: all 3 shortlisted roles on 2026-07-10 were presented "verified live" off crawl caches and were stale on same-day manual check). (3) **Session-resume provenance:** the WebFetch provenance gate doesn't persist across resumptions, so after any session break/resume every previously staged shortlist URL is unverified — re-establish provenance (search, then fetch the result link) before presenting, or void the entry (basis already in the Migration Delta Log, incl. the 2026-07-10 addendum — no delta action). (4) **Output format:** shortlist-table URLs render as clickable markdown links in chat, never bare text; the Notion Job URL property stays raw.
- **2.6.0** (2026-07-10) — Two fixes from the 2026-07-10 AM scan follow-up conversation. (1) New `Unverified/Blocked` Reason Passed option on the Passed/Seen Log (schema patched via `notion-update-data-source`): previously a lead that survived retry + search fallback (Verification Step #6) but still couldn't be evaluated had no home in the schema and simply vanished uncounted — confirmed cost: SysMap Solutions Senior Scrum Master 403'd on Remote Rocketship on a prior AM scan, was never logged, and got re-discovered and re-403'd on the next AM scan before search finally resolved it. Verification Step #6 and Real-Time Dedup Logging now both instruct logging fully-blocked leads under this reason so they're suppressed on future scans; flip to the real reason if a later scan resolves them. (2) Migration Delta Log's "cheap by design" rule — which let a scan skip the page based on its own judgment of whether anything friction-worthy happened — replaced with a mandatory end-of-run assessment: every scan compiles an explicit friction list from what actually happened, and only skips the page fetch if that list is genuinely empty. Root cause: the 2026-07-10 AM scan judged from memory that nothing new needed logging, missed two escalations (PROVENANCE_REQUIRED hitting new platforms, a second Lever bot-block company) and one resolution (SysMap), and only caught it because Borjan asked directly rather than the process catching it on its own.
- **2.5.1** (2026-07-09) — Duplicate-page race fix. Two concurrent sessions (the AM-run follow-up chat and the PM-run session) each followed "create the Migration Delta page once if missing" and, blind to each other mid-flight, created two pages with the same title. Fixed by merging the duplicate's 6 entries into the canonical page (4 as dated addenda, 2 as new entries, plus the race itself logged as a delta entry) and retiring the duplicate. SKILL.md now pins the page IDs for both singleton pages — Migration Delta `398054b0-88af-8158-9cae-e1d7c44eb48b` and Job Scout Runs `398054b0-88af-81b7-8670-fef8aad15254` — with a never-create-by-title rule: fetch by pinned ID, fall back to title search, create only if both miss, and report the new ID for pinning.
- **2.5.0** (2026-07-09) — Claude Code Migration Delta Log. New section + Notion page ("Claude Code Migration Delta", same parent as Job Scout Runs): every scan logs Cowork-environment frictions that code could fix — fetch permission gates, robots/JS-render blocks, lossy extraction, search caps, MCP timeouts, sandbox network limits, missing LinkedIn auth — as dated entries with impact + code-side fix, so the planned v3.0.0 Claude Code migration starts with a concrete improvement work-list instead of re-discovering pain points. New-frictions-only (escalations get dated addenda), page fetched only when a run actually hits something, `Δ+N` marker on the run digest line. Seeded at creation with all frictions known to date.
- **2.4.2** (2026-07-09) — Closed a silent-drop gap on `WebFetch` failures. The 2026-07-09 PM scheduled scan hit repeated `PROVENANCE_REQUIRED` errors (WebFetch's same-turn approval prompt, which nobody is there to answer in Unattended Mode) plus some robots.txt blocks and boilerplate-only fetches; roles that couldn't be fetched were dropped as insufficient-data even though at least one (Bystadium) was plausibly a real, verifiable candidate. New Verification Step #6: on any fetch failure (`PROVENANCE_REQUIRED`, robots block, or a "successful" fetch that returns generic site chrome instead of the JD), retry once, then fall back to `web_search` to reconstruct the JD from mirrors before marking a role unverified. New Unattended Mode point 10 makes explicit that isolated blocked fetches are expected in this mode and must NOT be logged under the digest's `sources down` — that's reserved for a platform being unreachable entirely.
- **2.4.1** (2026-07-09) — Closed a silent-write gap: an AM scheduled scan called `notion-create-pages` for 27 rows (4 shortlist + 23 drops) without a `parent` field. The API accepted it without error and created 27 blank standalone pages instead of database rows — every property beyond title was silently dropped, so Borjan's `New — Unreviewed` view showed 0 despite a "successful" write. Fixed that session via `notion-move-pages` + re-applied `update_properties`. Real-Time Dedup Logging section now mandates `parent: {"type": "data_source_id", ...}` on every `notion-create-pages` call to either log, plus a post-write spot-check (`notion-fetch` or re-query by Reason Passed/Status) before treating a batch write as verified.
- **2.4.0** (2026-07-09) — Unattended / Scheduled Mode for Cowork remote scheduled tasks (2x/day, laptop-off). New section defines the behavior deltas: no questions (conservative resolution + `❓ NEEDS BORJAN:` flags), no Gemini offer, Notion-as-inbox delivery (new candidates → Passed/Seen Log as `New — Unreviewed` with role notes in page body; new select option added), a one-line-per-run digest on a "Job Scout Runs" Notion page, source-down honesty in the digest, AM/PM split rotation with per-day completeness (scheduled runs only; interactive scans unchanged), best-effort LinkedIn snippet pass, and minimal chat output. Systematic LinkedIn coverage remains shelved with the v3.0.0 Claude Code spec.
- **2.3.0** (2026-07-09) — Closed a dedup gap: scans only cross-checked the Passed/Seen Log, not the Job Applications Tracker, so an already-applied role could be re-shortlisted as if new. Confirmed miss: the Skopje-tagged Andersen Delivery Manager req (applied 2026-07-04) was re-surfaced on the 2026-07-09 scan. Token-Efficiency Protocol #6 now caches the Applications Tracker alongside the Passed/Seen Log at scan start; new mandatory Applications Tracker cross-check (match by Job URL first, then Company+Role+location/client) runs before every shortlist, silently dropping any role already logged "Applied" regardless of fit score.
- **2.2.0** (2026-07-08) — Two final efficiency patches: (1) Bulk dedup pre-fetch — one Passed/Seen Log query (LIMIT 100, recent-first) at scan start, cached in context; per-candidate dedup checks run against the cache instead of individual Notion reads. (2) Project-files guard — scans never open `/mnt/project/` files; CV/cover letter/review/articles are pitch-time-only material. Remaining known improvements are data-gated, not editorial: tier recompute (5 logged scans), keyword promote/demote review (cluster-era Keyword Source data), skill eval benchmarking (real scan runs). Bash-based batch link checking investigated and rejected — job board domains are outside this environment's network allowlist.
- **2.1.0** (2026-07-08) — Recall fix on the 2.0.0 keyword clusters after Borjan flagged the trade-off: OR-batching a high-volume term with niche terms lets the generic term crowd all ~10 result slots, burying the niche variants. Redesigned clusters: generic terms (project manager, delivery manager, scrum master, program manager) run alone and rely on substring matching for their title variants; only similar-low-volume niche terms share an OR. Added a mandatory saturation escape hatch: a ≈10/10-relevant results page triggers one dedicated follow-up query for buried variant terms on that platform. Net query count unchanged (5/platform) with recall protected.
- **2.0.0** (2026-07-08) — Fable-assisted restructure for Sonnet token efficiency; no rules dropped, only compressed and reorganized. (1) Progressive disclosure: pitch/voice/Q&A rules → `references/pitching.md`; Gemini prompt → `references/gemini-prompt.md`; scans no longer load ~190 lines they never use. (2) New Token-Efficiency Protocol: OR-batched keyword clusters (5 queries/platform instead of up to 19), snippet-first triage, cheap liveness rechecks via `text_content_token_limit≈400` (full JD fetched once per role), batched same-turn Notion writes, minimal scan narration. (3) Keyword Source attribution updated for clusters: record the title variant on the posting, not the literal query. (4) All 1.x "confirmed example" narratives compressed to rule + parenthetical. Deferred to a future data-driven run: tier recompute (needs 5 logged scans) and keyword promote/demote review (needs Keyword Source data).
- **1.9.0** (2026-07-08) — Five scan-session fixes: real-time dedup logging; Country-Clone Posting Pattern (Spiralyze); mirror liveness ≠ source liveness (Superside); timezone snippet-blindness (Spiralyze 3pm EST); "location-fluid" copy ≠ worldwide (Moro Tech).
- **1.8.0** (2026-07-08) — Measured full Tier 1+2 keyword hit rates; promoted 6 title variants to core, left 6 in expanded; added Keyword Source field to both Notion logs as the promote/demote dataset.
- **1.6.0** (2026-07-07) — Added 14 Borjan-approved title variants to the keyword set.
- **1.5.0** (2026-07-07) — Tiered execution order (Tier 1/2/3) by hit rate; revisit trigger at 5 logged scans.
- **1.4.0** (2026-07-07) — Otta merged into WttJ; Remote Rocketship per-job bot-block; Pinpoint HQ JS-render documented in-file; undated NoDesk listings = unverified-by-default; Greenhouse `.eu.` fetches identically.
- **1.3.0** (2026-07-07) — Stale Platform Demotion Rule; applied to EuropeRemotely.
- **1.2.0** (2026-07-07) — Dedup key strengthened to Company+Title+location/domain; within-scan mirror check; Platform select pre-check.
- **1.1.0** (2026-07-07) — Added metadata block, Files section, Changelog; hardened Passed/Seen Log with direct DB IDs.
- **1.0.0** — Baseline: profile, hard filters, 20-platform rotation, scoring, Tracker logging, pitch rules, strategy notes.
