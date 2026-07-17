---
name: job-scout-setup
description: >
  CV-driven setup interview ("the templater") that onboards a NEW job-search profile
  end-to-end. Use this skill whenever someone wants to set up job scouting for a new person
  or a new stream — "onboard me", "set up a new profile", "add a job search for <role>",
  "create a profile from this CV", "try a new stream". It reads a CV (or runs a guided Q&A
  if none), classifies the person to a template stream/subvariant, tailors the template to
  their real experience/seniority/goals within guardrails, provisions their Notion, writes +
  validates profiles/<id>/profile.yaml, and offers a first scan. This is SETUP; the recurring
  scan is the separate job-scout-run skill.
metadata:
  version: "1.0.0"
  status: "Phase 2 — first real onboarding (backend-java) run 2026-07-16."
  created_by: Borjan
  organization: 2Coders Studio
---

# Job Scout — setup interview / templater (one skill, N onboarded profiles)

Conversational onboarding in Claude Code. Turns a CV (or a guided Q&A) into a **validated,
Notion-provisioned profile** the `job-scout-run` skill can scan. Every step is
**scriptable/promptable** (Phase 4 constraint) — no step exists only as human prose; the
mechanical parts are real scripts (`core/provision_notion.py`, `core/writeback.py`,
`core/validate.py`, `core/scan.py`).

**Privacy invariant (D4/D6, non-negotiable):** the CV is **read to derive search config and
then forgotten — never written to the repo.** Only profile-schema facts (display name,
location, citizenship, eligibility, experience years, headline, tools, certs, domains) land
in `profile.yaml`. CV narrative, employers-as-history, email, phone, and any pitch/voice
material stay out of the repo entirely.

**Prime directive:** onboarding a new profile is purely additive. It never touches another
profile's config, state, or Notion. `borjan-pm` (and every existing profile) is untouched.

## The flow (run in order)

### 1. Kickoff
Ask for the **CV** (PDF or pasted text) plus any hard constraints the person already knows:
location, must-be-part-time, a salary floor **if** they have one, target seniority, target
role note. **CV is strongly preferred but not required (D16)** — with no CV, run a guided Q&A
that fills the same fields (less auto-tailoring, identical schema output).

### 2. Extract
Read the CV (or run the Q&A) into a structured extract held in-session only: titles, years,
tech/skills, domains, seniority signals, location, languages, eligibility. **Never write the
CV or the extract to the repo (D4).**

### 3. Classify → stream + subvariant
Map the extract to a **stream + primary subvariant** from the template library
(`templates/<stream>/<subvariant>.yaml`), and optionally a **secondary subvariant (D15)** when
the CV/goal genuinely spans two (keyword/archetype sets are unioned; the **primary** drives the
comp band + platform tiers). Clear match → confirm. Ambiguous/multi → present the top
candidates (use each template's `suggest_also`), let the person pick primary (+ optional
secondary). No match → nearest stream + generic subvariant, and **log a template-gap** (feeds
library growth). List templates with `ls templates/*/` and read the candidate ones.

### 4. Consent gate (write-back, D6)
Ask permission to stage **anonymized, generic** template enrichments for curator review
(`core/writeback.py`, staged to `suggestions/`). Record the answer as `writeback.consent`
(default **off**). Never stage CV/PII — the guard refuses it regardless.

### 5. Tailor (guardrails — D5)
Deep-merge the template defaults (primary; **union** primary+secondary keyword/archetype sets
for D15). Then apply CV enrichments **within guardrails**: you MAY reweight/select from the
template's keyword+archetype sets and add **CV-obvious concrete tech terms** (e.g. "Spring
Boot", "Kafka"); you MAY NOT invent new filter types or archetypes — those come from the
template. Set `target_seniority` (actual experience vs the level they want to *see* — these
differ for a post-break survey), `employment_type`, `work_model`, `fte_fraction` for part-time
(D22). **Comp: never fabricate a floor (D20)** — take it from the person if stated, else leave
unset for judgment-time estimation via the template's `salary_estimation_heuristics`.

### 6. Confirm interview (posture is the user's choice — D14)
First offer, with a friendly one-line explanation, a choice between **(a) progressive** (confirm
only high-impact / ambiguous fields, accept template defaults for the rest) and **(b) full
field-by-field**. Then run the chosen posture. Surface `target_seniority.strict` and the
`employment_type: any` escape explicitly. Never ask what a template default already answers
(spec §1 rule 2); lean on each template's `interview.emphasize` / `skip_if_defaulted`.

### 7. Provision → persist → validate
Write a **draft** `profiles/<id>/profile.yaml` with `output.notion: { dry_run: true }` so it
validates, then:
- **Provision Notion** — `python3 core/provision_notion.py --profile <id> --parent-page-id
  <uuid>` (token via the `core/secrets` seam → `NOTION_TOKEN` env; D11/D18). It creates the
  **Applications Tracker**, **Passed/Seen Log**, and **Runs page**, is **idempotent** (adopts
  existing by title under the parent — D19), and writes the real IDs into `output.notion`
  (dropping `dry_run`). **Access is instruct→verify-by-probe (D17):** if the integration can't
  reach the parent page, it tells the person to add the integration under the page's
  Connections and re-run — an honest manual step, never pretend-headless.
- **The saved "📥 New — Unreviewed" view** is NOT creatable via the Notion REST API (probed) —
  create it interactively via the Notion MCP `notion-create-view` tool (filter Passed/Seen Log
  → Reason Passed = "New — Unreviewed"), or instruct the person to add it and confirm. Never a
  silent skip.
- **Validate** — `python3 core/validate.py` (and `core/scan.py --profile <id> --plan`). Refuse
  to proceed on any error. Write `schedule:` config (cron **not** wired — D12).

### 8. First run
Offer `python3 core/scan.py --profile <id> --plan` (dry-run) then one live scan
(`core/scan.py --profile <id>`), and review the coverage ledger together via the
`job-scout-run` skill's judgment pass. Honest ledger — sources down are named, not hidden.

### 9. Write-back (if consented at step 4)
Extract **generic** enrichments (role-generic keyword/archetype additions — no PII) and stage
them with `core/writeback.stage_suggestions(...)` to `suggestions/<template>.yaml` for curator
review. Never CV text, names, employers, or PII (the guard enforces this).

## Notes
- The interview skill itself runs on a capable model (CV understanding + classification are
  reasoning-heavy) — separate from the profile's scan-time `run.effort`.
- Overlap between streams (data-engineer ∈ SE ∩ data; sales-engineer ∈ sales ∩ SE) is resolved
  by asking the person (step 3); templates may `suggest_also` their neighbors.
- Files: `core/provision_notion.py` (provision/adopt), `core/secrets.py` (token seam),
  `core/writeback.py` (staged suggestions), `core/profile_loader.py` + `core/validate.py`
  (strict validation), `templates/` (the library), `core/data/seniority_lexicon.yaml` (D21).
