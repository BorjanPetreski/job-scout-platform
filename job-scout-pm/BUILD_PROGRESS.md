# BUILD_PROGRESS — job-scout-pm v3.0.0 (spec r2, 2026-07-11)

> Read this FIRST on any session start/resume. Continue from state below; never redo ✅ steps.
> Delete this file only after ALL acceptance criteria (§9) pass. Not shipped in the skill zip.

## Blocker

❗ **v2.10.0 skill source (SKILL.md + references/pitching.md + references/gemini-prompt.md) is NOT available** — not in repo, uploads, or Notion (searched 2026-07-11). Borjan must upload the v2.10.0 skill zip. Blocks: SKILL.md v3 rewrite (step 9), CHANGELOG 1.0.0→2.10.0 history (step 10), config keywords/hard-filter fine print (partially mitigated: spec §1 enumerates all 13 filters + numbers). Everything else proceeds from spec r2.

## Build order (spec §9)

| # | Step | Status | State / findings |
|---|------|--------|------------------|
| 1 | BUILD_PROGRESS.md | ✅ done | This file. Repo layout created under `job-scout-pm/` (subdir of job-scout-platform repo). |
| 2 | config.yaml | ✅ done | Full 23-platform registry, tiers, caps, filters-as-data, Notion IDs. Live-verified: Remotive + Working Nomads APIs up. Schemas verified: Passed/Seen platform option is "Welcome to the Jungle" (config fixed); Tracker select missing MANY options (not just Pinpoint/Deel/Crossover) → generic select pre-check required. Keywords/rejected-reasons carry TODO(v2.10.0 port) markers. |
| 3 | dedup.py (+ Notion backfill) | ✅ done | 203 rows backfilled via Notion MCP (188 Passed/Seen + 15 Tracker) into state/seen.jsonl; last-wins append semantics; URL-exact + 3-part-key match verified incl. Andersen both-log case. |
| 4 | check_links.py | ✅ done | Live ✅ / stale ❌ (410) verified against real Remotive postings; 403-class → headless retry; evidence rows land in fetch_evidence.jsonl. RR per-job 403s even headless → unverifiable_direct (honest). Positive app-shell→rendered-live demo pending a fresh JS posting (do during step 6). |
| 5 | render.py (headless wrapper) | ✅ done | API surface = render/render_many only (ban structural). IMPORTANT env finding: agent proxy resets Chromium TLS 1.3 ClientHello → when HTTPS_PROXY set, wrapper passes --ssl-version-max=tls1.2 + proxy launch arg (lossless; proxy re-terminates TLS). Chromium at /opt/pw-browsers/chromium via executable_path. NoDesk/Crossover/Landing.jobs all render. |
| 6 | fetch_boards.py | ✅ done | All endpoints live-verified 2026-07-11. Wins: Himalayas /jobs/api (new, replaces 403'd HTML), Deel careers-page embedded JSON (Ashby API disabled by Deel), JJ.it by-cursor endpoint (`from` param, cat 15 = PM, 831 offers). Degraded (report source_down honestly): Remotive (API stub regression, post-delta), Remote Rocketship (Cloudflare 403s lists+sitemap even headless), JustRemote (lazy-load), WttJ (Algolia/consent-gated). Harvest specs per platform w/ anchor-text titles. |
| 7 | linkedin_tripwire.py | ✅ done | Guest endpoint live; 46-52 cards from 6 requests (caps: ≤10 req, ≥3s); title/company/loc/date parsed; 429/999 immediate stop coded. |
| 8 | scan.py | ✅ done | First full rotation: 5m55s, 210 candidates (first-run backlog), 17 auto-drops + 1 link-dead logged, ledger printed, runs.json + recompute counter. Seeded dedup proof passed (Andersen applied + OSF passed both suppressed). Fixed: degenerate empty-company dedup keys; read cap → 60. NOTE: unscored candidates re-emit on re-run BY DESIGN (crash resilience); "zero dupes on re-run" holds once the session logs decisions — drops/link-dead/unverified_blocked are suppressed immediately. |
| 9 | notion_sync.py | ✅ done (REST path untested-live) | Typed wrapper (hard-coded data_source parent + post-write assertion; parentless write raises), generic select pre-check, backoff, digest append w/ anti-race, --applied Tracker flow gated on status=applied. No NOTION_TOKEN in env → tokenless path exports state/notion_pending.json for MCP push (exercised: 18 real rows pushed via MCP to Passed/Seen, digest line appended to Runs page, 📥 "New — Unreviewed" review view created on the DB). ❗ REST path needs NOTION_TOKEN to be verified + required for unattended runs. |
| 10 | SKILL.md v3 rewrite | 🚫 blocked | Needs v2.10.0 SKILL.md upload. |
| 11 | CHANGELOG.md | 🚫 blocked (3.0.0 entry can be drafted) | Needs v2.10.0 changelog history. |

## Open questions (spec §10) — defaults adopted, Borjan may override

1. NOTION_TOKEN: not present in build env → notion_sync.py takes token via env, MCP fallback documented. **Needs token for unattended runs.**
2. Full rotation per run: **adopted** (spec r2 default).
3. Host OS: unknown → both Desktop-task and cron instructions shipped.
4. LinkedIn locations: "European Union" + "Worldwide" (N. Macedonia third slot left as config comment).
5. Weekly full sweep: Monday (default).
6. 2x/day schedule: adopted as documented default.
7. Delta Log closure entry: deferred to acceptance (§9 crit. 9) — needs Borjan sign-off anyway.

## Environment notes (build session, 2026-07-11)

- Build runs in Claude Code remote session, repo `borjanpetreski/job-scout-platform`, branch `claude/job-scout-pm-migration-ypek3r`.
- Outbound HTTPS via agent proxy (CA bundle /root/.ccr/ca-bundle.crt) — live-fetch tests must set `REQUESTS_CA_BUNDLE` if TLS errors appear; never disable verification.
- Python 3.11.15; requests + PyYAML present; selectolax/playwright to install.
