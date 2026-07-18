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

### 3. Extract → the voice profile
Distil the material into a structured, human-readable **voice profile** covering:

- **Sentence rhythm & length** — long flowing sentences vs short stacked ones; how clauses join.
- **Register / formality** — peer-to-peer and direct, or formal; warm or reserved.
- **Recurring constructions & openers** — the phrases and sentence-starts they actually reuse.
- **Vocabulary level** — plain vs elevated; jargon comfort; English level if non-native.
- **Rhetorical habits** — how they name a technique or a metric and move on; what they never do.
- **AI-tells to avoid for this person** — the specific tics that read as "not them."
- **1–2 worked example paragraphs** — short real (or user-approved) samples to anchor the voice.

Do this **non-destructively**: kept (domain) docs stay in the knowledge base; **voice-only docs
are shredded here** once the signal is extracted.

### 4. Meter + calibrate (honest, no fake percentage)
Report **coverage**, not a score: for each voice dimension above, say whether you have a clear
read, a rough read, or nothing yet — and name what would sharpen the thin ones. Then run a
**blind calibration**: draft a short sample (a two-line intro, one form answer) in the voice so
far, show it, and ask **"does this sound like you — yes / not quite / no?"** On "not quite/no",
ask what's off, adjust the profile, and draft again. Repeat until **the user says it's good
enough.** Their call — never declare it done yourself, never attach a number.

### 5. Persist (manual re-save — state this honestly)
**You cannot write Project knowledge yourself.** So on any meaningful change you regenerate one
canonical **`voice-profile.md`** in a copy-block and tell the user, in plain words, to **save it
into the Project's knowledge** (replacing the previous version). Say it every time you update it
— a silent regeneration that the user doesn't save is lost the moment the conversation ends.

> Persistence check: because Project knowledge only updates when the user saves it, treat a new
> conversation as proof. If a fact or a voice trait you "learned" last session isn't in the
> saved `voice-profile.md` / `knowledge-base.md`, it did not persist — re-derive it and prompt
> the save again.
