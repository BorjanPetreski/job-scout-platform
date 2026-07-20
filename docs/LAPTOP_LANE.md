# Laptop Lane — attended run + unattended scheduling (borjan-pm)

> How to run the job-scout engine on your laptop with the Claude CLI: first an
> **attended** run (you watch, it shows the delta table), then **unattended**
> scheduled runs (cron fires them, Notion is the inbox). The laptop lane complements
> the cloud Routines — your residential IP reaches sources the cloud can't (both Remote
> Rocketship platforms came back live on the laptop, down in the cloud), so laptop runs
> get better coverage. Dedup absorbs any overlap between the two lanes.

Applies to macOS/Linux. Windows notes at the end. Assumes the v3 setup already ran on
this machine (Python 3.11+, `requests pyyaml selectolax playwright`, `chromium`
installed, and the `claude` CLI logged in).

---

## 0. One-time prep (do once, today or tomorrow)

```bash
cd /path/to/job-scout-platform          # your local clone
git checkout main && git pull origin main   # pull core/, profiles/, skills/, catalog/, templates/

# zero-prompt permissions for the scan workflow (needed for unattended; nice for attended)
mkdir -p .claude && cp claude-settings.example.json .claude/settings.json
```

Verify the engine resolves before anything else (no network, instant):

```bash
python3 core/scan.py --profile borjan-pm --plan
```

You should see the rotation plan (platforms, keywords, filters, salary floor). If that
prints cleanly, the lane is ready.

If deps are missing (fresh machine only):

```bash
pip install -r requirements.txt && playwright install chromium
```

(Claude Code cloud/web sessions install `requirements.txt` automatically via the
`SessionStart` hook in `.claude/settings.json` — see `docs/PROGRESS.md` 2026-07-20. A
missing/broken `selectolax` degrades JD-text extraction silently otherwise — see the
`_visible_text()` note in `core/fetch_boards.py`.)

### Notion token

Unattended Notion writes (and attended, if you want rows pushed automatically) need
`NOTION_TOKEN` in the environment. Put it where each lane can read it:

- **Attended:** `export NOTION_TOKEN='ntn_…'` in the shell before launching `claude`.
- **Unattended (cron):** set it inside the cron command (see §2) or in a file the cron
  job sources — cron does NOT inherit your shell's env.

Without the token the scan still runs; `notion_sync` just exports
`profiles/borjan-pm/state/notion_pending.json` for a later MCP push and the digest goes
unwritten (a *failed* sync, not a crash).

---

## 1. Attended run (Claude CLI, you watch)

Interactive — Claude reads the skill, runs the scan, does the judgment/scoring, and
shows you the delta table. Use this to review shortlists and record applications.

```bash
cd /path/to/job-scout-platform
export NOTION_TOKEN='ntn_…'        # optional but recommended for the attended run
claude                              # launches the interactive CLI in this repo
```

Then type (natural language — this drives the whole flow):

```
Run the job scout scan for borjan-pm per skills/job-scout-run/SKILL.md.
```

What happens, in order (all from the skill):
1. `state_sync.py pull` → `scan.py` (fetch, filter, liveness, shortlist sweep) → you'll
   see the coverage ledger.
2. Claude reads `state/last_run_candidates.json` + the JD cache, applies your hard
   filters + `filter_notes`, scores every survivor, and prints the **delta table** +
   role notes.
3. Shortlisted rows are logged to `seen.jsonl` and pushed to your Notion **Passed/Seen
   Log** as `New — Unreviewed`; the digest line lands on the Runs page.
4. `state_sync.py push` converges the state to git.
5. It ends with the Gemini cross-check offer (attended only).

Because it's **attended** (you did NOT say "unattended mode"), it will ask before
anything ambiguous and won't go silent. If you copied `settings.json` in §0, it won't
prompt for routine tool calls; otherwise approve them as they appear.

**Recording an application** (when you decide to apply to a shortlisted role): just tell
Claude in the same session:

```
I applied to <job-url>
```

That marks the `seen.jsonl` record `applied` and creates the row in your **Applications
Tracker** (the only path that ever writes the Tracker).

**Reviewing the queue:** your 5 New — Unreviewed rows from today's cloud run are already
in the Passed/Seen Log — open the "📥 New — Unreviewed" view in Notion to work them.

---

## 2. Unattended scheduling (cron)

Unattended = no questions, Notion is the inbox, minimal chat. Mirror the cloud cadence:
**AM Tue–Sun**, **Monday full sweep**, **PM daily** (dedup makes cloud+laptop overlap
harmless). Times below are **local**; pick what suits you (v3 used 08:00 / 18:00).

### 2a. Find the pieces

```bash
which claude          # e.g. /opt/homebrew/bin/claude or /usr/local/bin/claude — use the FULL path in cron
echo "$HOME"          # cron needs HOME set so claude finds its login + your .claude/settings.json
```

### 2b. Edit crontab

```bash
crontab -e
```

Add (replace `CLAUDE` with the full path from `which claude`, and `/path/to/repo` with
your clone path):

```cron
# --- Job Scout (borjan-pm, core engine) — laptop lane ---
HOME=/Users/you
NOTION_TOKEN=ntn_…

# AM scan, Tue–Sun 08:00
0 8 * * 0,2-6 cd /path/to/repo && CLAUDE -p "Run the job scout AM scan for borjan-pm per skills/job-scout-run/SKILL.md. Unattended mode. Code lane: python3 core/state_sync.py pull --profile borjan-pm first, python3 core/state_sync.py push --profile borjan-pm last." >> "$HOME/job-scout-am.log" 2>&1

# Monday full sweep 08:00
0 8 * * 1 cd /path/to/repo && CLAUDE -p "Run the job scout AM scan for borjan-pm per skills/job-scout-run/SKILL.md using python3 core/scan.py --profile borjan-pm --full-sweep (weekly full sweep). Unattended mode. Code lane: state_sync.py pull --profile borjan-pm first, push last." >> "$HOME/job-scout-sweep.log" 2>&1

# PM scan, daily 18:00
0 18 * * * cd /path/to/repo && CLAUDE -p "Run the job scout PM scan for borjan-pm per skills/job-scout-run/SKILL.md. Unattended mode. Code lane: python3 core/state_sync.py pull --profile borjan-pm first, python3 core/state_sync.py push --profile borjan-pm last." >> "$HOME/job-scout-pm.log" 2>&1
```

Save and exit. Check it registered: `crontab -l`.

### 2c. The gotchas that actually bite

- **Full path to `claude`** — cron's `PATH` is minimal; a bare `claude` will "command
  not found". Use the `which claude` output.
- **`HOME=` line** — without it cron can't find your `claude` login creds (`~/.claude`)
  or the repo's `.claude/settings.json`, and every tool call would block. The `cd
  /path/to/repo` is what makes `claude -p` pick up the `settings.json` allowlist you
  copied in §0.
- **`NOTION_TOKEN`** — set in the crontab (as above) or the sync silently degrades to
  the pending-export path. Cron does not read your shell profile.
- **Laptop must be awake** — cron only fires when the machine is on and not asleep. This
  is exactly why the **cloud Routines** exist (they run laptop-off). The laptop lane is
  the *better-coverage bonus* when you're working; the cloud lane is the always-on
  baseline. Run both.
- **First run per day does the heavy backfill**; steady-state deltas are small (you saw
  26 today after this morning's 116 got deduped).
- **Auth non-interactive** — `claude -p` uses your existing CLI login. If runs fail with
  an auth error, run `claude` once interactively to refresh the login, then cron works.

### 2d. Test a cron line by hand first

Before trusting the schedule, run one line manually to confirm it completes end-to-end:

```bash
cd /path/to/repo && NOTION_TOKEN='ntn_…' claude -p "Run the job scout AM scan for borjan-pm per skills/job-scout-run/SKILL.md. Unattended mode. Code lane: python3 core/state_sync.py pull --profile borjan-pm first, python3 core/state_sync.py push --profile borjan-pm last."
```

Watch for: coverage ledger, a new `scan state` commit pushed to `main`, and the digest
line + any shortlist rows in Notion. Then check the log file the cron line writes to.

---

## Alternative schedulers

- **macOS launchd** (survives better than cron on laptops): create a
  `~/Library/LaunchAgents/com.borjan.jobscout-am.plist` with `StartCalendarInterval`
  running the same `cd … && claude -p "…"` via `/bin/zsh -lc`. Use `launchctl load` it.
  Same env caveats (set `NOTION_TOKEN`, run from the repo dir).
- **Windows Task Scheduler**: create a task per run, Action = `claude` with the `-p "…"`
  argument, "Start in" = repo path, set `NOTION_TOKEN` as a user/system env var, and
  tick "Run whether user is logged on or not". Same prompts as the cron lines.

---

## Quick reference — the prompts

| Run | Prompt |
|-----|--------|
| Attended | `Run the job scout scan for borjan-pm per skills/job-scout-run/SKILL.md.` |
| Unattended AM | `Run the job scout AM scan for borjan-pm per skills/job-scout-run/SKILL.md. Unattended mode. Code lane: state_sync.py pull --profile borjan-pm first, push last.` |
| Unattended PM | same as AM with "PM scan" |
| Weekly sweep | AM prompt + "using python3 core/scan.py --profile borjan-pm --full-sweep" |
| I applied | `I applied to <job-url>` |

## Cloud Routines (already set up, currently PAUSED)

The 3 cloud Routines are re-pointed to this engine and paused. Re-enable them in the
Claude Code Routines UI when ready; set `NOTION_TOKEN` in the `env_01BNDMn4YXdEnRiQEqqxMb7Q`
environment first. They run laptop-off on the same repo/profile and converge state via git.
