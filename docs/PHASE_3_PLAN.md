# Phase 3 Execution Plan — Application Assistant (Claude Project + Notion MCP)

> The detailed build plan for Phase 3, produced from a design brainstorm and written to be
> **executed by a build agent in a later session** (the next session picks up here — see
> PROGRESS.md). Companion to [PROJECT_PLAN.md](PROJECT_PLAN.md) §Phase 3 (scope),
> [ARCHITECTURE.md](ARCHITECTURE.md) §5 (the Notion contract + write-ownership invariant), and
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md) (schema/profile facts the composer reads).
> This document is the plan of record for the Phase 3 build; where it refines the earlier
> drafts, it wins, and the build should update those docs to match as it goes.
>
> Status: **ready for the 3.0 review gate** · Created: 2026-07-17 · Brainstorm: Opus 4.8 ·
> Review gate: Fable 5 (planned, step 3.0) · Build: Opus 4.8 (§12.2)

---

## 0. What Phase 3 is (one paragraph)

Split the "help me apply" half out of the scanner entirely. The scanner ends at a Notion
shortlist; the **Application Assistant** starts from it. The assistant is a **claude.ai Claude
Project + the Notion MCP connector** — not repo code. It reads a profile's `📥 New — Unreviewed`
shortlist from the Passed/Seen Log, walks the roles one at a time at the user's pace, re-verifies
each posting's key facts, drafts application materials (cover letters, email pitches, form answers)
**in the user's voice** from data held in the Project (CV, cover-letter bank, articles, past
answers), and **records applications** — creating the Applications Tracker row and resolving the
shortlist row. The load-bearing property: **Notion is the only shared surface between the scanner
and the assistant; neither ever reads the other's local state.** Because the assistant lives on
claude.ai it cannot read repo files or run `core/*.py` at runtime, so its entire persistence layer
is Notion, and Phase 3 needs almost no core-engine change — it is a claude.ai-side instruction
package plus one small deterministic composer. First real test: a full supervised loop on Borjan's
live `borjan-pm` shortlist (production use, not a regression), with a portability proof on Ani's
`ani-backend-java`.

## 0a. Prime directive — the scanner and `borjan-pm` stay untouched; the Tracker firewall is sacred

**Phases 1–2 shipped a scanner Borjan uses daily. Phase 3 must not touch it.** This is the top
constraint; it outranks any Phase 3 convenience.

- **The scanner is not modified in behavior.** The Application Assistant is a new, separate
  claude.ai-side app. The only repo code Phase 3 adds is a build-time composer (`core/compose_assistant.py`)
  plus a small, guarded scanner-side *reconciliation* (§5) — neither changes what a scan fetches,
  filters, scores, or writes. `borjan-pm` validates and scans identically before and after Phase 3.
- **The Tracker firewall is sacred (ARCHITECTURE §5 invariant, verbatim from v2.7.0).** The scanner
  **never** writes the Applications Tracker, in any mode. Phase 3 does not add a scanner Tracker
  write path and does not weaken the existing block. The assistant writes the Tracker via Notion MCP;
  the Claude Code "I applied" chat flow keeps writing it via `notion_sync.py`. The scanner stays out.
- **State/history is untouchable.** `profiles/<id>/state/` (seen.jsonl, runs, evidence, JD cache) is
  never regenerated, migrated destructively, or reset by any Phase 3 work. The assistant never writes
  it at all (it has no repo access); the scanner's reconciliation (§5) is additive and idempotent.
- **CV/PII never enters the repo (Phase 2 D4, carried forward).** The Project holds all person-secrets
  (CV, voice, past answers). The repo holds only search config and scan state. The single repo↔Project
  crossing is build-time, one-directional (repo config → Project instructions), and carries no PII.
- **Borjan is user #1, forever.** His profile, state, Notion, and now his Application-Assistant
  binding are carried in verbatim when the app arrives (Phase 4/5). Nothing here assumes a fresh start.

If any Phase 3 change would force a regression here, the change is wrong — find the additive path instead.

## 1. Decisions locked in the brainstorm (the design contract)

These are settled. Do not re-litigate; implement.

| # | Decision |
|---|----------|
| D1 | **Notion is the sole scanner↔assistant bridge.** Neither app reads the other's local state. The scanner lives in the repo; the assistant lives on claude.ai and reaches profile data **only via Notion** (Phase 2 D4 made concrete). The assistant reads `📥 New — Unreviewed` and writes the Tracker + Passed/Seen transitions; the scanner reads both DBs at scan start (as it already does for dedup) and reconciles its own state. **The Tracker row is the cross-process message** (D7). |
| D2 | **`assistant/` is a profile-agnostic instruction package + setup guide** — an engine-level artifact, sibling to `skills/job-scout-run/`, holding generic apply *doctrine* and the claude.ai-Project setup guide. Modular: a core instruction file plus reference modules (mirrors how a profile keeps `references/`). It is **not** person-specific and **not** repo-executable code. |
| D3 | **`pitching.md` splits along the Phase-1 engine/profile seam.** Generic apply doctrine (copy-block delivery, gap-honesty procedure, salary-ask *structure*, employment-type closing-gate *logic*, "no invented experience", re-verify-before-draft) moves **up** into `assistant/`. The profile-specific residue (the person's actual writing voice, source-doc priority + conflict rule, the Gemini-not-ChatGPT correction, the B2B/visa *mechanism*, profile links, domains) stays **down** in `profiles/<id>/assistant/voice.md`. Same move as splitting `config.yaml`/`SKILL.md`. |
| D4 | **The Project is configured by a build-time composed SNAPSHOT, not runtime repo reads.** `core/compose_assistant.py` reads `profile.yaml` + `profiles/<id>/assistant/voice.md` + the generic `assistant/` package + the profile's Notion `data_source_id`s, and emits `profiles/<id>/assistant/project-instructions.md` for the user to paste into the claude.ai Project. Profile facts (floor for the salary-ask safety check, eligibility for the B2B gate, Notion IDs to target the right DBs) reach the assistant this way **without a live repo read**. Re-run the composer when the profile changes materially (re-bind). Deterministic + scriptable (Phase 4 constraint). |
| D5 | **Strict data boundary (Phase 2 D4, restated and locked for the assistant).** **Project holds**: CV, cover-letter bank, articles, past answers, the profile voice guide, the composed instruction snapshot — all PII/voice, uploaded by the user. **Repo holds**: config (profile.yaml, templates, catalog) + scan state. **Bridge is Notion only** at runtime. The one crossing is the D4 build-time composition: repo config → Project instructions, one-directional, no PII (PII originates in the Project and never flows to the repo). |
| D6 | **Write-ownership partitions by row STATE, not by row.** The scanner writes a Passed/Seen row only while it is `New — Unreviewed` (creation) or flips it → `Stale/Expired` (staleness). The assistant writes only the *transitions out* of `New — Unreviewed` (→ `User Declined` + reason, or → `Applied`-adjacent) plus Tracker row creation. Dedup guarantees the scanner never re-touches a resolved row, so the two apps physically cannot collide on a transition. This makes ARCHITECTURE §5's "scanner owns creation + staleness; human-driven flows own progression" mechanical. |
| D7 | **The cross-process handoff IS the Notion Tracker row.** The assistant creates an `Applied` Tracker row via Notion MCP → the next scan reads the Tracker at start → matches by URL / 3-part key → **hard-silent-drops** the role (existing dedup rule) → reconciles `seen.jsonl` (scanner-side, §5). The assistant never writes `seen.jsonl`. The scanner owns all local-state reconciliation. |
| D8 | **The assistant is the primary/canonical scanner-external Tracker writer; the Claude Code "I applied" chat flow persists as a fallback.** Off-session applies (you applied on your phone, or in a Claude Code chat) still log via `notion_sync.py --applied`. Both paths are idempotent-by-URL, so a role logged by one is deduped by the other. The scanner remains a **non**-writer of the Tracker either way (prime directive). |
| D9 | **The per-role apply loop (§6):** read `📥 New — Unreviewed` → per role, user-paced, one at a time: present the role + surface prior history → **re-verify key facts** (D10) → decide apply/pass with the user → on apply, draft materials in voice (copy-blocks) → on "applied", create the Tracker row + flip the Passed/Seen row; on "pass", flip → `User Declined` + the real reason. The user drives the pace; the assistant never batch-applies. |
| D10 | **Re-verification is mandatory before drafting — fetch-first with an honest paste/confirm fallback.** The assistant **fetches the posting URL itself** (claude.ai web) and re-checks the hard facts against the profile's constraints (still live; location/eligibility; working hours; salary; employment type — mirrors the `gemini-prompt.md` verification block). When the fetch comes back **JS-walled, login-walled, or thin** (the LinkedIn-walled-Java-leads pattern is real in the logs), it falls back to asking the user to paste or confirm — the scanner's "unverifiable → flag, don't retire" honesty applied at apply-time. Never draft against an unverified posting silently. |
| D11 | **The assistant may set `Stale/Expired` on an observed-dead posting.** `Stale/Expired` is a shared terminal state neither app resurrects, so when the assistant directly observes a dead posting at verify time it flips the Passed/Seen row → `Stale/Expired` with a dated note (matches reality, avoids a wasted next-sweep cycle). This is a narrow, well-defined extension of ARCHITECTURE §5's "sweep owns staleness": the sweep remains the *proactive* staleness engine; the assistant records staleness it *directly witnesses* on a row it is already resolving. |
| D12 | **Profile↔Project binding is recorded in `profiles/<id>/assistant/`.** One profile = one claude.ai Project. The repo holds `voice.md` (profile voice/pitch params), `data-manifest.md` (what to upload to the Project), and the generated `project-instructions.md` (the composed snapshot). The Project itself lives on claude.ai; the repo holds the **recipe to (re)build it**, and the binding is documented by the composed instructions naming the profile's specific Notion `data_source_id`s. |
| D13 | **Voice fidelity is first-draft discipline, generalized.** The generic package carries the rule "apply the profile's voice on the **first** draft (not as a correction after the user flags it); re-read the voice guide + the relevant source doc before drafting." The profile's `voice.md` carries the actual voice signature. The AI-tell avoidance (no em-dash stacking, no "delve/testament/moreover", no generic openers) is generic doctrine in `assistant/`; the specific cadence ("stacked sentences joined by semicolons", "I've found that…") is profile data. |
| D14 | **Acceptance = `borjan-pm` primary + `ani-backend-java` portability proof.** Primary: a real, supervised full loop on Borjan's live `📥 New — Unreviewed` roles under his Notion — this is **production use, not a regression** (Borjan applies to jobs today; the assistant is how he'll do it). It exercises the richest voice material (`pitching.md`, CV, cover-letter bank, articles), the B2B/visa closing gate, and the salary-ask against his real floor. Proof: a dry composed binding + coherent apply loop on Ani's backend-java shortlist, showing the package is genuinely profile-parameterized, not Borjan-shaped (mirrors Phase 2's backend-java portability proof). |
| D15 | **The scanner-side reconciliation is small, additive, and idempotent (§5).** On reading the Tracker at scan start, a `Applied`-status match with no local `applied` record back-fills `seen.jsonl` (`status: applied`); the sweep already skips rows no longer `New — Unreviewed` in Notion (so assistant-resolved rows drop out of the sweep scope automatically). Phase 3 verifies/tightens this so no engine behavior changes and no assistant write is required for correctness. |
| D16 | **The Gemini cross-check stays scanner-side.** `gemini-prompt.md` is a scan-time broad-crawl augmentation offered post-scan by the run skill — it is **out of assistant scope** and stays with the profile/run-skill unchanged. The assistant is apply-side only. |

## 2. The `assistant/` package shape (D2)

An engine-level, profile-agnostic package — sibling to `skills/job-scout-run/`. It is **instructions
and a setup guide, not executable code.** Proposed structure:

```
assistant/
├── README.md                  # setup guide: create the claude.ai Project, paste the composed
│                              #   instructions, upload data per the manifest, connect Notion MCP,
│                              #   verify with a probe read of 📥 New — Unreviewed
├── instructions/
│   ├── core.md                # the apply-loop spec (§6): read queue → per-role verify → draft → record
│   ├── notion-contract.md     # the write-ownership contract (§5) from the assistant's side:
│   │                          #   which statuses it may write, on which transitions, and the firewall
│   ├── verification.md        # D10 re-verify procedure (fetch-first + paste/confirm fallback)
│   ├── voice-discipline.md    # D13 generic voice doctrine + AI-tell avoidance + copy-block delivery
│   ├── answers.md             # generic gap-honesty procedure, salary-ask STRUCTURE, common form-Q types,
│   │                          #   employment-type closing-gate LOGIC (all profile-agnostic)
│   └── data-model.md          # how the Project's uploaded docs are used (source-doc priority PATTERN,
│                              #   conflict-rule PATTERN — the profile's manifest fills in the specifics)
└── COMPOSED.md                # generated-artifact NOTE: the per-profile composed instructions live at
                               #   profiles/<id>/assistant/project-instructions.md (built by the composer)
```

The composer (D4) concatenates the generic `instructions/*.md` with the profile's `voice.md` and a
small facts snapshot (floor, eligibility, Notion IDs) into one `project-instructions.md`. Whether the
user pastes one composed file or uploads the modules separately is a build-detail for 3.5; the source
of truth is modular so the generic doctrine stays legible and reusable across profiles.

## 3. The `pitching.md` split (D3) — engine/profile seam

`profiles/borjan-pm/references/pitching.md` is the battle-tested source. It splits like `config.yaml`/
`SKILL.md` did — **generic doctrine up, profile residue down** — and, like the Phase-1 extraction, it
is done as a **diffable extraction**: every line of today's `pitching.md` lands in exactly one of the
two destinations, nothing invented, nothing dropped.

| Stays generic → `assistant/instructions/` | Becomes profile data → `profiles/<id>/assistant/voice.md` |
|---|---|
| Copy-block delivery format (triple-backtick, mobile one-tap, first-response, even a single URL) | The actual writing voice (stacked sentences + semicolons, "I've found that…", plain technique-naming, imperfect rhythm, warm-plain close) |
| Gap-honesty / screening-question procedure (the 4 steps) | Canonical source-doc list + priority + conflict rule (CV / Quarterly Review / Cover Letter …) |
| Salary-ask heuristic **structure** (anchor-to-top / market+10–15% / basis matches listing / one number) | The Gemini-not-ChatGPT terminology correction (a per-profile tooling fact) |
| Employment-type **closing-gate logic** (freelance→work in the contractor advantage; full-time→plain close; unclear→ask once) | The B2B/visa **mechanism** (no EU visa → sole-proprietor bypass) — *the reason* the gate resolves the way it does for this person |
| "No invented experience / flag the gap" doctrine | Profile links (GitHub/LinkedIn) delivered verbatim in copy-blocks |
| Re-verify-before-draft + first-draft-voice discipline (D13) | Domains + past-answer talking points specific to the person |

The salary-ask *safety check* ("never below the floor") is generic **logic**, but the floor *value*
comes from `profile.yaml` via the composer (D4) — so the generic doctrine references "the profile's
floor" and the composed snapshot supplies the number. Same for the B2B gate: the generic logic asks
"does the profile's eligibility include b2b_contractor?", the snapshot answers it.

`gemini-prompt.md` is **not** split — it stays a scanner-side reference (D16), untouched.

## 4. The binding + composer (D4, D12)

**`core/compose_assistant.py` (NEW, the only substantial Phase 3 core code).** Inputs: `--profile <id>`.
Reads `profile.yaml`, `profiles/<id>/assistant/voice.md`, and the generic `assistant/instructions/*.md`.
Emits `profiles/<id>/assistant/project-instructions.md`: the generic doctrine + the profile voice + a
**minimal facts snapshot** — `compensation.floor` (or "unset → judgment-time estimation"),
`candidate.eligibility` (drives the B2B gate), `candidate.location`/timezone (drives verification),
`search.employment_type`, and the Notion `output.notion.tracker` / `passed_seen` `data_source_id`s so
the assistant queries and writes the **right** DBs.

- **No PII in the output.** The composer emits config facts only; CV/voice-material stays in the
  Project as uploaded files. (The profile's `voice.md` is voice *guidance*, authored by/with the user
  and safe to live in the repo — it names cadence and rules, not CV contents. The 3.7 CI check enforces
  no PII-shaped content lands in `voice.md` or the composed output.)
- **Deterministic + idempotent.** Re-running regenerates `project-instructions.md` byte-stably from
  unchanged inputs; re-bind = re-run after a profile/voice/Notion change. Scriptable so the Phase 4 app
  renders "set up your Application Assistant" as a button over this exact composer.
- **The Project is not in the repo.** The repo holds the *recipe* (`voice.md` + `data-manifest.md` +
  generated `project-instructions.md`); the claude.ai Project is built once from it by following
  `assistant/README.md`. Binding is recorded by the composed instructions naming the profile's Notion IDs.

## 5. Notion contract — status transitions + write-ownership (operationalized D6/D7/D11/D15)

This section formalizes ARCHITECTURE §5 into the exact transitions each app may write. **This is the
firewall.**

**Passed/Seen Log** (per profile):

| Transition | Writer | When |
|---|---|---|
| _create_ → `New — Unreviewed` | **Scanner only** | shortlist emit |
| `New — Unreviewed` → `Stale/Expired` | **Scanner sweep** (proactive) **or Assistant** (on directly observed death, D11) | staleness |
| `New — Unreviewed` → `User Declined` (+ real reason) | **Assistant** (primary) / Claude Code chat flow (fallback) | user passes |
| `New — Unreviewed` → resolved on apply | **Assistant** (flip out of the queue) | user applied |

**Applications Tracker** (per profile):

| Transition | Writer | When |
|---|---|---|
| _create_ → `Applied` | **Assistant** (primary, via Notion MCP) / Claude Code "I applied" chat flow (fallback, via `notion_sync.py`) | user applied |
| `Applied` → `Screening`/`Interview`/`Offer`/`Rejected`/`Withdrawn` | **Human-driven** (assistant updates if the user reports back, or the user edits Notion) | progression |
| _any_ | **NEVER the scanner** (firewall — invariant) | — |

**Runs page**: scanner digest only, unchanged. **The assistant never writes it.**

**Anti-collision guarantees:**
1. The scanner writes a Passed/Seen row only while it is `New — Unreviewed` (creation) or flips it to
   the terminal `Stale/Expired`; it never re-touches a row it or the sweep already resolved, and dedup
   hard-silent-drops any role already `User Declined`/`Applied`/`Stale/Expired`. So the scanner and the
   assistant never target the same transition on the same row.
2. Both Tracker write paths (D8) are **idempotent-by-URL** — a role already in the Tracker is not
   duplicated by the other path.
3. **Scanner-side reconciliation (D15, additive/idempotent):** at scan start the scanner reads the
   Tracker (it already does, for dedup); on an `Applied` match with no local `applied` record it
   back-fills `seen.jsonl` (`status: applied`). The sweep already scopes only rows still
   `New — Unreviewed` in Notion, so assistant-resolved rows fall out of the sweep automatically — no
   assistant `seen.jsonl` write is needed for correctness. Phase 3 **verifies** this holds and tightens
   only if a gap is found; it changes no fetch/filter/score behavior.

## 6. The per-role apply loop (D9/D10) — the assistant's core spec

Runs inside a claude.ai Project session, driven by the composed instructions. User-paced, one role at
a time; the assistant never batch-applies and never acts without the user in the loop.

1. **Read the queue.** Query the profile's `📥 New — Unreviewed` view (Passed/Seen Log) via Notion MCP.
   Present the list; let the user pick a role (or go top-down).
2. **Present + surface prior history.** Show the role + its role notes. If the company appears elsewhere
   in the Tracker/Passed-Seen (the scanner records `company_prior`), surface the prior reqs and their
   status so the user never asks "is this a variant of one I applied to?" (the run-skill's history rule,
   read here from Notion).
3. **Re-verify key facts (D10, mandatory).** Fetch the posting URL; re-check: still live; location /
   work-authorization / eligibility; core working-hours overlap; salary vs the profile floor;
   employment type. On a JS/login/thin wall, ask the user to paste or confirm. If dead → flip
   `Stale/Expired` (D11) with a dated note and move on. Never draft against an unverified posting.
4. **Decide apply/pass** with the user (the assistant advises; the user decides — the scanner's
   "scripts flag, Claude decides, user owns the call" doctrine, apply-side).
5. **Draft in voice (on apply).** Draft the needed materials — cover letter, hiring-manager email pitch,
   or form answers — applying the profile's voice on the **first** draft (D13), from Project data, with
   the gap-honesty procedure on every "do you have experience with X". Deliver every submittable text in
   a **copy-block**; analysis stays outside it.
6. **Record.** On "applied": create the `Applied` Tracker row (Source, Date Applied, Fit, Keyword
   Source, Notes) **and** flip the Passed/Seen row out of `New — Unreviewed`. On "pass": flip the
   Passed/Seen row → `User Declined` with the user's real reason verbatim.
7. **Next role** — return to the queue.

## 7. Data boundary (D5) — the wall, both directions

- **Project → repo: nothing.** CV, cover letters, articles, past answers, and voice material live only
  in the claude.ai Project. They never enter the repo, git, or any scan artifact. The scanner does not
  need them and cannot read them.
- **Repo → Project: config only, once, at build time.** The composer (D4) snapshots search config +
  Notion IDs into `project-instructions.md`. No scan state, no history, no PII. One-directional.
- **Runtime bridge: Notion only.** Everything the assistant reads about the shortlist and everything it
  writes about applications flows through the profile's Notion DBs. No live repo read, no `core/*.py`
  call from the assistant.
- **Consequence for correctness:** because the assistant cannot write `seen.jsonl`, the Tracker row is
  the *only* signal the scanner gets that a role was applied to via the assistant — which is exactly D7,
  and why the scanner-side reconciliation (D15) is where local state is kept honest.

## 8. Acceptance test (D14)

- **Primary — `borjan-pm`, real, supervised (production use).** Compose Borjan's binding; stand up his
  Application-Assistant Project (upload his CV / cover-letter bank / articles / past answers; connect
  Notion MCP). Run the full loop on **1–2 real `📥 New — Unreviewed` roles**: verify the assistant
  re-verifies facts, drafts in his voice (copy-blocks; B2B gate + salary-ask behaving), creates the
  `Applied` Tracker row, and flips the Passed/Seen row — **with Borjan watching every write.** Then run
  a scan and confirm the applied role is **hard-silent-dropped by dedup** and `seen.jsonl` reconciles
  (D7/D15). This is Borjan's real job search, done the new way — not a throwaway fixture.
- **Proof — `ani-backend-java`, portability.** Compose Ani's binding from her profile + a minimal
  `voice.md`; confirm the generic package produces a coherent, non-Borjan apply loop and a
  Java-appropriate draft on her real shortlist rows (voice material may be thin — the point is that the
  package is genuinely profile-parameterized, not that Ani applies). Mirrors Phase 2's backend-java proof.
- **Acceptance passes when:** the composer emits a valid PII-free binding for both profiles; a full
  loop records an application correctly to the right DBs for `borjan-pm`; the next scan dedups it; the
  scanner's fetch/filter/score behavior is unchanged (prime directive); and the Tracker firewall holds
  (no scanner Tracker write anywhere). Capture lessons into `assistant/` (generic), `voice.md` (profile),
  or the composer per the friction-logging culture.

## 9. Ordered build checklist (seed into PROGRESS.md Phase 3 table)

Ordered so the scanner and `borjan-pm` stay untouched at every step.

| # | Step | Notes |
|---|------|-------|
| 3.0 | **Pre-build review gate (Fable 5)** — one scoped adversarial review of this plan; amend for blocking findings (D1–D16 intact) before 3.1 | §12.1 |
| 3.1 | **`assistant/` generic package** — build `assistant/instructions/*.md` (core apply loop, notion-contract, verification, voice-discipline, answers, data-model) + `assistant/README.md` setup guide, by **extracting the generic doctrine from `pitching.md`** (diffable — every generic line lands here). | §2/§3, D2/D3/D6/D9/D10/D13 |
| 3.2 | **Profile-side split** — create `profiles/borjan-pm/assistant/voice.md` (the profile residue of `pitching.md`) + `data-manifest.md` (what to upload). `gemini-prompt.md` stays put (D16). Verify the split is loss-free vs today's `pitching.md`. | §3, D3/D12/D16 |
| 3.3 | **`core/compose_assistant.py`** — deterministic, idempotent composer: profile.yaml + voice.md + generic package + Notion IDs → `profiles/<id>/assistant/project-instructions.md`; **no PII** in output. | §4, D4/D12 |
| 3.4 | **Notion write-contract formalization + scanner reconciliation check** — write `assistant/instructions/notion-contract.md` (§5 from the assistant's side); **verify** (and tighten only if needed) the scanner-side reconciliation (D15) so assistant-resolved + Tracker-applied rows are handled with **zero** fetch/filter/score change. Confirm the Tracker firewall is intact. | §5, D6/D7/D11/D15 |
| 3.5 | **Setup / binding walkthrough** — finalize `assistant/README.md`: create the Project, paste/upload the composed instructions, upload data per `data-manifest.md`, connect the Notion MCP connector (write scope to Tracker + Passed/Seen), probe-read `📥 New — Unreviewed` to confirm the binding. | §2/§4, D1/D5/D12 |
| 3.6 | **Acceptance** — `borjan-pm` real supervised loop (record 1–2 real applications, confirm next-scan dedup) + `ani-backend-java` portability proof; capture lessons. | §8, D14 |
| 3.7 | **CI** — extend `validate-platform`: composer runs clean per profile with an `assistant/` binding; composed output + `voice.md` pass a **no-PII-shaped-content** check; `assistant/` package structure lints; `data-manifest.md` parses. | — |
| 3.8 | **Docs** — update ARCHITECTURE §5 (the operationalized transition table), PROFILE_CONFIG_SPEC (the `profiles/<id>/assistant/` binding files + composer), PROGRESS. | — |
| 3.9 | **Human-readable documentation** — update `docs/PLATFORM_GUIDE.md` (what the Application Assistant is, how the apply loop works, the boundary, the Maia/Ani worked example extended through applying). *Standing rule, PROJECT_PLAN §4.* | — |

## 10. Out of scope for Phase 3

- **Auto-apply / computer-use browsing / authenticated scraping** — engine law, unchanged. The assistant
  drafts and records; the human submits the application. No automated form submission.
- **Interview-stage progression automation** — the assistant may update a Tracker status when the user
  reports back, but Phase 3 builds no automated Screening/Interview/Offer tracking or reminders.
- **The Gemini cross-check** — stays scanner-side (D16), untouched.
- **Multi-user / multi-Project management, account/login, connector provisioning** — Phase 4/5 app layer.
  Phase 3 binds one profile to one Project via the composer + a manual claude.ai setup.
- **Any scanner behavior change** — Phase 3 adds the composer + a guarded reconciliation check only; no
  change to what a scan fetches, filters, scores, or writes (prime directive).
- **A scanner Tracker write path** — the firewall stands; the Tracker is written only by the assistant
  and the existing "I applied" chat flow.
- **Phase 4 FE app.**

## 11. Guardrails carried from Phases 1–2 (do not regress)

- **The scanner and `borjan-pm` stay production and untouched — the prime directive (§0a).** No behavior
  change to scans, state, history, or the run skill's judgment layer; Borjan keeps searching throughout.
- **The Tracker firewall is sacred.** The scanner **never** writes the Applications Tracker, in any mode.
- **CV/PII never enters the repo** (D5) or any scan artifact or write-back suggestion.
- **Strict validation / honesty:** the composer refuses to emit an invalid or PII-carrying binding with a
  named error; the assistant never drafts against an unverified posting (D10) and never silently papers a
  gap (gap-honesty doctrine).
- **Dedup + staleness discipline** unchanged: a Tracker-applied match is a hard silent drop; the sweep
  owns proactive staleness (the assistant only records directly witnessed death, D11).

## 12. Execution handoff — models, effort, and the pre-build review gate

Recommended pipeline: **plan (done) → Claude Fable 5 pre-build review → Claude Opus 4.8 build.** Put the
most-capable model where judgment on the finished spec pays off (adversarial review of a boundary-heavy
artifact), and the cost-efficient model on execution.

### 12.1 Pre-build review gate (step 3.0) — Claude Fable 5

Before any build step, run **one scoped adversarial review of this plan** on Claude Fable 5. Purpose:
catch structural gaps before they propagate into the package split + the composer + the live loop. Scope
it tightly — **read the Phase 1/2 contracts for grounding, but critique `PHASE_3_PLAN.md` only.** Phase
3's biggest risks are at the *seams*: the write-ownership partition (does any transition let the scanner
and assistant collide?), the data boundary (does any step leak PII into the repo or make the assistant
read repo state at runtime?), the cross-process dedup handoff (D7/D15 — does an assistant-recorded apply
reliably dedup on the next scan without an assistant `seen.jsonl` write?), and the prime directive (does
the reconciliation in 3.4 change any scanner behavior?). Review prompt:

> Read `docs/PROGRESS.md` and `docs/PHASE_3_PLAN.md` in full, plus `docs/ARCHITECTURE.md` §5 (the Notion
> contract + write-ownership invariant), `docs/PROFILE_CONFIG_SPEC.md`, and
> `profiles/borjan-pm/references/pitching.md` as the Phase 1/2 contracts + source material Phase 3
> extends. Spot-check `skills/job-scout-run/SKILL.md` (the "I applied" flow, the Tracker firewall, the
> dedup + sweep rules) to verify Phase 3's write-ownership and reconciliation claims fit the existing
> engine. Then act as a pre-build reviewer of **`PHASE_3_PLAN.md` only** — do not critique the settled
> Phase 0/1/2 docs. Hunt ONLY for **structural gaps, contradictions, unstated assumptions, seam risks
> with the Phase 1/2 contracts (especially: could the scanner and assistant collide on a Notion row? could
> any step leak PII into the repo or require a runtime repo read by the assistant? does an
> assistant-recorded application reliably dedup on the next scan? does the 3.4 reconciliation change any
> scanner fetch/filter/score/write behavior — the prime directive?), and checklist-sequencing problems**
> that would cause the Phase 3 build to fail or require rework. Do NOT re-litigate the locked decisions
> D1–D16, and do NOT propose new scope. Output a short prioritized list of genuine risks, each with a
> one-line suggested fix — or "no blocking issues found." Do not change any files — this is review only.

Effort: **xhigh** (bounded one-shot, high leverage; `high` is the acceptable floor). Address any
*blocking* findings by amending the plan (keeping D1–D16 intact) before starting 3.1; non-blocking
suggestions are optional.

### 12.2 Build model + per-step effort — Claude Opus 4.8

Build on `claude-opus-4-8`. A well-specified checklist is execution, not open-ended reasoning — Fable 5's
edge doesn't pay off here and draws ~1.5–2× the usage. Default effort **`high`**; tier it:

| Steps | Effort | Why |
|-------|--------|-----|
| 3.1 (package extraction), 3.2 (profile split), 3.8–3.9 (docs) | `medium` | mechanical, well-patterned (a diffable extraction + doc updates) |
| 3.3 (composer), 3.5 (setup guide), 3.7 (CI) | `high` | real design surface, bounded by spec |
| 3.4 (write-contract + reconciliation check), 3.6 (live acceptance) | `xhigh` | the firewall/boundary correctness + the end-to-end supervised test |

Escalate a single step to Fable 5 only if it turns out genuinely hard/ambiguous mid-build.
