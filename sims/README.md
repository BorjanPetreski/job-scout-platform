# sims/ — offline acceptance simulations

Self-contained, self-asserting harnesses that exercise engine flows end-to-end against a mocked
Notion — **no token, no network, no profile state touched** (each writes only to a throwaway temp
dir). They prove a behavior the way a live run would, so an acceptance box can be closed offline and
re-checked any time. Not imported by the engine; not run by `core/validate.py`.

| Script | Proves |
|--------|--------|
| `reconcile_new_tracker_box.py` | The companion-created **NEW Tracker row → next-scan back-fill** box (PHASE_3A_ACCEPTANCE §4): `reconcile_applied_from_tracker` back-fills the `seen.jsonl` record to `applied`, flips the lingering Passed/Seen shortlist row `New — Unreviewed → User Applied Elsewhere` (#8/#11), dedups the role on re-discovery, is token-gated, idempotent on re-run, and never clobbers an already-resolved row (read-before-write guard). |

Run any sim directly; exit 0 = proven:

```
python3 sims/reconcile_new_tracker_box.py
```
