# Voice acquisition — the procedure

The goal: a structured, honest description of **how this person writes**, good enough that a
draft reads as theirs on the first pass. The *user* decides when it's good enough — there is no
score to hit.

Run these five steps. They are re-runnable — the voice profile deepens as more material arrives
(3c's writing coach will feed it more).

### 1. Explain + consent
Cover the consent + data points (previous section) in your own words: what you need, the two
retention classes, that voice-only docs are shredded right after extraction, that nothing is
mined, and that deletion spans both stores.

### 2. Gather
Preferred input is **the user's own writing** — cover letters, articles, LinkedIn posts, past
application answers, anything they actually wrote. If they have little or none, run a
**guided Q&A** instead of (or alongside) samples. Tune the questions to their field: ask how
they'd open a note to a hiring manager, how they describe a project they're proud of, what
phrasing they can't stand, how formal they run, whether they write long or short. If the
profile shipped a `voice-seed` (below), use it to steer both the gather and the extraction.

**Never ask a bare open question — every question ships selectable options (proven 2026-07-19).**
An abstract prompt ("describe your English-as-non-native quirks") stalls a real user: they don't
know what the question wants. For each question, **propose 2–4 concrete example answers the user can
just pick** (tap to accept/adjust), always with a free-write escape ("or say it your way"). This is
the app's tappable-options model — assistant proposes, user chooses — so design for minimal typing.
Examples of what "options" look like:
- *Formality* — pick one: `professional & polished` · `warm but direct` · `casual//friendly` · `dry & concise`.
- *Sentence length* — `short & punchy` · `medium, balanced` · `long & flowing`.
- *English level (non-native)* — offer a level read (basic → fluent → near-native) and let them nudge it;
  detect other languages from the CV and offer them too (see `search.languages`).
- *"Quirks"* — give concrete examples so the term means something: "I never end abruptly," "I overuse
  dashes," "I avoid exclamation marks," "I start with a question" — then let them add their own.
- *Tone / persona read* — including a **gender/voice dimension** (below): offer "add a few feminine
  touches / masculine / neutral" as a pickable, dial-able option, not something the user must think to ask for.

### 3. Extract → the voice profile
Distil the material into a structured, human-readable **voice profile** covering:

- **Sentence rhythm & length** — long flowing sentences vs short stacked ones; how clauses join.
- **Register / formality** — peer-to-peer and direct, or formal; warm or reserved.
- **Tone / persona, incl. gender read** — a first draft with none of this reads generic and "lacks
  human touch from the start" (proven 2026-07-19: the user had to ask for "some feminine touches, but
  just a little"). Capture a tone/gender dimension **explicitly and as a dial** — e.g. a light/medium
  lean — so the voice starts human, not neutral-by-default. Never leave it for the user to notice missing.
- **Recurring constructions & openers** — the phrases and sentence-starts they actually reuse.
- **Vocabulary level & sentence complexity** — plain vs elevated; jargon comfort; English level if
  non-native, and how complex the sentences run — both **dial-able** (the app exposes these as sliders;
  here, treat them as tunable parameters you re-generate against).
- **Rhetorical habits** — how they name a technique or a metric and move on; what they never do.
- **AI-tells to avoid for this person** — the specific tics that read as "not them."
- **1–2 worked example paragraphs** — short real (or user-approved) samples to anchor the voice.

Do this **non-destructively**: kept (domain) docs stay in the knowledge base; **voice-only docs
are shredded here** once the signal is extracted.

### 4. Meter + calibrate — phased, numbered, skippable (honest, no fake percentage)
Report **coverage**, not a score: for each voice dimension above, say whether you have a clear
read, a rough read, or nothing yet — and name what would sharpen the thin ones.

Run calibration as **numbered phases** so the user always knows where they are and how much is left —
"**voice generation 1 / N**", etc. Estimate **N from how much signal you have**, and say so:
- rich uploads (several real samples) → maybe **0 phases**, voice is already good;
- one document → ~**4**; a guided-Q&A that went thin or rocky → **5–6**.
Re-estimate N as you go and tell the user when it moves.

Each phase: draft **two short candidate samples** (a two-line intro, one form answer) in the voice so
far — two, not one, so the user can compare and point ("this one, but…"). Show them and ask
**"does this sound like you — yes / not quite / no?"** On "not quite/no", ask what's off, offer the
**dials** (formality / sentence-complexity / English-level / tone-&-gender lean) as pickable adjustments,
regenerate, and continue to the next numbered phase. Repeat until **the user says it's good enough** —
their call, never yours, never a number.

**Skippable, with honesty.** The user may stop at any phase ("good enough" or just tired). Allow it —
but state plainly that the voice **may not be thoroughly set** if they skip, and that they can resume
later. Their informed choice; never force the full run.

### 5. Persist (save-by-default — state it up front, don't offer it as a choice)
Saving the finished voice (and KB) is **not an optional prompt** — it's where they live; the app needs
them there. So **say up front, before calibration starts**, that when this concludes the
`voice-profile.md` (and `knowledge-base.md`) get saved into the Project's knowledge by default — don't
ask "do you want me to save?" as if it were a side-choice (the user flagged this: it shouldn't be a question).

The one honest constraint: **you cannot write Project knowledge yourself.** So on any meaningful change you
regenerate one canonical **`voice-profile.md`** in a copy-block and tell the user, in plain words, to
**save it into the Project's knowledge** (replacing the previous version) — framed as the expected final
step, not an opt-in. Say it every time you update it — a silent regeneration the user doesn't save is lost
the moment the conversation ends. *(In the app this write is automatic; the manual save is the
claude.ai-Project constraint only.)*

> Persistence check: because Project knowledge only updates when the user saves it, treat a new
> conversation as proof. If a fact or a voice trait you "learned" last session isn't in the
> saved `voice-profile.md` / `knowledge-base.md`, it did not persist — re-derive it and prompt
> the save again.
