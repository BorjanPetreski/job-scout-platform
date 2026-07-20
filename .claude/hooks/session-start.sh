#!/bin/bash
set -euo pipefail

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
