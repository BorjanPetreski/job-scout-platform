#!/bin/bash
set -euo pipefail

# ── 1) Environment ───────────────────────────────────────────────────────────
# Installs core/'s third-party Python dependencies (requests, pyyaml, selectolax,
# playwright) at session start — see requirements.txt. Without this, a fresh session
# silently lacks selectolax/playwright and core/fetch_boards.py's JD extraction falls
# back to a degraded path (2026-07-20 finding: this fed raw CSS/JS text to every
# downstream detector — language, salary, stack-keyword — with no visible signal).

pip install -q -r "$CLAUDE_PROJECT_DIR/requirements.txt"

# Chromium: managed remote environments pre-install it (PLAYWRIGHT_BROWSERS_PATH is
# already set) — never run `playwright install` there. Local/laptop-lane machines need
# it once; skip if already present (idempotent).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  if [ -z "${PLAYWRIGHT_BROWSERS_PATH:-}" ] || [ ! -d "${PLAYWRIGHT_BROWSERS_PATH:-/nonexistent}" ]; then
    python3 -m playwright install --with-deps chromium
  fi
fi

# ── 2) Session context injection ─────────────────────────────────────────────
# SessionStart hook stdout is added to Claude's context. Injecting docs/STATE.md here
# means every session opens already knowing the current lane / next step / phase
# status — no manual read, no repo re-exploration, and no reading the 160KB+
# PROGRESS.md log (history stays on demand). See CLAUDE.md "Session START protocol".
# Costs ~1K tokens per session vs the ~40K a full PROGRESS.md read used to burn.

echo "=== SESSION CONTEXT (auto-injected by .claude/hooks/session-start.sh) ==="

STATE_FILE="$CLAUDE_PROJECT_DIR/docs/STATE.md"
if [ -f "$STATE_FILE" ]; then
  echo "--- docs/STATE.md (current build state — trust this first) ---"
  cat "$STATE_FILE"
else
  echo "!!! docs/STATE.md is MISSING — fall back to the per-phase checklists in"
  echo "!!! docs/PROGRESS.md (read ONLY the checklist sections, not the session log),"
  echo "!!! flag the missing dashboard to Borjan, and recreate STATE.md this session."
fi

echo "--- git ---"
echo "branch: $(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null || echo 'unknown')"
DIRTY="$(git -C "$CLAUDE_PROJECT_DIR" status --porcelain --no-renames 2>/dev/null | head -20 || true)"
if [ -n "$DIRTY" ]; then
  echo "uncommitted changes (first 20):"
  echo "$DIRTY"
else
  echo "working tree clean"
fi
echo "=== END SESSION CONTEXT ==="
