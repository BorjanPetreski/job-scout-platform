# Phase 3a — Acceptance runbook (Borjan's supervised live loop)

Everything for 3a is built and green (steps 3a.1–3a.6). **3a.7 is the acceptance — your
supervised live loop** — because it needs real judgment against real postings and your call on
"that sounds like me." This is the exact, ordered list of what *you* do. Nothing here changes the
scanner or `borjan-pm` config; the loop runs on the claude.ai side + Notion.

Contract: [PHASE_3A_PLAN.md](PHASE_3A_PLAN.md) §7 · package: [`assistant/`](../assistant/) ·
setup detail: [`assistant/SETUP.md`](../assistant/SETUP.md) · voice/KB dry-run:
[`assistant/DRY-RUN.md`](../assistant/DRY-RUN.md).

---

## What's already done for you

- The generic companion package (`assistant/`) and the two bindings are composed and committed:
  - `profiles/borjan-pm/assistant/project-instructions.md` (your binding — floor 2500 EUR net,
    B2B+full-time, your Notion IDs, your `voice-seed`).
  - `profiles/ani-backend-java/assistant/project-instructions.md` (portability proof — floorless,
    part-time, guided-Q&A path).
- The scanner-side reconciliation (3a.4) is live in `core/scan.py` + `core/notion_sync.py`,
  token-gated and proven offline. It does nothing until you record a real application.

If you changed `profile.yaml` since, re-compose first: `python3 core/compose_assistant.py --profile borjan-pm`.

---

## Part 1 — Stand up your companion Project (borjan-pm)

Follow [`assistant/SETUP.md`](../assistant/SETUP.md) — the short version:

1. On claude.ai, create a **Project** ("Job Applications — Borjan").
2. Paste `profiles/borjan-pm/assistant/**project-bootstrap.md**` into the Project's custom
   instructions, and **upload `project-instructions.md` into Project knowledge** (the full
   doctrine is too long for the custom-instructions field — see SETUP.md §3).
3. Upload your materials into Project knowledge per
   `profiles/borjan-pm/assistant/data-manifest.md` (CV, cover letter, quarterly review, past
   answers, articles). Anything you share *only* for tone, the companion shreds after extraction.
   **None of this touches the repo.**
4. Connect the **Notion MCP** (authorized to your job-search workspace).
5. Ask it to read your **`📥 New — Unreviewed`** view — confirm it lists your current roles.
6. Ask it to confirm the pinned `Reason Passed` / Tracker `Status` options exist (SETUP.md §7).
   Your DBs were provisioned by `provision_notion.py`, so they should all be present.

## Part 2 — Build your voice + seed your KB (prove the round-trip)

Run [`assistant/DRY-RUN.md`](../assistant/DRY-RUN.md) end-to-end **across two separate
conversations**:

- **Conversation 1:** consent → share a couple of things you actually wrote → let it extract your
  voice → check the coverage report and the blind sample; tell it "me / not quite / no" until
  **you** say it's good enough → it regenerates `voice-profile.md`, **you save it to Project
  knowledge**. Then hit one real gap → supply the answer → it stores it and regenerates
  `knowledge-base.md`, **you save it**.
- **Conversation 2 (brand new):** confirm it still drafts in your voice and still has the grown
  answer — *because you saved them*. That's the persistence proof. If Conversation 2 lost
  something, you didn't save the regenerated file — that's the mechanic working, not a bug.

## Part 3 — Work 1–2 real roles (the apply loop)

Pick 1–2 real `📥 New — Unreviewed` roles and, with the companion:

1. **Re-verify** — it fetches the posting and re-checks live/eligibility/hours/salary/employment
   type against your snapshot; on a wall it asks you to paste the JD. It never drafts against an
   unverified posting.
2. **Decide** apply or pass (it advises; you decide). B2B closing gate + salary-ask against your
   real floor (2500 EUR net) apply.
3. **On apply** — it drafts the cover letter / email / answers in your voice, in copy-blocks,
   from your KB (honest-answer + growth loop). You submit them yourself.
4. **Record** — it creates the `Applied` Tracker row (answers in the body) and flips the
   Passed/Seen row `New — Unreviewed` → `User Applied Elsewhere`. On a pass it flips →
   `User Declined` + your reason.

## Part 4 — Confirm the dedup + reconciliation (the scanner half)

After you record at least one real application, from the repo with your Notion token set:

```
export NOTION_TOKEN=<your token>
python3 core/notion_sync.py --profile borjan-pm --reconcile      # scan-start back-fill, standalone
python3 core/scan.py --profile borjan-pm                         # a normal run does it automatically
```

Confirm in the ledger / output:

- **`tracker reconcile: N tracker rows, K back-filled applied, …`** — your applied role's
  `seen.jsonl` record is flipped to `applied` (not tokenless-skipped).
- The applied role **does not reappear** as a new candidate (hard-silent dedup).
- If you **declined** a role and its posting later dies, the sweep must **not** clobber the
  `User Declined` row back to `Stale/Expired` — you'll see a `[sweep-guard] … skipping sweep
  flip, no clobber` line if that case triggers.

**Passes when:** the application recorded to the right DBs; the next scan dedups it and back-fills
`seen.jsonl`; a later sweep leaves the companion-resolved rows untouched; the scanner is otherwise
unchanged; and no CV/PII landed in the repo.

## Part 5 — Portability proof (ani-backend-java)

Spin up a second Project with `profiles/ani-backend-java/assistant/project-instructions.md`,
connect Ani's Notion, and confirm the **same generic package** produces a coherent **non-Borjan**
voice build (guided-Q&A path — she has no voice-seed) and a working apply loop on her real Java
`📥 New — Unreviewed` shortlist. This proves the package isn't Borjan-shaped.

## Part 6 — Capture lessons

Note anything the loop taught us into `assistant/` (generic) or `profiles/borjan-pm/assistant/`
(profile) — **the same no-PII discipline as everywhere: no CV body facts, emails, phone numbers,
or addresses in the repo.** Then we finish 3a.8 (CI), 3a.9 (docs), 3a.10 (guide refresh).

---

### If something's off

- **Companion can't read Notion** → MCP not connected / not authorized to that DB (SETUP §5–6).
- **A stray `Reason Passed` option appears** → a value was written that isn't pinned; check
  `05-notion-write-contract.md` and re-provision if a real new label is needed.
- **`tracker reconcile: skipped — no NOTION_TOKEN`** → export the token before the scan.
- **Snapshot looks stale** (floor/eligibility/IDs changed) → re-run `compose_assistant.py
  --profile borjan-pm` and re-paste into the Project.
