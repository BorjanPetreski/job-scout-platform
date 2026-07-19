# Ani — first companion run: feedback capture & backlog

Source: Borjan's dogfood of the `ani-backend-java` companion (Part B, 2026-07-19), running the
no-voice-seed guided-Q&A path end-to-end on Cowork. This file banks every observation so nothing
evaporates between sessions. **Status legend:** ✅ done · 🔜 next PR (companion doctrine) · 🗺️ roadmap (app).

---

## 1. Scanner leak — ✅ FIXED this session (see PROGRESS 2026-07-19)

**Symptom:** full-time, Polish-language, and hybrid (on-site-days) roles reached Ani's
`📥 New — Unreviewed` shortlist despite her profile declaring remote-only + part-time. "Something is
leaking somewhere… how did they get into New — Unreviewed?"

**Root cause (forensics on the real 319-candidate run):**
- `work_model: [remote]` was **declared but unenforced** — 168/319 candidates carried `(hybrid)` in
  their loc tag, but no detector read `work_model` against it. The `filter_notes` *documented* the
  lesson but it was never wired to code.
- Full-time-on-B2B was **swallowed** — `detect_employment` found `full_time`, but the off-target test
  `not (detected & accept)` let it pass whenever `contract`/`b2b` co-occurred (36 roles). Time-commitment
  and contract-vehicle are orthogonal; "Full-time B2B" is full-time HOURS.
- Polish detection worked on full JDs but **leaked via JD-less dedup twins** (title-only, no detection)
  and **title-only Polish** ("bankowość", "z praktyką").
- The judgment-layer skill then **shortlisted flagged candidates on fit alone** (issue #4).

**Fix (profile-gated, borjan-pm byte-identical — resolved-config hash verified unchanged):**
- `core/scan.py`: `detect_work_arrangement(loc, jd)` (structured loc tag authoritative) + part-time guard
  in employment detection + title-level Polish fallback.
- New opt-in `hard_filters.work_arrangement: [off|flag|drop]` and `employment_mismatch: [flag|drop]`.
  `drop` mechanically Filters Out the machine-certain hard-eligibility misses (hybrid-when-remote,
  full-time-when-part-time) BEFORE they reach the shortlist — the same class as `us_only`. Ani opts into
  `drop`; borjan-pm (which also declares remote) is untouched because it doesn't set the toggles.
- Skill doctrine (`skills/job-scout-run` → 4.5.0): documents the new flag + drop modes and hardens the
  "resolve EVERY flag before shortlisting" rule.
- Replay over the real run: 190/319 now drop (168 hybrid + 22 full-time), genuinely-remote roles kept.

**Residual (acceptable, conservative):** a genuinely-remote JD-less twin whose hours are unknown still
survives for judgment (we can't machine-certify full-time without the JD). The companion re-verifies the
live posting anyway (form is ground truth).

---

## 2. Companion doctrine — ✅ FOLDED 2026-07-19 (generic `assistant/` modules + recomposed bindings)

Folded into `02-voice-acquisition.md` (selectable options + worked examples, explicit tone/gender dial,
sentence-complexity/English-level dials, numbered+skippable phased generation with N estimated from input
richness, two-samples-per-phase, save-by-default), `03-knowledge-base.md` (save-by-default), and
`04-apply-loop.md` (always-clickable-link, proceed-as-explicit-options → Notion status). Both bindings
recomposed. The list below is the record of what was proven-by-failure in the live run.

- **Voice Q&A needs worked examples + selectable options.** "English-as-non-native quirks" meant nothing
  without examples. Every guided question should ship 2–4 concrete example answers the user can pick, with
  a free-write escape. Design for Gen-Z/Alpha: assistant proposes, user taps to accept/adjust.
- **Add a gender / feminine-touch dial.** The first samples "lacked human touch from the start" and sounded
  generic until Borjan asked for "some feminine touches, but just a little." Voice acquisition must capture a
  gender/tone dimension explicitly, not leave it to the user to notice it's missing.
- **English-level & sentence-complexity as explicit dials** (sliders in-app; explicit tunable parameters in
  doctrine now). Offer the English-level gauge at the *start* of voice acquisition (and detect other
  languages from the CV), then re-offer at each sample-tuning step.
- **Phased voice generation, numbered and skippable.** "Voice generation 1/4 → two samples → tune → 2/4…".
  N estimated from input richness: enough docs → maybe 0 phases; one doc → ~4; poor initial Q&A → 5–6.
  Skippable at any point with an **honest warning** ("voice may not be thoroughly set") — the user's call.
- **Two-samples-then-tune loop** as explicit doctrine (Borjan liked getting two candidate samples to compare).
- **Save is NOT an optional prompt.** Cowork asked "save voice/KB to folder?" — it shouldn't ask. Voice + KB
  land in Project knowledge (the app's store) by default at calibration end; the assistant states this up front.
- **Apply loop MUST always emit a clickable posting link.** A role was surfaced with no link to open in a
  browser. Never present a role without its clickable URL.
- **"How do you want to proceed" = explicit options** that map to pinned Notion statuses (apply / decline /
  stale / skip), so the choice is a tap that writes the right status — not free prose.

## 3. App / UX — 🗺️ roadmap (product build, no engine change yet; → PROJECT_PLAN Phase 5/6)

Simple, tappable interface aimed at Gen-Z/Alpha (minimal typing):
- **Sliders:** English level (Claude-effort style), sentence complexity, formality (professional↔informal).
  Reused at voice-gauge time and at each sample-tuning step to re-generate.
- **KB editing by tap:** confirm an entry (e.g. a skill); slider for self-assessed skill level (pre-set by the
  assistant); tap to remove; tap to add/extend a skill with assistant-suggested related options.
- **Salary field:** number + net/gross toggle + monthly/hourly + currency ($/€ enough for now). Gross↔net via
  country estimates/calculator (an LLM/API ping — Cowork already demonstrated this).
- **Proceed actions** as buttons that write the Notion/db status directly.

## 4. Portability signal (Part C)

The guided-Q&A path DID build a non-Borjan voice and a coherent KB from scratch — portability is trending pass.
The gaps above are UX/doctrine polish, not a package-is-Borjan-shaped failure. The apply loop surfaced the
scanner leak, now fixed. Remaining Part-C proof: voice+KB survive a fresh conversation (save round-trip) and the
apply loop runs clean on the de-leaked shortlist.

---

## 5. Enforcement-coverage audit + balance — 🔜 next session (Borjan, 2026-07-19)

**Scope beyond the two params already fixed.** Audit EVERY constraint a profile declares
(current: `regions_acceptable`, `target_seniority` strict, `citizenship`, `timezone_window`,
salary floor, `tool_lockin`, work_model, employment_type, …) AND plan for params a user may add
at onboarding that the app doesn't ship — the scanner should machine-drop the straightforward
ones. Close every "declared but only flagged / not enforced" gap.

**Balance — do NOT overconstrain (critical).** Hard drops can silently zero the results.
- **Diagnose Borjan's last scan: it returned 0 new — find WHICH param(s) dropped everything and
  why.** (This session earlier noted borjan's parallel run was 0 for "legitimate" reasons —
  re-verify that's true and not a leak-in-reverse / over-drop.)
- **Add drop-telemetry + a user nudge:** track per-param drop counts each run; when one param
  drops a large share (e.g. 280 of 300 found), surface it — "parameter_x dropped 280/300; consider
  relaxing this hard drop." Never let a single hard filter annihilate the funnel silently.

**Language rule — generalize (don't hardcode Polish/English).** Current fix flags/drops "Polish".
Reframe as: drop a posting whose **main language is not among the user's set languages**. The user
sets a language list (e.g. primary German, secondary English) — keep postings in ANY of those,
drop the rest. English is just Borjan's default, not the rule. Detection must be language-agnostic
(the `_PL_MARKERS`/`_EN_SIGNAL` approach must generalize to a configurable per-profile language set).
