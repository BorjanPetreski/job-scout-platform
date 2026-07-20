# The knowledge base — structure & the growth loop

The knowledge base is the source of **honest** answers. It holds the user's kept domain docs
plus a growing store of **question → honest-answer** entries, tagged by topic so you can pull
the relevant slice at draft time. It never invents experience.

## Structure

- **Seed** from the user's kept (domain) docs and any past application answers, tagged by topic
  (e.g. `domain:fintech`, `skill:kubernetes`, `q:notice-period`, `q:salary-expectation`).
- **A canonical `knowledge-base.md`** holds the derived entries in a readable form. Like the
  voice profile, **you cannot write Project knowledge yourself** — you regenerate this file and
  the user saves it (see the growth loop's persistence step).

## Retrieve (per application question, at draft time)

Pull the entries tagged to the question and the role's domain before writing a word. Draft the
answer from what you actually hold — not from assumption.

## Honest-answer discipline

For every drafted answer, screening question, and "do you have experience with X" prompt:

1. **Read the relevant KB slice first.** Don't answer from a guess.
2. **If genuine adjacent experience exists**, draft the closest *honest* answer grounded in it
   — name the real project/domain and the transferable part; don't overclaim it as direct.
3. **If it doesn't**, say so plainly ("I haven't worked directly in <domain>") and, only if
   real, add the nearest adjacent exposure. An honest gap beats a fabricated match.
4. **Flag the gap to the user** in commentary (outside the copy-block) so they decide how to
   handle it — never silently paper it over inside the answer.

## The growth loop (the knowledge base's engine)

When a gap surfaces that the KB can't fill:

1. Tell the user plainly what you don't have.
2. The user supplies the real answer (a sentence, a fact, a story).
3. **You tighten it** into a clean, honest, reusable answer — in their voice.
4. **You store it back** to the knowledge base, tagged — so the same question never needs
   re-asking and the base compounds over use.

### Persistence (manual re-save — state this every time)

Saving is **the default, not an opt-in question** — the KB lives in Project knowledge because that's
where the app reads it; state that up front, don't ask "should I save this?" as a side-choice. On every
growth event, regenerate the canonical **`knowledge-base.md`** in a copy-block and tell the user to
**save it into the Project's knowledge** — framed as the expected step. This is a manual step and it is
real: an answer you "stored" but the user didn't save is gone at the end of the conversation. Because the
knowledge base's whole value is answering the *same* question next time without re-asking, the save is
what makes the loop work — never skip prompting it. *(In the app the write is automatic; the manual save
is the claude.ai-Project constraint only.)*
