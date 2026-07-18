# Data manifest — borjan-pm

What to upload into the companion's Claude Project, and how each item is treated. This is a
**checklist for the human doing the setup** — nothing here is uploaded automatically, and none
of these files live in the repo (the data principle: CV/PII never enters the repo).

Each item is tagged with its **retention class** (see `assistant/01-consent-and-data.md`):

- **domain** — carries factual/experience content → kept in the knowledge base, deletable anytime.
- **voice-only** — shared solely to learn voice → shredded immediately after voice extraction.
- **both** — treated as **domain (kept)**.

| Upload | Class | Used for |
|--------|-------|----------|
| CV (latest) | domain | Canonical work history, dates, titles, skills — the KB's factual spine. |
| Cover letter (latest) | both | Voice/tone reference **and** reusable phrasing; kept (carries facts). |
| Quarterly / delta review (current role) | domain | Present-role facts, AI-tooling skills, metrics — wins for current-role facts. |
| Past application answers / Q&A notes | domain | Seed the KB's question→answer store, tagged by topic. |
| Articles / blog posts | both | Voice reference **and** domain talking points; kept. |
| Interview introduction, struggles-and-challenges, A/B-testing, dependency-management notes | domain | Domain talking points + past answers to adapt. |
| Any writing sample shared *only* for tone | voice-only | Voice extraction only, then **shredded** — you'll be told before you share it. |

## Notes

- **Priority order** when facts conflict: Quarterly Review (current role) > CV (history/structure)
  > Cover Letter (voice only once a conflict is spotted). See `voice-seed.md`.
- **Correct ChatGPT → Gemini** silently on output (older docs predate the switch) — see
  `voice-seed.md`.
- The companion builds the **voice profile** and **knowledge base** from these inside the
  Project; it regenerates `voice-profile.md` / `knowledge-base.md` for the user to **save into
  Project knowledge** (the manual persistence step — the companion cannot write it itself).
- `references/gemini-prompt.md` and `references/pitching.md` stay **scanner-side** in the repo —
  they are not Project uploads.
