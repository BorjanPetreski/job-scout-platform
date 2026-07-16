# suggestions/ — staged write-back suggestions (Phase 2 §6, D6)

The **opt-in, human-reviewed learning loop**. When a consenting profile is set up or run,
`core/writeback.py` stages **generic, non-PII** template enrichments here for a curator to
review into the shared template library. Nothing here is used at scan time; nothing is
auto-merged (D6 option a — auto-merge is a later upgrade once the pattern is trusted).

## Why this lives OUTSIDE `templates/`

The platform validator (`core/validate.py`) rglobs `templates/**/*.yaml` and strict-validates
every hit as a full template (unknown keys = error). A staging file has a different shape, so
it must not sit under `templates/`. This directory mirrors the template tree
(`suggestions/<stream>/<subvariant>.yaml`) but is validated by its own light check
(`writeback.validate_suggestion_file`, wired into CI in step 2.10).

## What may be staged (and what may NOT)

- **May:** role-generic keyword additions (`keyword_core` / `keyword_expanded`) and
  `archetype` additions — e.g. `kafka`, `spring boot`, `Event-Driven Specialist` for
  backend-java. Short generic terms only.
- **May NOT — ever:** CV text, names, employers, emails, URLs, locations, salaries, or any
  personal data. The staging code refuses any value that isn't a short generic term, and the
  CI check rejects any PII-shaped key. This is the D4/D6 privacy invariant: **CV/PII never
  enters the repo.**

## File format

```yaml
target_template: software-engineering/backend-java     # must exist under templates/
suggestions:
  - kind: keyword_expanded            # keyword_core | keyword_expanded | archetype
    value: kafka                      # short generic term only
    sources: [demo-backend-java]      # kebab-case profile ids that surfaced it (no PII)
    first_seen: "2026-07-16"
    last_seen: "2026-07-16"
    frequency: 2                      # bumped each time another profile surfaces the same term
```

## Curator flow (Borjan, for now)

1. Review the staged entries here (higher `frequency` = surfaced by more profiles = stronger
   signal).
2. For accepted ones, add the term to the target template's `defaults.search.keywords.*` or
   `defaults.search.archetypes` (a normal template edit, validated by CI).
3. Remove (or leave as an audit trail) the merged suggestion entry.

Staging is done only via `core/writeback.py` (`stage_suggestions`) — never hand-edit to add a
value the guard would reject.
