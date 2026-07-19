# The apply loop — per role, user-paced

Work the shortlist one role at a time, at the user's pace. Draw on the voice profile and the
knowledge base throughout.

### 1. Read the queue
Query the profile's **`📥 New — Unreviewed`** view in the Passed/Seen Log via the Notion MCP.
Present the roles; let the user pick one or go top-down. Do a single bulk read at the start
(the queue plus the Tracker for prior-history, below) rather than re-querying per role.

### 2. Present + surface prior history
Show the role and its notes. **Always include the posting's clickable URL** — the user must be able
to open it in a browser without asking (proven 2026-07-19: a role was surfaced with no link). Never
present a role without its link.

If the company appears elsewhere in the Tracker or Passed/Seen Log, surface the prior requisitions and
their status ("they also have DM-Warszawa, which you applied to") — read from Notion, so the user never
has to ask "did I already go for a variant of this?"

### 3. Re-verify (mandatory — never skip)
**Fetch the posting URL** and re-check the hard facts against the profile snapshot:

- still live?
- eligibility (location / remote-region / visa) — a fit for this profile?
- hours / part-time vs full-time?
- salary (against the floor in the snapshot, or judgment estimation if floorless)?
- employment type (B2B / contract / full-time)?

On a **JS / login / thin wall** where you can't read the posting, **ask the user to paste or
confirm** the facts — don't guess. If the posting is **dead**, set the row to `Stale/Expired`
(see the write contract) and move on. **Never draft against an unverified posting.**

### 4. Decide — offer the next step as explicit options
Advise apply or pass with a clear, honest read; **the user decides.** Respect the profile's
constraints (eligibility, employment type, floor) but surface, don't silently drop — the
scanner already filtered the machine-certain cases.

Present "how do you want to proceed?" as **explicit, pickable options that map to a Notion status**,
not an open prose question (the app renders these as buttons/taps):
- **Apply** → draft (step 5), then create the `Applied` Tracker row + flip → `User Applied Elsewhere`.
- **Pass / not for me** → flip → `User Declined` (capture the real reason).
- **Dead / expired** → flip → `Stale/Expired`.
- **Skip for now** → leave `New — Unreviewed`, move on.

Each choice writes the matching pinned status (step 6) — the tap *is* the record, no free-text status.

### 5. Draft in voice (on apply)
Produce the cover letter / email pitch / form answers, applying the **voice profile on the
first draft** and sourcing every factual claim from the **knowledge base** with the honest-answer
+ growth loop. Gate the closing on the posting's real employment type (see voice/delivery
discipline). Every submittable text goes in its own **copy-block**; analysis stays outside it.

### 6. Record
- **On "applied":** create the **Applied** Tracker row (with the submitted answers in the row
  body), and flip the Passed/Seen row from `New — Unreviewed` → **`User Applied Elsewhere`**.
- **On "pass":** flip the Passed/Seen row → **`User Declined`** with the user's real reason.

Both use the exact pinned vocabulary (see the write contract). Recording is what lets the next
scan dedup the role.

### 7. Next role
Move on at the user's pace.
