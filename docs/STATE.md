# STATE — session dashboard (read this, not PROGRESS, at session start)

> **The single source of truth for CURRENT build state.** Injected automatically into
> every session by `.claude/hooks/session-start.sh`. Small on purpose — if a section
> needs more than a few lines, it points at the doc that owns the detail.
> **History lives in [PROGRESS.md](PROGRESS.md)** (append-only log + per-phase
> checklists); never duplicate narrative here.
>
> **Update contract:** rewritten at every session end (CLAUDE.md DoD #2) — flip *Now /
> Next / Open threads* to match reality, refresh *Last updated*. The Stop hook nudges
> when a branch changes files but not this one. A stale STATE.md is a bug: fix it first,
> before any new work.

**Last updated:** 2026-07-24 · session-lifecycle restructure (this file created; see the
2026-07-24 PROGRESS row). Build state itself reflects main @ 2026-07-21 (PR #69) —
sources: PROGRESS checklists + session log, PHASE_3A_ACCEPTANCE, PHASE_3_HEALTH_PLAN,
HEALTH_LOG, PRs #65–#69. Confirm the two ⚑ flags below, then delete them.

## Now (active lane)

**Phase-3 interstitial — Platform Health & Self-Healing + board audits** (Borjan:
"fully build this before continuing with 3b"). The health layers are shipped
(telemetry contract, `core/health.py` Layer 1, bounded Layer-1.5 in-scan self-healing,
`HEALTH_LOG.md` capture loop, `health_review_due` + `arch_review` counters); the lane
now runs **manual board audits** under HEALTH_LOG "How a review works", including the
step-5 generalize-every-fix rule (2026-07-21).

## Next actions

1. **Remote Rocketship follow-up** — `/publicjobs/` regression + the query-string
   search surface (`?page=&sort=&jobTitle=`) were **scoped, no code yet** (PR #68).
   Decide: wire the query-search surface or park it; fix the regression either way.
2. Continue board audits per the HEALTH_LOG protocol as scan nudges fire.
3. When the health lane settles → **Phase 3b planning** (interview lifecycle):
   brainstorm → plan → review gate → build, per PROGRESS Phase-3 staging.

## Phase status

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | Documentation set | ✅ merged (PR #8) |
| 1 | Core engine extraction + parity + sweep | ✅ cutover 2026-07-14; legacy `job-scout-pm/` frozen ⚑¹ |
| 2 | Template library + setup interview + Notion provisioning | ✅ complete 2026-07-17 (2.1–2.12) |
| 3a | Companion: voice + KB + apply loop | ✅ **COMPLETE 2026-07-19** — 3a.0–3a.10 done; borjan-pm live loop passed; **ani portability passed 2026-07-19** ⚑² |
| 3-health | Platform Health & Self-Healing (interstitial) | 🟡 built; **board-audit lane active** (see Now) |
| 3b | Interview lifecycle | ⬜ vision-captured — next major |
| 3c | CV doctor + writing coach | ⬜ vision-captured |
| 4 | Setup/companion FE app (Agent SDK) | ⬜ not started |

⚑¹ PROGRESS's old phase table still said "cutover pending" — this row is corrected from
the newer README + frozen archive; confirm 1.12 fully closed and clear this flag.
⚑² PROGRESS checklist row 3a.7 carried a stale "ani: not yet run" note (fixed in the
restructure); the 3a stage table + 2026-07-19 session rows are the truth designation.

## Open threads (unconfirmed / deferred / pending Borjan)

- **Deferred 3a confirmation:** companion drafts → creates a NEW Tracker row → next
  scan back-fills it. Proven by sim, not yet live (no eligible role at UAT time) —
  confirms itself on the first real apply; flip to closed when observed.
- **NOTION_TOKEN rotation** — flagged 2026-07-13 (token appeared in chat); no closure
  recorded anywhere. Confirm rotated, then delete this line.
- **arch_review counter** (added 2026-07-21, `due_at_sessions=10`) — when the scan
  ledger prints the nudge, assess per CLAUDE.md DoD #5; `core/arch_review.py --ack`
  after a pass.

## Standing constraints (full text lives where cited)

- **Prime directive:** `borjan-pm` is Borjan's live daily job search and is sacred —
  never regress its behavior, state, history, or Notion (PHASE_2_PLAN §0a). Frozen
  `job-scout-pm/` archive stays intact as the parity anchor. Gate: `core/validate.py`
  + `tests/run_all.py` green.
- **Data & privacy principle:** client-side is the destination; Claude is the engine,
  not the vault; no mining; deletable; no PII in the repo (PROJECT_PLAN §1a).
- **Notion is the only scanner↔companion bridge**; the scanner never writes the
  Applications Tracker (ARCHITECTURE §5).
