# Phase 3a Execution Plan — Voice + Knowledge Base + the Apply Loop

> The detailed build plan for **Phase 3a**, the first stage of the Application Companion
> (Phase 3 is staged 3a → 3b → 3c). Vision, phase scope, and the two standing principles are
> in **[PROJECT_PLAN.md](PROJECT_PLAN.md) §1/§1a/§3** (the single source of truth) — this
> document does not restate them, it *executes* 3a. Companion to
> [ARCHITECTURE.md](ARCHITECTURE.md) §5 (the Notion contract) and
> [PROFILE_CONFIG_SPEC.md](PROFILE_CONFIG_SPEC.md). Written to be executed by a build agent in
> a later session. Where it refines earlier drafts it wins; the superseded apply-bot
> [PHASE_3_PLAN.md](PHASE_3_PLAN.md) is retained only as apply-loop reference.
>
> Status: **3a.0 gate passed (2026-07-17) — ready for the Opus 4.8 build (§11.2)** ·
> Created: 2026-07-18 · Brainstorm: Opus 4.8 ·
> Review gate: Fable 5 ✅ 2026-07-17 — 8 findings + the D13 ⚑ ruling, all amended (§11.1) ·
> Build: Opus 4.8 (§11.2)

---

## 0. What 3a is (one paragraph)

The companion's foundation and its first usable loop. 3a builds the two user-owned assets —
the **voice profile** (how the user actually writes, learned from their own writing or built
by guided questions) and the **knowledge base** (their real experience and honest answers) —
and then runs the **per-role apply loop**: read the scanner's `📥 New — Unreviewed` shortlist,
re-verify each posting, draft the application **in the user's voice** from the knowledge base,
capture the Q&A, grow the knowledge base whenever the user fills a gap the companion couldn't,
and record the application. It runs on the **claude.ai Claude Project + Notion MCP** substrate
(storage option **(a)** — a consented server-side interim per the data principle; the
client-side store is Phase 4). The apply loop's scanner-facing contract was settled in the
superseded apply-bot plan and is carried in verbatim here; the voice + knowledge-base halves
are new. 3a is the milestone Borjan UATs against real jobs right after a scan.

## 0a. Standing principles (both apply — see PROJECT_PLAN §1a)

- **Prime directive:** the scanner and `borjan-pm` are production and untouched. 3a adds a
  claude.ai-side package plus one small composer and **one new, additive scanner-side
  reconciliation step** (§6 — a scan-start Notion read + `seen.jsonl` back-fill + a
  read-before-write sweep guard; it does not exist today and is BUILT in 3a.4, the one
  permitted scanner change) — no change to what a scan fetches from boards, filters,
  scores, or writes as shortlist rows. The **Tracker firewall is sacred** (the scanner
  never writes the Applications Tracker; the reconciliation READ does not weaken it).
- **Data & privacy principle:** the user owns their voice, knowledge base, and source docs;
  all deletable; used only for their own applications; never mined. Client-side is the
  destination (Phase 4); 3a's Project+Notion substrate is the consented interim. CV/PII never
  enters the repo.

## 1. Decisions locked (the design contract)

Settled across the Phase 3 brainstorms (apply-loop pass + companion reframe). Do not
re-litigate; implement. Items marked **⚑ gate** are proposals made to keep 3a buildable that
the 3a.0 review is explicitly invited to stress-test.

| # | Decision |
|---|----------|
| D1 | **Two user-owned assets are the foundation: the *voice profile* and the *knowledge base*.** Everything the companion drafts draws from both. Both grow with use. Both are the user's, deletable, never mined (data principle). |
| D2 | **Voice is learned from the user's own writing, or built by guided Q&A if they have none.** Preferred input: things they actually wrote (cover letters, articles, posts, past answers). No-writing path: a guided interview whose questions are tuned to the user's field. |
| D3 | **The voice "meter" is honest, not a fake percentage.** It reports *coverage* of how the user writes (sentence rhythm, register, go-to phrases/constructions, English level, real worked examples) plus a **blind calibration** — the companion drafts a short sample, the user judges "that's me / not me," adjust and repeat. **The user decides when it's good enough.** No pseudo-scientific score. |
| D4 | **Two document retention classes.** *Domain docs* (carry factual/experience content) are kept in the knowledge base by default and deletable anytime. *Voice-only docs* (offered solely so the companion can learn voice, no lasting factual value) are **shredded immediately after voice extraction**, and the user is told this plainly before they share them. A doc that carries both is treated as a domain doc (kept). |
| D5 | **The knowledge base is the source of *honest* answers.** It never invents experience. On a question it can't answer from what it holds, it says so plainly, the user supplies the answer, the companion tightens the wording, and it is **stored back — the knowledge base grows.** (The unknown-answer→growth loop; same gap-honesty doctrine as the scanner, turned into a write path.) |
| D6 | **Notion is the sole scanner↔companion bridge** (carried from the apply-loop pass). The companion lives on claude.ai — it cannot read repo files or run `core/*.py` — so its scanner-facing persistence is Notion only. The scanner reads Notion at scan start for dedup; the companion writes the Tracker + resolves shortlist rows. Neither reads the other's local state. |
| D7 | **Write-ownership partitions by row STATE** (carried). Scanner writes a Passed/Seen row only while `New — Unreviewed` (creation) or → `Stale/Expired` (staleness). Companion writes only transitions *out* of `New — Unreviewed` (→ `User Declined` + reason, or → `Applied`-adjacent) + Tracker row creation. Dedup makes the scanner never re-touch a resolved row, so they cannot collide. |
| D8 | **The Tracker row is the cross-process dedup handoff** (carried). Companion creates the `Applied` row via Notion MCP → next scan reads the Tracker → hard-silent-drops the role → reconciles `seen.jsonl` (scanner-side, additive/idempotent, **zero** fetch/filter/score change). No `seen.jsonl` write from the companion. |
| D9 | **Companion primary + Claude Code "I applied" chat fallback** (carried). The companion is the canonical scanner-external Tracker writer; the existing chat flow persists for off-session applies. Both idempotent-by-URL. The scanner writes the Tracker in neither case (firewall). |
| D10 | **Re-verify fetch-first with an honest paste/confirm fallback** (carried). The companion fetches the posting URL and re-checks the hard facts (still live; eligibility; hours; salary; employment type). On a JS/login/thin wall it asks the user to paste/confirm. Never draft against an unverified posting. |
| D11 | **The companion may set `Stale/Expired` on a directly observed dead posting** (carried), with a dated note — a shared terminal state neither app resurrects. The sweep remains the proactive staleness engine. |
| D12 | **A small, PII-free composer binds a profile to its Project.** `core/compose_assistant.py` composes the generic instruction package + a minimal profile-config snapshot (floor for the salary-ask safety check, eligibility for the B2B gate, location/timezone for verification, Notion `data_source_id`s) into `project-instructions.md` the user pastes into the Project. Config only, one-directional (repo→Project), no PII. The **voice profile and knowledge base are NOT composed from the repo** — they are built and held inside the Project (D13). |
| D13 | **⚑ gate — the substrate-(a) storage split: Project holds knowledge, Notion holds application state.** The **Claude Project** holds the user's source docs, the derived voice profile, and the knowledge base (the material the companion reasons over). **Notion** holds application *state* — the Passed/Seen shortlist rows and the Applications Tracker rows (incl. the submitted answers in the row body so the user can revisit them). Both are storage-option-(a) interim; the durable data model (D14) is designed so both lift into the Phase 4 client-side store unchanged. *⚑ resolved by the 3a.0 gate: split CONFIRMED — keep. The Q&A log stays in Notion (moving it into the Project would worsen the manual-persistence burden of §3/§4 and lose the user's revisit surface). Answers are deliberately dual-homed — the Notion body is the per-role record, the Project KB entry the reusable knowledge and the draft-time retrieval source — and the consent language names BOTH stores in the deletion story (deleting the Project does not delete Notion bodies).* |
| D14 | **The durable data model is designed now, substrate-agnostic.** Five user-owned entities (PROJECT_PLAN §3): voice profile, knowledge base, application log, interview records, CV state. **3a builds the first three** (interview records + CV state are 3b/3c) but the model is shaped so 3b/3c extend it and Phase 4 migrates all of it to the client-side store without rework. |
| D15 | **Acceptance = Borjan's real loop after a live scan + an `ani-backend-java` portability proof** (carried, extended). Borjan onboards his own voice + knowledge base, runs the apply loop on real `New — Unreviewed` roles, records a real application, and the next scan dedups it. Ani proves the package isn't Borjan-shaped. |
| D16 | **The Gemini cross-check stays scanner-side** (carried) — out of companion scope. |

## 2. The durable data model (D14) — what 3a builds

Substrate-agnostic entity shapes (the Project/Notion rendering is D13; Phase 4 re-homes them):

- **Voice profile** — a structured, human-readable description of how the user writes:
  sentence rhythm and length, register/formality, recurring constructions and openers,
  vocabulary level, rhetorical habits, AI-tells to avoid, and 1–2 worked example paragraphs.
  Derived (D2/D3), non-destructive to kept docs, held in the Project.
- **Knowledge base** — the user's kept domain docs + a growing store of question→honest-answer
  entries (D5), tagged by topic so the apply loop can retrieve the relevant slice. Held in the
  Project. No PII leaves it to the repo.
- **Application log** — per role: the posting, the questions asked, the answers submitted, the
  decision (applied/declined + reason), the date. The record the user revisits. On substrate
  (a): the Notion Tracker/Passed-Seen rows + their page bodies (D13). Answers are deliberately
  dual-homed: the Notion body is the per-role *record*; the Project KB entry is the reusable
  *knowledge* — **the KB, not the Notion body, is the draft-time retrieval source** (3a.0 gate).

## 3. Voice acquisition (D2/D3/D4) — the procedure the package specifies

1. **Explain + consent.** The companion explains what it needs and why (to sound like the
   user, and to answer honestly from real experience), that materials are the user's and
   deletable, and — for anything shared purely to learn voice — that it is **deleted right
   after extraction, never stored** (D4). Nothing is used for training or any secondary use.
   The consent language also names the **second store** (3a.0 gate): application content
   recorded to Notion row bodies (§5) is not deleted by deleting the Project — the deletion
   story covers both stores.
2. **Gather.** Preferred: the user's own writing. If they have little/none, run the guided
   Q&A (field-tuned questions) instead or in addition (D2).
3. **Extract → voice profile.** Distill the material into the structured voice profile (§2),
   non-destructively (kept docs stay in the KB; voice-only docs are shredded here, D4).
4. **Meter + calibrate (D3).** Show coverage of the voice dimensions, then draft a short blind
   sample; the user judges "me / not me"; refine. Repeat until the **user says it's good
   enough** — their call, no fake score.
5. **Persist.** Save the voice profile as a Project artifact (D13). **Persistence mechanic
   (3a.0 gate):** the companion cannot write Project knowledge itself — it regenerates one
   canonical `voice-profile.md` and the USER saves it to Project knowledge; the package states
   this manual step honestly. Re-runnable to deepen later (3c's writing coach feeds it more
   material).

## 4. Knowledge base (D5) — structure + the growth loop

- **Seed** from the user's kept domain docs + any past application answers (tagged by topic).
- **Retrieve** the relevant slice per application question at draft time.
- **Honest-answer discipline:** never invent experience; when the KB lacks an answer, say so
  plainly, name the nearest real adjacent experience if any, and **flag the gap to the user**
  (same doctrine as the scanner's gap-honesty procedure).
- **Growth loop (the KB's engine):** on a gap the user fills, the companion tightens the
  wording into an honest answer and **stores it back to the KB**, tagged — so the same question
  never needs re-asking and the base compounds over use.
- **Persistence mechanic (3a.0 gate):** same as the voice profile — claude.ai offers no
  programmatic write into Project knowledge, so the companion maintains one canonical
  `knowledge-base.md` it regenerates on every growth event and the USER re-saves to Project
  knowledge. The package makes this step explicit each time; the 3a.5 dry-run must prove the
  round-trip across **two separate conversations** (a single-conversation dry-run would pass
  without ever exercising the KB's actual value).

## 5. The apply loop (D6–D11) — per role, user-paced

Carried from the settled apply-loop design; now drawing on the voice profile (§3) and KB (§4).

1. **Read the queue** — query the profile's `📥 New — Unreviewed` view via Notion MCP; the
   user picks a role or goes top-down.
2. **Present + surface prior history** — role + notes; if the company appears elsewhere in the
   Tracker/Passed-Seen, surface the prior reqs and their status (read from Notion).
3. **Re-verify (D10, mandatory)** — fetch the URL, re-check the hard facts against the profile
   constraints; on a wall, ask the user to paste/confirm; if dead → `Stale/Expired` (D11).
4. **Decide** apply/pass with the user (companion advises; user decides).
5. **Draft in voice (on apply)** — cover letter / email pitch / form answers, applying the
   voice profile on the **first** draft, sourced from the KB with the honest-answer + growth
   loop (§4). Every submittable text in a **copy-block**; analysis outside it.
6. **Record** — on "applied": create the `Applied` Tracker row (+ submitted answers in the
   body) and flip the Passed/Seen row `New — Unreviewed` → **`User Applied Elsewhere`** (the
   provisioned applied-resolution option). On "pass": flip → **`User Declined`** + the user's
   real reason. **Vocabulary is pinned (3a.0 gate):** the companion writes only exact select
   values from the provisioned Passed/Seen vocabulary (`provision_notion.py` REASON_OPTIONS /
   `notion_sync.py` VALID_REASONS) — a free-text variant would make Notion silently mint a
   stray option the scanner doesn't recognize. A new label is a 3a.4 provisioning decision
   (added to both constants), never an ad-hoc MCP write.
7. **Next role.**

## 6. Package, binding & composer (D12/D13)

- **`assistant/` (generic, profile-agnostic)** — the companion instruction package + setup
  guide, sibling to `skills/job-scout-run/`. Modules: the voice-acquisition procedure (§3),
  the knowledge-base + growth loop (§4), the apply loop (§5), the Notion write contract (§5,
  from the companion side), verification (D10), voice/delivery discipline (copy-blocks, AI-tell
  avoidance, first-draft voice), and the data-principle/consent language (D4). Built by
  extracting the generic doctrine from `profiles/borjan-pm/references/pitching.md`.
- **`profiles/<id>/assistant/` (per-profile)** — the profile residue of `pitching.md`
  (`voice-seed.md`: source-doc priority, the Gemini-not-ChatGPT correction, the B2B/visa
  mechanism, profile links, domains) + `data-manifest.md` (what to upload to the Project).
  `gemini-prompt.md` stays scanner-side (D16). *Note:* the profile's `voice-seed.md` is
  authored guidance, not PII; the **derived voice profile** lives in the Project (D13).
  **`references/pitching.md` itself REMAINS in place, intact (3a.0 gate):** the run skill's
  pitch router loads it at runtime for the Code-lane pitch flow (`borjan-pm` production —
  prime directive); the split *extracts copies*, it never hollows out the source. And
  `voice-seed.md` is **optional per profile** — a profile without one (e.g.
  `ani-backend-java`) gets the guided-Q&A path.
- **`core/compose_assistant.py`** — deterministic, idempotent, PII-free composer (D12):
  generic package + profile-config snapshot + Notion IDs → `profiles/<id>/assistant/project-instructions.md`.
  **Snapshot-staleness guard (3a.0 gate):** the composer stamps a **compose date +
  source-config hash** into the output, the package has the companion announce its snapshot
  date, and the README names the re-compose triggers (any `profile.yaml` change — floor,
  eligibility, Notion IDs). The Project cannot read the repo, so a stale snapshot drifts
  silently — the engine's own memory-ID lesson (IDs drift; the profile is the source of
  truth) applies doubly to a pasted snapshot. Handles a profile with no
  `assistant/voice-seed.md` (composes the guided-Q&A path).
- **Scanner reconciliation — a BUILD, not a verification (3a.0 gate).** No reconciliation
  exists today: the scanner never reads Notion at scan start (`notion_sync.py` is push-only),
  the `applied` status in `seen.jsonl` is written solely by the chat "I applied" flow, the
  sweep's scope is `seen.jsonl`-only (`status == "shortlisted"`), and `apply_sweep_update`
  blind-PATCHes `Reason Passed` — so a companion-resolved row would stay in sweep scope
  forever and, when the posting dies, be clobbered back to `Stale/Expired` (a D7 violation).
  3a.4 BUILDS the additive step, in two parts: **(1) a token-gated scan-start Tracker read**
  → back-fill matching `seen.jsonl` records to `applied` (idempotent; sequenced BEFORE the
  sweep in the run pipeline so applied rows exit sweep scope the same run; tokenless runs
  skip it with an honest ledger note); **(2) a read-before-write guard in
  `apply_sweep_update`** — flip only a row still `New — Unreviewed`, so companion-resolved
  rows (`User Declined` has no Tracker row to reconcile from) are never clobbered. Board
  fetch/filter/score untouched; the Tracker firewall intact (the new access is a READ).

## 7. Acceptance (D15)

- **Primary — `borjan-pm`, real, supervised.** Stand up Borjan's companion Project (upload his
  writing + domain docs; connect Notion MCP; compose the binding). Build his voice to *his*
  "good enough" (D3) and seed his KB. Run the loop on **1–2 real `New — Unreviewed` roles**:
  re-verify → draft in his voice (copy-blocks; B2B gate + salary-ask against his real floor;
  honest-answer loop) → record → confirm the next scan **hard-silent-dedups** the applied role
  and `seen.jsonl` reconciles. His real job search, done the new way.
- **Proof — `ani-backend-java`, portability.** Compose Ani's binding; confirm the generic
  package produces a coherent non-Borjan voice-build + apply loop on her real Java shortlist.
- **Passes when:** voice reaches user-judged good-enough; the KB answers honestly, grows on
  a filled gap, and **round-trips across separate conversations** (§4 persistence mechanic);
  a real application records correctly to the right DBs; the next scan dedups it **and
  back-fills `seen.jsonl` (3a.4 reconciliation), and a subsequent sweep leaves the
  companion-resolved rows untouched (no clobber)**; the scanner is behaviorally unchanged
  beyond the 3a.4 additive step (prime directive) and the firewall holds; no CV/PII in the
  repo (data principle). Capture lessons into `assistant/` (generic) or the profile —
  lesson text passes the same no-PII discipline as 3a.8.

## 8. Out of scope for 3a

- **The interview lifecycle** (JD-driven prep, debrief→feedback, paste-email status) — **3b**.
- **CV doctor + delta ingest + writing coach** — **3c**.
- **The client-side/GDPR store (option b), real UI, the voice meter as a UI element** — **Phase 4**.
- **Email OAuth auto-ingest, LinkedIn export ingest** — **Phase 5**.
- **Auto-apply / computer-use / authenticated scraping** — engine law, never.
- **Any scanner behavior change** beyond the guarded additive reconciliation build (§6, 3a.4).

## 9. Ordered build checklist (seed into PROGRESS.md)

Ordered so the scanner + `borjan-pm` stay untouched at every step.

| # | Step | Notes |
|---|------|-------|
| 3a.0 | **Pre-build review gate (Fable 5, xhigh)** — scoped adversarial review of *this plan*; amend blocking findings (D1–D16 intact) before 3a.1. | §11.1 |
| 3a.1 | **`assistant/` generic package** — voice-acquisition, KB + growth loop, apply loop, Notion write contract, verification, voice/delivery discipline, consent/data-principle language + README setup guide; extract generic doctrine from `pitching.md`. | §3–§6 |
| 3a.2 | **Profile-side split** — `profiles/borjan-pm/assistant/voice-seed.md` + `data-manifest.md` (residue of `pitching.md`); `gemini-prompt.md` stays put; **`references/pitching.md` stays in place intact** (the run-skill pitch router loads it at runtime — prime directive); verify loss-free *including the router still resolving*; `voice-seed.md` optional per profile. | §6, D16 |
| 3a.3 | **`core/compose_assistant.py`** — deterministic, idempotent, PII-free composer → `project-instructions.md`; stamps compose date + source-config hash (re-compose triggers documented in the README); handles absent `voice-seed.md` (guided-Q&A path). | §6, D12 |
| 3a.4 | **Notion write-contract + scanner reconciliation BUILD** — companion-side contract doc pinning the exact Passed/Seen select values to the provisioned vocabulary; BUILD the additive scan-start Tracker read → `seen.jsonl` back-fill (token-gated, sequenced before the sweep, honest ledger skip when tokenless) + the read-before-write guard in `apply_sweep_update`; board fetch/filter/score untouched; firewall intact. | §5/§6, D6–D11 |
| 3a.5 | **Voice + KB build procedure** — finalize the §3/§4 procedures in the package; dry-run the voice meter + growth loop end-to-end (no live application yet), **proving the voice/KB persistence round-trip across TWO separate conversations** (the manual re-save mechanic). | §3/§4, D2–D5 |
| 3a.6 | **Setup / binding walkthrough** — `assistant/README.md`: create the Project, paste instructions, upload per manifest, connect Notion MCP, probe-read `New — Unreviewed` **+ verify the pinned status select options exist in the profile's DBs**. | §6, D6/D12/D13 |
| 3a.7 | **Acceptance** — `borjan-pm` real supervised loop (record 1–2 real applications, confirm next-scan dedup + reconciliation back-fill + sweep no-clobber) + `ani-backend-java` portability proof; capture lessons. | §7, D15 |
| 3a.8 | **CI** — composer runs clean per profile; composed output + `voice-seed.md` pass a no-PII check — **defined as a denylist: emails, phone numbers, postal addresses, CV-body facts beyond what `profile.yaml` already holds** (the 2.7 writeback guard is NOT reusable here — voice-seed legitimately carries URLs + full sentences); `assistant/` structure lints; `data-manifest.md` parses. | — |
| 3a.9 | **Docs** — ARCHITECTURE §5 (companion transitions), PROFILE_CONFIG_SPEC (binding files + composer), PROGRESS. | — |
| 3a.10 | **Human-readable documentation** — refresh `docs/PLATFORM_GUIDE.md` (the companion: voice, KB, apply loop; boundary; worked example). *Standing rule, PROJECT_PLAN §4.* | — |

## 10. Guardrails (do not regress)

- **Both standing principles** (§0a / PROJECT_PLAN §1a): scanner + `borjan-pm` untouched, Tracker
  firewall sacred; data is the user's, deletable, unmined, client-side-bound.
- **Notion is the only scanner↔companion bridge**; write-ownership by row state; no companion
  `seen.jsonl` write; the scanner reconciles local state (additive, zero behavior change).
- **CV/PII never enters the repo**; voice-only docs shredded after extraction (D4).
- **Honest-answer discipline**: never invent experience; never draft against an unverified
  posting; flag gaps to the user.

## 11. Execution handoff — models, effort, and the review gate

Same pipeline as Phase 2: **plan (done) → Fable 5 pre-build review → Opus 4.8 build.**

### 11.1 Pre-build review gate (step 3a.0) — Claude Fable 5

Run one scoped adversarial review of **this plan only** (the Phase 0–2 docs and PROJECT_PLAN
vision are settled — read for grounding, don't critique). Hunt for structural gaps,
contradictions, seam risks with the Phase 1/2 contracts, and — specifically — stress-test the
**⚑ gate** decision D13 (the Project/Notion storage split), the data-principle boundary (could
any step leak PII into the repo, or require the companion to read repo state at runtime?), the
cross-process dedup handoff (D8, does an applied role reliably dedup with no companion
`seen.jsonl` write?), and whether the §6 reconciliation changes any scanner behavior (prime
directive). Review prompt:

> Read `docs/PROGRESS.md`, `docs/PHASE_3A_PLAN.md`, and `docs/PROJECT_PLAN.md` §1/§1a/§3 in
> full, plus `docs/ARCHITECTURE.md` §5, `docs/PROFILE_CONFIG_SPEC.md`, and
> `profiles/borjan-pm/references/pitching.md` as the contracts + source material 3a extends.
> Spot-check `skills/job-scout-run/SKILL.md` (the "I applied" flow, the Tracker firewall, dedup
> + sweep) to verify 3a's write-ownership and reconciliation claims fit the engine. Then act as
> a pre-build reviewer of **`PHASE_3A_PLAN.md` only** — do not critique the settled Phase 0–2
> docs or the PROJECT_PLAN vision. Hunt ONLY for structural gaps, contradictions, unstated
> assumptions, seam risks with the Phase 1/2 contracts (especially: could the scanner and
> companion collide on a Notion row? could any step leak PII into the repo or require a runtime
> repo read by the companion? does an applied role reliably dedup on the next scan? does the §6
> reconciliation change any scanner fetch/filter/score/write behavior?), the soundness of the
> ⚑-flagged D13 storage split, and checklist-sequencing problems that would cause the 3a build
> to fail or require rework. Do NOT re-litigate the locked decisions D1–D16, and do NOT propose
> new scope. Output a short prioritized list of genuine risks, each with a one-line suggested
> fix — or "no blocking issues found." Do not change any files — this is review only.

Effort: **xhigh** (`high` is the acceptable floor). Amend blocking findings (D1–D16 intact)
before 3a.1; non-blocking suggestions optional.

**Gate outcome (2026-07-17, Fable 5 @ xhigh): RAN — 8 findings + the D13 ⚑ ruling, ALL
amended into this plan (D1–D16 intact; claims verified against the engine code, not just the
docs).** Blocking: (1) the D8 reconciliation did not exist in the engine — the scanner never
reads Notion at scan start and the `applied` back-fill was chat-flow-only, so 3a.4 was
re-scoped from "verify" to **BUILD** (token-gated Tracker read → `seen.jsonl` back-fill,
sequenced before the sweep) and §0a re-worded to name it the one permitted additive scanner
change; (2) the sweep's `seen.jsonl`-only scope + blind `apply_sweep_update` PATCH would
clobber companion-resolved rows on posting death — and `User Declined` flips have no Tracker
row to reconcile from — so 3a.4 gained the **read-before-write sweep guard** (flip only rows
still `New — Unreviewed`). High: (3) claude.ai Projects offer no programmatic knowledge
write — the manual voice/KB re-save mechanic is now explicit (§3/§4) and 3a.5's dry-run must
round-trip across two conversations. Moderate: (4) the companion's Passed/Seen select values
pinned to the provisioned vocabulary (§5.6, 3a.4, 3a.6); (5) composer snapshot staleness —
compose-date + config-hash stamp + named re-compose triggers (§6, 3a.3); (6)
`references/pitching.md` stays in place intact — the run-skill pitch router loads it at
runtime (§6, 3a.2). Minor: (7) the 3a.8 no-PII check defined as a denylist (the 2.7
writeback guard is not reusable); (8) the composer handles a voice-seed-less profile (Ani,
guided-Q&A path). **D13 ⚑ resolved: split confirmed** — Q&A log stays in Notion; the KB is
the draft-time retrieval source; the deletion story names both stores.

### 11.2 Build model + per-step effort — Claude Opus 4.8

Build on `claude-opus-4-8`. Default effort **`high`**; tier it. *(Retiered after the 3a.0
gate: the gate resolved the design ambiguity that originally put 3a.4/3a.5 at `xhigh` —
they are now precise specs, and careful execution of a precise spec is `high` work. The
`xhigh` premium is reserved for genuine unknowns, via the auto-escalation rule below and
the live acceptance.)*

| Steps | Effort | Why |
|-------|--------|-----|
| 3a.1–3a.2 (package extraction, profile split), 3a.9–3a.10 (docs) | `medium` | mechanical, well-patterned |
| 3a.3 (composer), 3a.6 (setup guide), 3a.8 (CI) | `high` | real design surface, bounded by spec |
| 3a.4 (write-contract + reconciliation), 3a.5 (voice/KB procedure) | `high` + **auto-escalate** | post-gate these are precise specs (§6 reconciliation mechanics; §3/§4 persistence mechanic). **Auto-escalation rule: the moment the step surfaces ANYTHING the amended spec does not cover** — a back-fill idempotency edge, a tokenless-path surprise, a sweep-ordering interaction, Notion 429/permission behavior, a persistence-mechanic gap — **STOP, switch the step to `xhigh`, and only then continue. Never improvise past the spec at `high`.** |
| 3a.7 (live acceptance) | `xhigh` | live judgment against real postings + the end-to-end firewall/dedup/no-clobber verification — the one step where open-ended thinking is back in play |

Escalate a single step to Fable 5 only if it turns out genuinely hard/ambiguous mid-build
(i.e. `xhigh` still isn't resolving it).
