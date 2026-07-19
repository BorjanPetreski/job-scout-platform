# Guided Flow — the curated prompt library (the app's golden path)

> **Living library.** Every meaningful interaction with the platform is, underneath, a
> **curated, battle-tested prompt**. Today those prompts are pasted by hand (during dogfooding
> and QA); in **Phase 4** the app wraps them so the user sees a **simple action** — a button, a
> plain question, "Next", "Yes" — and that action fires the tuned prompt **in the background**.
> The prompt is the unit of interaction; the UI is a thin trigger over it.
>
> **This file is the source of those prompts — current, retroactive, and future.** It is kept
> current as a standing rule (PROJECT_PLAN §4): whenever a step is dogfooded and its prompt is
> tuned, capture it here. Phase 4 wires UI triggers to these entries instead of re-inventing them.

## How to read an entry

**Action** = what the user does in the (future) app · **Prompt** = the curated text run in the
background · **Drives** = the skill/script it invokes · **Maturity**: ✅ tuned (proven in
QA/dogfood) · 📋 canonical (from a shipped skill, not yet UI-tuned) · 🔮 future (phase not built).

Placeholders in `[brackets]` are filled by the app from context (the active profile, a URL, a
pasted JD) — the user never types them.

---

## Stage A — Onboarding a new profile  ·  Phase 2 · `job-scout-setup`

### A1. Start onboarding — 📋
```
Onboard me for job scouting. Here is my CV: [attach CV]. Constraints I already know:
location [city, country]; employment [full-time / part-time / contract / any]; salary floor
[amount + currency, or "none"]; target seniority [junior/mid/senior/lead]; target roles/streams
[e.g. backend engineering, delivery management]. Read the CV to derive my config, never store it
in the repo, and walk me through setup.
```
No-CV variant — append: `I don't have a CV — run the guided Q&A instead.`

### A2. Approve the classification — 📋
```
[Yes, that stream/subvariant is right] — continue.   (or: Actually I'm closer to [stream]; re-classify.)
```

### A3. Write-back consent — 📋
```
[Opt me in / Keep me out] of the anonymous generic-term write-back.
```

### A4. Choose interview posture — 📋
```
Do the [progressive / full] setup interview.
```

### A5. Provision Notion + first scan — 📋
```
Provision my Notion databases under [parent page], validate my profile, and run my first scan.
```

---

## Stage B — Scanning & tracking  ·  Phase 1 · `job-scout-run`

### B1. Run a scan (attended, full scored) — ✅
```
Run a full job scan for [profile] using the job-scout-run skill. Pull state first, run the full
rotation with --verbose, then do the judgment pass: score and archetype-tag every candidate against
my filters and filter_notes, shortlist everything at/above my surface threshold, and log each
decision to seen.jsonl. Push the shortlist to my Notion Passed/Seen Log as "New — Unreviewed" with
role notes in the page body, run the shortlist sweep + the Tracker reconciliation, append the
digest line, then push state. Give me the coverage ledger plus the shortlisted roles.
```
> Runs in the repo-aware Claude session (laptop lane), NOT the companion Project — the scanner and
> the companion are separate contexts bridged only by Notion.

### B2. Run a scan (unattended / scheduled) — ✅
```
Run the scheduled job scan for [profile] per skills/job-scout-run/SKILL.md. Unattended mode.
```

### B3. Watch a run live (CLI) — ✅
```
python3 core/scan.py --profile [profile] --verbose
```

### B4. "I applied" (chat fallback → Tracker) — 📋
```
I applied to [url]. Record it in my Applications Tracker.
```

### B5. "I'm passing" on a shortlisted role — 📋
```
I'm passing on [role/url] — reason: [reason]. Flip its Passed/Seen row to User Declined.
```

### B6. Assess a pasted JD — 📋
```
Assess this job for [profile] — problem it solves, my fit, and any red flags: [paste JD].
```

### B7. Draft a pitch / cover letter (Code-lane pitch router) — 📋
```
Draft a [cover letter / hiring-manager email] for [role/url] in my voice. Here's the JD: [paste].
```

### B8. Reconcile applied roles into local state (CLI) — ✅
```
python3 core/notion_sync.py --profile [profile] --reconcile
```
> Now emits `{tracker, resolutions}`: back-fills `applied` from the Tracker (#8/#11) AND reads
> Passed/Seen resolutions (Declined/Filtered/Stale) back into local state (#13), so a
> Notion-resolved row stops looking `shortlisted` locally. Read-only on Notion, idempotent.

### B9. Run several profiles in parallel (operator, staggered) — ✅ *(dogfooded 2026-07-19: borjan-pm + ani-backend-java concurrently, clean isolation, validate green)*
```
Run a full scored scan for [profile-1] and [profile-2] concurrently — one subagent per profile,
each running the job-scout-run skill end-to-end for its OWN profile only (pull state → scan
--verbose → judgment score/tag → push shortlist to that profile's Notion → sweep + reconcile).
Stagger the scan starts by ~60s to be polite to shared job boards. Each subagent touches only its
own profiles/<id>/state and Notion. When both finish, run python3 core/validate.py and report, per
profile: shortlist count + fit scores, the tracker/resolutions reconcile counters, and any
rate-limited/403 host. Do NOT commit state — leave the run artifacts in the working tree.
```
> Operator lane (repo-aware Claude session), not the companion Project. Profiles never share state,
> so parallel is isolation-safe; at scale give each concurrent run its own scratch dir (Phase 5).

---

## Stage C — Companion binding & verification  ·  Phase 3a · claude.ai Project

### C1. Confirm the doctrine loaded — ✅
```
Do you have project-instructions.md in your knowledge? If so, confirm you can see the
consent/retention section and the apply loop, then walk me through consent and the two document
retention classes.
```

### C2. Probe-read the queue — ✅
```
Read my "📥 New — Unreviewed" view in the Passed/Seen Log via the Notion MCP (the data_source_id
is in your snapshot). List company, title, and Reason Passed for each row, and how many there are.
Don't score or draft anything yet.
```

### C3. Verify the pinned vocabulary — ✅
```
Using the Notion MCP, read the schema of both databases and confirm these exact select options
exist, listing any missing:
- Passed/Seen Log → "Reason Passed": New — Unreviewed, Stale/Expired, Filtered Out,
  Duplicate Listing, User Declined, User Applied Elsewhere, Unverified/Blocked
- Applications Tracker → "Status": Applied, Screening, Interview, Offer, Rejected, Withdrawn;
  and "Source": Claude Skill Scan, Manual Entry
```

---

## Stage D — Companion: voice + knowledge base  ·  Phase 3a

### D1. Build the drafting voice — ✅
```
Let's build my application-drafting voice profile. Pull from the writing I uploaded plus the
voice-seed in your instructions. Give me a coverage read (not a score) of what you've got and
what's thin, then draft ONE short application-style sample so I can judge "me / not quite / no".
We'll iterate until I say it's good enough, then you regenerate voice-profile.md for me to save
into Project knowledge.
```

### D2. Recalibrate / deepen voice later — ✅
```
Re-open my voice profile. Here's more of my writing: [attach]. Update it, show me what changed,
draft a fresh blind sample, and regenerate voice-profile.md for me to re-save.
```

### D3. Knowledge-base growth (honest-answer loop) — ✅
```
When you hit a question you can't answer from what I've given you, say so plainly, name the
nearest real adjacent experience if any, and ask me. When I answer, tighten it into an honest
reusable entry and regenerate knowledge-base.md for me to save.
```

> **Manual persistence (state it every time):** the companion cannot write Project knowledge
> itself — on any change it regenerates `voice-profile.md` / `knowledge-base.md` and the **user
> saves the file into Project knowledge**. Unsaved = not persisted (a fresh conversation is the proof).

---

## Stage E — Companion: the apply loop  ·  Phase 3a

### E1. Work a role — pull + prior-history cross-check — ✅ *(caught a real duplicate in QA)*
```
Work my "📥 New — Unreviewed" queue — pull [company — role] (or the top role). BEFORE anything
else, cross-check its Job URL against BOTH my Applications Tracker and Passed/Seen Log and surface
any prior history: if I've already applied (a Tracker row with the same URL), tell me plainly —
don't treat it as fresh and don't create a duplicate Tracker row. Surface prior reqs from the same
company too.
```
> Why this matters: in QA this caught a role already applied to 8 days ago whose Passed/Seen row
> had never been flipped out of `New — Unreviewed` — preventing a wasted re-application. The
> prior-history cross-check is the companion's dedup safety net on top of the scanner's.

### E2. Re-verify + recommend (don't draft yet) — ✅
```
Re-verify this posting before we draft: fetch the URL and check against my snapshot — still live?
eligible (worldwide/EMEA-remote for me, no visa/citizenship clause)? hours? employment type (drives
the closing gate — the contractor angle only if it's freelance/contract/B2B)? salary vs my floor
(flag if unpublished)? If you can't read it, tell me and I'll paste the JD: [paste]. **If you can
reach the actual application form, check it too — its location dropdown / language / required
fields are ground truth over the JD's marketing copy and often reveal hidden eligibility misses.**
Then give me the verification read + an apply/pass recommendation. Do NOT draft yet.
```
> Proven in acceptance: the *form* caught a Poland-only location dropdown + a German-language field
> on a role the JD badged "Remote" with no such requirements — the form wins over the JD.

### E3. Draft on apply — 📋 *(pending live confirmation)*
```
I want to apply. Draft the cover letter / email / form answers in my voice, from my knowledge
base, honest about any gaps, each submittable in its own copy-block.
```

### E4. Record — applied — ✅ *(flip-half proven on OSF; Tracker-create pending a fresh role)*
```
I applied to this one. Create the Applied Tracker row (my submitted answers in the body) and flip
the Passed/Seen row to "User Applied Elsewhere". If a Tracker row with this Job URL already exists,
do NOT duplicate it — just flip the Passed/Seen row.
```

### E5. Record — declined — ✅ *(proven: Britenet, 3-reason decline, no Tracker row)*
```
I'm passing on this — reason: [reason]. Flip the Passed/Seen row to "User Declined" with that
reason (dated note). Do NOT create a Tracker row — a decline isn't an application.
```

### E6. Mark a dead posting — 📋 *(pending live confirmation)*
```
This posting is dead/expired — I checked. Flip its Passed/Seen row to "Stale/Expired" with a dated note.
```

---

## Stage F — Future (capture as each phase is built)

### F1. Interview lifecycle — 🔮 Phase 3b
```
I got an interview for [role]. Read the JD, predict likely questions, and map my real experience
onto the role's gaps.
```
```
Debrief my interview: [notes on how it went]. Give me honest feedback and store what to fix.
```
```
Here's a status email I got: [paste]. Flip the role's Tracker status accordingly.
```

### F2. CV doctor + writing coach — 🔮 Phase 3c
```
Review my CV — is it current, where is it stale (>6 months), and what should I sharpen?
```
```
Co-write a [blog post / article] about [topic] in my voice — it should strengthen my candidacy
and feed my voice + knowledge base.
```

### F3. Integrations — 🔮 Phase 5
Email OAuth auto-ingest (status flips from real emails) and LinkedIn *export* ingest — replace the
paste steps (B4/F1's paste-an-email) with automated capture.

---

## Maintenance (standing rule)

- **Fold each tuned prompt in the moment the step is *proven*, not batched at the end**
  (standing cadence, Borjan 2026-07-18): capture per proven step in its own small PR — a long
  session can be stopped at any time, so never let proven prompts sit un-banked in chat. Capture
  when proven (not while still a draft), then mark ✅.
- **Keep prompts app-ready:** context values in `[brackets]`, one clear action each, no repo-path
  assumptions the app can't satisfy (Stage-B CLI entries are the exception — they're operator
  tools until Phase 4 wraps them).
- **Phase 4 wires UI triggers to these entries** — the button/label is the Action; the background
  call is the Prompt. Treat each entry as a versioned asset.
