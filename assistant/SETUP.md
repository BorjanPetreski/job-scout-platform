# Setup & binding — standing up a companion Project

Follow this once per profile to bind the Application Companion to a user's claude.ai Project. It
assumes the profile already has a provisioned Notion (the three databases from
`core/provision_notion.py`) — the same Notion the scanner writes.

Everything here is done **by the user / operator**; the companion runs entirely on claude.ai and
never reads this repo.

---

## 1. Compose the binding (in the repo)

```
python3 core/compose_assistant.py --profile <id>
```

This writes `profiles/<id>/assistant/project-instructions.md` — the generic package + a PII-free
snapshot of the profile's config (floor, eligibility, location/timezone, Notion `data_source_id`s)
stamped with a compose date + source-config hash. Re-run it after **any** `profile.yaml` change to
the floor, eligibility, location, or Notion IDs (the Project can't read the repo, so a stale
paste drifts silently).

## 2. Create the Claude Project

On claude.ai, create a new **Project** for this person's job search (e.g. "Job Applications —
<name>").

## 3. Paste the instructions

Open `profiles/<id>/assistant/project-instructions.md`, copy the whole file, and paste it into
the Project's **custom instructions**. (This is config + doctrine only — no CV, no PII.)

## 4. Upload the user's materials (per the data manifest)

Upload into **Project knowledge** the items in the profile's data manifest
(`profiles/<id>/assistant/data-manifest.md`), or — if the profile has none — the generic set
(CV, past application answers, a few writing samples). Respect the retention classes:

- **domain / both** docs → keep in Project knowledge.
- **voice-only** docs → the companion shreds them after extracting voice; don't leave them in
  knowledge afterward.

Nothing here is committed to the repo — the CV and personal materials live only in the Project
(the data principle).

## 5. Connect the Notion MCP

Connect the **Notion MCP** to the Project, authorized to the workspace holding this profile's
databases. Confirm the connection is live before working the queue.

## 6. Probe-read the queue

Ask the companion to read the profile's **`📥 New — Unreviewed`** view via the Notion MCP
(the Passed/Seen Log `data_source_id` is in the pasted snapshot). It should list the current
unreviewed roles. If it can't, the MCP isn't connected or lacks access to that database — fix
before continuing.

## 7. Verify the pinned status vocabulary exists ⟵ do not skip

The companion writes only exact select values (see `05-notion-write-contract.md`). Before the
first apply, confirm those options **already exist** in the profile's databases, so a write never
makes Notion silently mint a stray option the scanner won't recognize:

- **Passed/Seen Log → `Reason Passed`** must include: `New — Unreviewed`, `Stale/Expired`,
  `Filtered Out`, `Duplicate Listing`, `User Declined`, `User Applied Elsewhere`,
  `Unverified/Blocked`.
  *(These are `provision_notion.py` `REASON_OPTIONS` — a provisioned DB has them all.)*
- **Applications Tracker → `Status`** must include: `Applied`, `Screening`, `Interview`,
  `Offer`, `Rejected`, `Withdrawn`. **`Source`** must include `Claude Skill Scan`,
  `Manual Entry`.

Have the companion read each database's schema via the Notion MCP and confirm the options are
present. If any are missing, the database wasn't provisioned by `core/provision_notion.py` (or
was edited) — re-provision/adopt rather than letting the companion create the option ad hoc. A
genuinely new label is a provisioning decision (add it to `provision_notion.REASON_OPTIONS` +
`notion_sync.VALID_REASONS` first), never an ad-hoc MCP write.

## 8. (Optional) confirm the saved view exists

The scanner's contract expects a **`📥 New — Unreviewed`** filtered view on the Passed/Seen Log
(`Reason Passed = New — Unreviewed`). `core/provision_notion.py` prints a manual instruction for
this (the REST API can't create saved views); the companion can create it via the Notion MCP
`notion-create-view` tool, then confirm it exists.

---

## Then: build voice + KB, and work the loop

- Build the voice profile and seed the knowledge base with the companion (§ `02`/`03`). Prove the
  persistence round-trip with **`DRY-RUN.md`** before the first real application.
- Work the `📥 New — Unreviewed` queue role by role (§ `04`): re-verify → decide → draft in voice
  → record. Recording (Tracker row + Passed/Seen flip) is what lets the next scanner run dedup
  the role.

## Re-compose triggers (keep the snapshot honest)

Re-run step 1 and re-paste whenever the profile's **salary floor, eligibility, location, or
Notion `data_source_id`s** change. The companion announces its compose date at the start of a
session; if it's older than the last `profile.yaml` change, re-compose.
