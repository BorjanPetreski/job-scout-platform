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

## 1.0.0 → 2.10.0

> TODO(v2.10.0 port): full history migrates here verbatim from the v2.10.0
> SKILL.md changelog once the skill source is provided. Do not reconstruct from
> memory — insufficient data beats hallucination.
