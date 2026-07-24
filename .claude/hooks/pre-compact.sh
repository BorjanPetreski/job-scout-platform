#!/bin/bash
# PreCompact hook (added 2026-07-24) — fires before manual (/compact) AND auto compaction.
# Compaction summarizes older turns; anything living only in chat can be lost. This is the
# last moment to bank two perishables:
#   1. DoD #7 lesson candidates — a build-method insight discussed but not yet folded into
#      docs/BUILD_AND_FLIP_PLAYBOOK.md (or at least parked in docs/STATE.md open threads).
#   2. Proven-but-unbanked prompts (DoD #1 → assistant/GUIDED-FLOW.md).
# Belt-and-braces: CLAUDE.md "Compact Instructions" also tells the summarizer to carry
# un-banked candidates across the boundary — this hook is the loud pre-flight, that line
# is the parachute. Cannot and should not block compaction. Always exits 0.

set -u

printf '{"systemMessage":"Pre-compact check: about to summarize older context. (1) DoD #7 — if a build-method lesson surfaced this session and is not yet in docs/BUILD_AND_FLIP_PLAYBOOK.md, bank it NOW or park it in docs/STATE.md open threads so it survives. (2) DoD #1 — any proven-but-unfolded prompt goes to assistant/GUIDED-FLOW.md. Compaction proceeds either way; un-banked chat-only insights may not."}'

exit 0
