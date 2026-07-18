# Voice + knowledge-base dry-run (the persistence round-trip)

A concrete, follow-along script that exercises the **voice meter** (§ `02-voice-acquisition.md`)
and the **knowledge-base growth loop** (§ `03-knowledge-base.md`) **end-to-end, with no live
application yet** — and proves the one thing a single-conversation demo can't: that voice and KB
**persist across separate conversations** via the manual re-save mechanic.

**Why two conversations.** The companion cannot write Project knowledge itself. It regenerates a
canonical `voice-profile.md` / `knowledge-base.md`; the **user** saves them into Project
knowledge. A single-conversation dry-run would "remember" everything from context and pass
without ever exercising the save. So the proof is: build in **Conversation 1**, save, then start
a **brand-new Conversation 2** and confirm the companion still has the voice and the grown answer
— which is only possible if the save happened. If Conversation 2 has lost them, the persistence
mechanic failed, not the model.

---

## Conversation 1 — build, then save

### A. Consent
The companion explains, in its own words: what it needs and why, the two document retention
classes (domain = kept; voice-only = shredded after extraction), that nothing is mined, and that
deletion spans **both** stores (Project + Notion bodies). The user agrees.

### B. Gather
The user shares 1–3 things they actually wrote (a past cover letter, a LinkedIn post, an old
application answer). *No-writing variant:* the user has none → the companion runs the guided Q&A
instead (how they'd open a note to a hiring manager, a project they're proud of, phrasing they
can't stand, how formal/long they write).

### C. Extract → voice profile
The companion distils a structured voice profile (rhythm, register, recurring openers,
vocabulary, rhetorical habits, AI-tells to avoid, 1–2 worked example paragraphs). Any voice-only
doc is **shredded here**; kept docs stay for the KB.

### D. Meter + calibrate (honest, no score)
- **Coverage report:** for each voice dimension, "clear read / rough read / nothing yet," and
  what would sharpen the thin ones — *not* a percentage.
- **Blind calibration:** the companion drafts a short sample (a two-line intro) in the voice so
  far and asks **"does this sound like you — yes / not quite / no?"**
- The user says **"not quite — too formal, and I'd never open with 'I am writing to…'."**
- The companion adjusts the profile and drafts again. The user says **"yes, that's me."**
- ✅ **The user decides it's good enough** — the companion never declares it.

### E. Persist the voice profile (manual save)
The companion regenerates the full **`voice-profile.md`** in a copy-block and says, plainly:
*"Save this into the Project's knowledge, replacing the previous version — I can't write it
myself."* **The user saves it.**

### F. A knowledge-base growth event
The user starts working toward an application and a question comes up the KB can't answer, e.g.
**"Do you have experience with regulated fintech / PCI-DSS?"**
- The companion checks the KB slice, finds nothing direct, and **says so plainly**, naming the
  nearest real adjacent experience if any ("no direct PCI-DSS; closest is the payments
  integration at <X>") — and **flags the gap** to the user.
- The user supplies the real answer: *"I did a payments integration at X that had to pass an
  external security audit, but I wasn't the compliance owner."*
- The companion **tightens** it into a clean, honest, reusable answer in the user's voice.
- It **stores it back** to the KB tagged `q:fintech-compliance`, `domain:payments`, then
  regenerates **`knowledge-base.md`** in a copy-block and says: *"Save this into Project
  knowledge."* **The user saves it.**

### G. End Conversation 1
Close the conversation. Nothing is in the model's memory anymore — only what the user saved into
Project knowledge (`voice-profile.md`, `knowledge-base.md`, and the kept domain docs).

---

## Conversation 2 — fresh, prove persistence

Start a **brand-new conversation in the same Project.** The companion has no memory of
Conversation 1; it has only Project knowledge.

1. **Voice persisted?** Ask it to draft a two-line intro for a role. It should draft in the
   calibrated voice (informal, not opening with "I am writing to…") — because it's reading the
   saved `voice-profile.md`. ✅ if it sounds like the user *on the first draft*.
2. **KB grown answer persisted?** Ask the fintech/PCI-DSS question again. It should **not**
   re-ask from scratch — it retrieves the stored, tightened answer from `knowledge-base.md`
   (tagged `q:fintech-compliance`), honestly scoped ("payments integration that passed an
   external audit; wasn't the compliance owner"). ✅ if the grown answer comes back without
   re-asking the user.
3. **Honest-gap still honest?** Ask a genuinely new gap question (something never covered). It
   should say plainly it doesn't have that yet and start a new growth event — proving the
   discipline holds, not just retrieval.

**Passes when:** both the voice and the grown answer survive into Conversation 2 **because they
were saved** — and a new gap still triggers an honest "I don't have that yet." If anything is
missing in Conversation 2, check that the user actually saved the regenerated file at steps E/F;
that gap *is* the mechanic working as designed (unsaved = not persisted), not a bug to code
around.

> This dry-run uses **no real application and writes nothing to Notion.** The live apply loop
> (re-verify → draft → record → next-scan dedup) is exercised separately in acceptance
> (`docs/PHASE_3A_PLAN.md` §7, step 3a.7).
