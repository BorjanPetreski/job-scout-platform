# Notion write contract (companion side)

Notion is the only bridge between you and the scanner, so writing it correctly is what keeps the
two from fighting and what makes dedup work. Read this contract before any Notion write.

## Write-ownership partitions by row STATE

The scanner and you never touch the same row in the same state:

- **The scanner** writes a Passed/Seen row only while creating it (`New — Unreviewed`) or when
  its sweep flips a still-unreviewed row to `Stale/Expired`. It also reads Notion at scan start
  to dedup. **It never writes the Applications Tracker** (the firewall — preserved verbatim).
- **You** write only transitions *out* of `New — Unreviewed` (→ `User Applied Elsewhere` or
  `User Declined`) and **Tracker row creation**. Once a row leaves `New — Unreviewed`, the
  scanner's dedup never re-touches it, so you and the scanner cannot collide.

**You never write `seen.jsonl` or any repo file.** The scanner reconciles its own local state
from Notion on its next scan. Your only persistence is Notion (and Project knowledge).

## The pinned vocabulary — use these EXACT values, never free-text

Notion silently mints a new select option if you write a value that doesn't exist. A stray
option the scanner doesn't recognize breaks dedup and the ledger. So the select values are
**pinned** — write only these exact strings:

**Passed/Seen Log — `Reason Passed`:**

| Situation | Exact value to write |
|-----------|----------------------|
| User applied (you recorded the application) | `User Applied Elsewhere` |
| User passed / declined the role | `User Declined` |
| You directly observed the posting is dead | `Stale/Expired` |

(The scanner owns the other values — `New — Unreviewed`, `Filtered Out`, `Duplicate Listing`,
`Unverified/Blocked`. Don't write those.)

**Applications Tracker — `Status`:** a new row you create always starts **`Applied`**. (Later
progression — `Screening`, `Interview`, `Offer`, `Rejected`, `Withdrawn` — is the interview
lifecycle, out of 3a scope.) **`Source`:** `Claude Skill Scan` for a scanned role, `Manual
Entry` for one the user found themselves.

> If a genuinely new label is ever needed, that is a **provisioning decision** — it must be
> added to the engine's `provision_notion.py` `REASON_OPTIONS` and `notion_sync.py`
> `VALID_REASONS` first, then to this contract. Never an ad-hoc MCP write of a new value.

## Recording an application (on "applied")

1. **Create the Tracker row** via the Notion MCP with parent
   `data_source_id = <tracker data_source_id from the snapshot>`: Role (title), Company, Job URL
   (raw URL, never a markdown link), Platform, Status `Applied`, Source, Date Applied
   (date-only), Fit Score, Keyword Source, Notes. Put the **submitted answers in the row body**
   (paragraph blocks) so the user can revisit exactly what they sent.
2. **Idempotent by URL:** before creating, check the Tracker for an existing row with the same
   Job URL. If one exists, update it instead of creating a duplicate.
3. **Flip the Passed/Seen row** `New — Unreviewed` → `User Applied Elsewhere` (find it by Job
   URL in the Passed/Seen Log).

## Recording a pass (on "declined")

Flip the Passed/Seen row `New — Unreviewed` → `User Declined` and put the user's real reason in
Notes. No Tracker row (a decline is not an application, and it has no Tracker row for the scanner
to reconcile from — so the scanner's sweep guard leaves it alone).

## A dead posting (D11)

If re-verification shows the posting is dead, flip the Passed/Seen row → `Stale/Expired` with a
dated note. This is a shared terminal state; neither app resurrects it. The scanner's sweep is
still the proactive staleness engine — you set it only on a posting you *directly* observed dead.
