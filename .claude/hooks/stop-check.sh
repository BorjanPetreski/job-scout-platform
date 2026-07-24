#!/bin/bash
# Stop hook — wrap-up nudges (CLAUDE.md Definition-of-Done).
# Nudge 1 (standing rule): branch changed core/ or skills/ but not assistant/GUIDED-FLOW.md
#   → fold proven prompts (DoD #1) + assess build-method lessons (DoD #7).
# Nudge 2 (state discipline): branch changed files but not docs/STATE.md
#   → rewrite the dashboard + append the PROGRESS session row (DoD #2).
# Nudge 3 (lesson assessment, added 2026-07-24): ANY changed branch that touched neither
#   the playbook nor the core/skills trigger zone (where nudge 1 already covers DoD #7)
#   → one-line reminder that the DoD #7 ASSESSMENT is mandatory even when folding-in isn't.
#   Rationale: the session-lifecycle restructure (docs-only branch) surfaced an obvious
#   playbook lesson and shipped without it — the honor-system tier fails even under ideal
#   conditions. Assessing is cheap; skipping it silently is the failure mode.
# Hooks only remind — acting on them stays a judgment call. Always exits 0.

set -u

changed=$( { git diff --name-only origin/main 2>/dev/null; \
             git status --porcelain --no-renames 2>/dev/null | cut -c4-; } | sort -u | grep -v '^$' || true )

[ -z "$changed" ] && exit 0

parts=()

msg1=""
if printf '%s\n' "$changed" | grep -qE '^(core|skills)/' \
   && ! printf '%s\n' "$changed" | grep -qx 'assistant/GUIDED-FLOW.md'; then
  msg1="Wrap-up check (standing rules): this branch changed core/ or skills/ but not assistant/GUIDED-FLOW.md. (1) If a step was dogfooded/proven this session, fold its prompt into assistant/GUIDED-FLOW.md (mark it proven). (2) Assess whether a reusable BUILD-METHOD lesson emerged (product-agnostic) — if so, fold it into docs/BUILD_AND_FLIP_PLAYBOOK.md. Do either in its own small PR before wrapping. See CLAUDE.md Definition-of-Done."
  parts+=("$msg1")
fi

if ! printf '%s\n' "$changed" | grep -qx 'docs/STATE.md'; then
  parts+=("State check (DoD #2): this branch changed files but not docs/STATE.md. Before wrapping: (a) rewrite docs/STATE.md (Now / Next / phase rows / open threads / Last updated) to match end-of-session reality, and (b) append a session row to docs/PROGRESS.md + flip any affected checklist box. A stale STATE.md breaks the next session's start.")
fi

if [ -z "$msg1" ] \
   && ! printf '%s\n' "$changed" | grep -qx 'docs/BUILD_AND_FLIP_PLAYBOOK.md'; then
  parts+=("Lesson check (DoD #7): assess whether this session taught a reusable, product-agnostic build-method lesson. Folding into docs/BUILD_AND_FLIP_PLAYBOOK.md is a judgment call; ASSESSING is not — state the assessment ('no generic lesson' is a valid answer) before wrapping.")
fi

if [ ${#parts[@]} -gt 0 ]; then
  msg=$(printf '%s  ||  ' "${parts[@]}")
  msg=${msg%  ||  }
  esc=$(printf '%s' "$msg" | sed 's/"/\\"/g')
  printf '{"systemMessage":"%s"}' "$esc"
fi

exit 0
