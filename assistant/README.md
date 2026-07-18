# `assistant/` — the Application Companion package

The generic, profile-agnostic instruction package for the **Application Companion** (Phase 3a).
It is the companion counterpart to `skills/job-scout-run/` (the scanner): the scanner finds
roles and writes the Notion shortlist; the companion reads that shortlist and helps the user
apply — in their own voice, from their real experience. See `docs/PHASE_3A_PLAN.md` for the
design contract and `docs/PROJECT_PLAN.md` §1/§1a/§3 for the vision and principles.

## What's here

The numbered modules are the generic doctrine, composed **in order** into a Project's
instructions by `core/compose_assistant.py`:

| Module | Covers |
|--------|--------|
| `00-overview.md` | What the companion is; the two assets; hard boundaries; the snapshot-date rule |
| `01-consent-and-data.md` | Consent + the data principle; two doc retention classes; both-stores deletion |
| `02-voice-acquisition.md` | The voice profile: gather → extract → honest meter → manual persist |
| `03-knowledge-base.md` | The KB: seed, retrieve, honest-answer discipline, growth loop, manual persist |
| `04-apply-loop.md` | The per-role loop: queue → prior history → re-verify → decide → draft → record |
| `05-notion-write-contract.md` | Write-ownership by row state; the **pinned select vocabulary**; recording |
| `06-verification.md` | Re-verify fetch-first; the wall/paste fallback; dead → `Stale/Expired` |
| `07-voice-delivery-discipline.md` | Copy-blocks, first-draft voice, AI-tells, salary-ask, closing gate |

Not composed (they don't match the `NN-*.md` glob): this `README.md`, `SETUP.md` (the binding
walkthrough), and `DRY-RUN.md` (the voice + KB persistence-round-trip script). Those are for the
human running the setup and the acceptance dry-run, not for the Project's instructions.

## How binding works

1. The engine composes the generic modules + a **PII-free profile snapshot** (floor, eligibility,
   location/timezone, Notion `data_source_id`s) via `core/compose_assistant.py` into **two** files:
   the full **`project-instructions.md`** (→ Project *knowledge*) and a compact
   **`project-bootstrap.md`** (→ the Project *custom-instructions* field, which caps at ~4k chars).
2. The user creates a **claude.ai Claude Project**, pastes the **bootstrap** into custom
   instructions, uploads **`project-instructions.md`** + their materials (per the profile's
   `assistant/data-manifest.md`) into Project knowledge, and connects the **Notion MCP**.
3. The companion builds the user's voice profile and knowledge base **inside the Project** (the
   repo never sees the user's CV/PII — the data principle), and works the Notion shortlist.

The **voice profile and knowledge base are not composed from the repo** — they are built and
held inside the Project. The repo → Project flow is config only, one-directional, no PII.

## Setup & binding

The full step-by-step walkthrough — create the Project, paste, upload, connect the MCP,
probe-read the queue, and verify the pinned select options — is in **`SETUP.md`** (this
directory). Start there when standing up a new companion.
