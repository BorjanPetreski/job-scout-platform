#!/usr/bin/env python3
"""compose_assistant.py — bind a profile to its Application Companion Project (Phase 3a, D12).

Composes the generic companion package (`assistant/[0-9][0-9]-*.md`, profile-agnostic) plus a
minimal, PII-free profile snapshot (salary floor, eligibility, location/timezone, Notion
data_source_ids) plus the profile's own `assistant/voice-seed.md` + `data-manifest.md` (both
optional) into:

    profiles/<id>/assistant/project-instructions.md

which the user pastes into their claude.ai Claude Project. One-directional (repo → Project),
config only, NO PII — the voice profile and knowledge base are built and held INSIDE the Project
(D13), never composed from the repo. CV/PII never enters this output (the data principle).

Determinism & idempotency (3a.0 gate):
  * The output is a pure function of (generic package, profile snapshot, voice-seed, manifest)
    plus a compose date. Re-running when nothing changed is a NO-OP: the composer compares the
    new body against the existing file (ignoring the compose-date line) and leaves the file — and
    its original compose date — untouched if identical. A real change (any `profile.yaml` edit
    that moves the floor / eligibility / location / Notion IDs, or a package edit) rewrites it
    with today's date.
  * A **source-config hash** over the extracted snapshot is stamped into the header so the
    Project can announce it and a human can tell whether a paste is stale. The Project cannot
    read the repo, so a stale snapshot drifts silently — the engine's own memory-ID lesson (IDs
    drift; the profile is the source of truth) applies doubly to a pasted snapshot.

Handles a profile with **no `voice-seed.md`** (composes the guided-Q&A voice path — e.g.
`ani-backend-java`) and no `data-manifest.md` (composes a generic upload checklist). Dry-run
profiles (no Notion targets) compose with an honest "no Notion targets" note instead of failing.

Usage:
  compose_assistant.py --profile <id>            compose (write if changed)
  compose_assistant.py --profile <id> --check    exit 1 if compose WOULD change the file (CI)
  compose_assistant.py --all [--check]           every LIVE profile (dry-run profiles skipped —
                                                 a companion binding needs Notion targets; an
                                                 explicit --profile <demo> still composes, for a
                                                 portability smoke)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
import profile_loader

PACKAGE_DIR = paths.REPO_ROOT / "assistant"
_MODULE_GLOB = "[0-9][0-9]-*.md"
_DATE_RE = re.compile(r"(\*\*Composed:\*\* )\d{4}-\d{2}-\d{2}")


def _generic_modules() -> list[tuple[str, str]]:
    """Ordered (name, text) for the composable generic package modules."""
    return [(p.name, p.read_text(encoding="utf-8").rstrip() + "\n")
            for p in sorted(PACKAGE_DIR.glob(_MODULE_GLOB))]


def _snapshot(cfg: dict) -> dict:
    """The minimal PII-free config snapshot (D12). Deliberately NO display_name, CV facts,
    tools, certs, domains, or headline — the companion learns those from the Project uploads,
    not from the repo. Only: floor, eligibility, location/timezone, Notion targets."""
    cand = (cfg.get("profile") or {}).get("candidate") or {}
    loc = cand.get("location") or {}
    elig = cand.get("eligibility") or {}
    sf = (cfg.get("hard_filters") or {}).get("salary_floor") or {}
    floor: dict | None = None
    if sf.get("floor"):
        floor = {
            "amount": sf["floor"].get("amount"),
            "currency": sf["floor"].get("currency"),
            "basis": sf["floor"].get("basis"),
            "period": sf["floor"].get("period"),
            "canonical_gross_month": sf.get("canonical_gross_month"),
            "canonical_currency": sf.get("currency"),
            "fte_fraction": sf.get("fte_fraction"),
        }
    notion = cfg.get("notion") or {}
    if notion.get("dry_run"):
        notion_ids: dict | None = None
    else:
        notion_ids = {
            "tracker_data_source_id": (notion.get("tracker") or {}).get("data_source_id"),
            "passed_seen_data_source_id": (notion.get("passed_seen") or {}).get("data_source_id"),
            "runs_page_id": (notion.get("pinned_pages") or {}).get("job_scout_runs"),
        }
    return {
        "profile_id": cfg.get("profile_id"),
        "location": {"city": loc.get("city"), "country": loc.get("country"),
                     "timezone": loc.get("timezone")},
        "location_match_terms": cand.get("location_match_terms") or [],
        "eligibility": {"employment_models": elig.get("employment_models") or [],
                        "needs_visa_sponsorship": elig.get("needs_visa_sponsorship")},
        "salary_floor": floor,
        "notion": notion_ids,
    }


def _config_hash(snap: dict) -> str:
    return hashlib.sha256(json.dumps(snap, sort_keys=True, default=str).encode()).hexdigest()[:12]


def _render_snapshot(snap: dict) -> str:
    loc = snap["location"]
    elig = snap["eligibility"]
    lines = ["## Profile snapshot (config only — no PII)", "",
             f"- **Profile:** `{snap['profile_id']}`",
             f"- **Location / timezone:** {loc.get('city') or '?'}, {loc.get('country') or '?'} "
             f"({loc.get('timezone') or '?'}) — use this for eligibility/remote-region checks.",
             f"- **Counts as \"includes me\" in a closed location list:** "
             f"{', '.join(snap['location_match_terms']) or '(none set)'}",
             f"- **Eligibility / employment models:** "
             f"{', '.join(elig['employment_models']) or '(unset)'}"
             + ("; needs visa sponsorship: "
                + ("yes" if elig["needs_visa_sponsorship"] else "no")
                if elig["needs_visa_sponsorship"] is not None else "")]
    sf = snap["salary_floor"]
    if sf:
        fte = f", pro-rated to {sf['fte_fraction']} FTE" if sf.get("fte_fraction") is not None else ""
        lines.append(
            f"- **Salary floor (safety check — never ask below it):** {sf['amount']} "
            f"{sf['currency']} {sf['basis']}/{sf['period']} "
            f"(≈{sf['canonical_gross_month']} {sf['canonical_currency']} gross/month{fte}).")
    else:
        lines.append("- **Salary floor:** none set — no floor to respect; estimate the ask from "
                     "role/region with judgment (floorless, D20) and say so honestly.")
    n = snap["notion"]
    if n:
        lines += ["- **Notion targets** (read/write via the Notion MCP):",
                  f"    - Passed/Seen Log data source: `{n['passed_seen_data_source_id']}` "
                  "(read the `📥 New — Unreviewed` view; flip rows out of it).",
                  f"    - Applications Tracker data source: `{n['tracker_data_source_id']}` "
                  "(create `Applied` rows here — the ONLY companion Tracker writes).",
                  f"    - Runs page: `{n['runs_page_id']}` (scanner digest — read-only for you)."]
    else:
        lines.append("- **Notion targets:** none (dry-run profile) — no live Notion binding; the "
                     "apply-loop/record steps are illustrative only for this profile.")
    return "\n".join(lines) + "\n"


def _profile_voice_section(profile_id: str) -> str:
    seed = paths.profile_dir(profile_id) / "assistant" / "voice-seed.md"
    if seed.exists():
        return ("## Profile voice seed (person-specific — steers voice + drafting)\n\n"
                "> The following is authored guidance from this profile. It steers voice "
                "acquisition and drafting; the derived voice profile is still built from the "
                "user's own writing inside the Project.\n\n"
                + seed.read_text(encoding="utf-8").rstrip() + "\n")
    return ("## Profile voice seed — none (guided-Q&A path)\n\n"
            "This profile ships **no voice seed**, so learn the user's voice via the guided-Q&A "
            "path in *Voice acquisition* above: field-tuned questions, then blind calibration "
            "until the user says it's good enough. Don't assume a voice from the role type.\n")


def _profile_manifest_section(profile_id: str) -> str:
    man = paths.profile_dir(profile_id) / "assistant" / "data-manifest.md"
    if man.exists():
        return ("## What the user uploads (data manifest)\n\n"
                + man.read_text(encoding="utf-8").rstrip() + "\n")
    return ("## What the user uploads (generic)\n\n"
            "This profile ships no data manifest. Ask the user to upload, into Project knowledge:\n"
            "- their **CV** (domain — the KB's factual spine),\n"
            "- any **past application answers / Q&A notes** (domain — seed the KB),\n"
            "- a few **writing samples** they actually wrote (voice — kept if they carry facts, "
            "otherwise shredded after voice extraction),\n"
            "and confirm the retention class of each per *Consent & the data principle* above.\n")


def _body(cfg: dict, snap: dict, cfg_hash: str) -> str:
    """Everything below the compose-date line — the idempotency-comparable content."""
    parts = [f"<!-- source-config hash: {cfg_hash} -->", "",
             "## How to use this document", "",
             "Paste this whole document into your Claude Project's **instructions**. It is the "
             "generic Application Companion doctrine plus a snapshot of your profile's config. "
             "Then upload your materials (see the data manifest below) and connect the Notion MCP "
             "— setup steps are in `assistant/SETUP.md` in the repo.", "",
             "Announce the **Composed** date above at the start of a working session. If your "
             "salary floor, eligibility, location, or Notion targets have changed since, ask to "
             "re-compose and re-paste — the snapshot cannot update itself.", "",
             _render_snapshot(snap), ""]
    for _name, text in _generic_modules():
        parts.append("---\n")
        parts.append(text)
    parts.append("---\n")
    parts.append(_profile_voice_section(cfg["profile_id"]))
    parts.append("---\n")
    parts.append(_profile_manifest_section(cfg["profile_id"]))
    return "\n".join(parts).rstrip() + "\n"


def _full(body: str, on_date: str, profile_id: str) -> str:
    header = (
        "<!-- AUTO-GENERATED by core/compose_assistant.py — do not edit by hand. Re-compose "
        "after any profile.yaml change (floor, eligibility, location, Notion IDs). -->\n"
        f"# Application Companion — Project instructions for `{profile_id}`\n\n"
        f"> **Composed:** {on_date}  ·  see the source-config hash below.\n\n")
    return header + body


def _strip_date(text: str) -> str:
    return _DATE_RE.sub(r"\1<DATE>", text, count=1)


def _is_dry_run(profile_id: str) -> bool:
    return bool((profile_loader.load(profile_id).get("notion") or {}).get("dry_run"))


def compose(profile_id: str, check: bool = False) -> dict:
    """Compose (or, with check=True, report whether composing WOULD change the file).
    Returns {profile, path, hash, changed}."""
    cfg = profile_loader.load(profile_id)
    snap = _snapshot(cfg)
    cfg_hash = _config_hash(snap)
    body = _body(cfg, snap, cfg_hash)
    out_dir = paths.profile_dir(profile_id) / "assistant"
    out_path = out_dir / "project-instructions.md"
    today = date.today().isoformat()
    new_full = _full(body, today, profile_id)

    changed = True
    if out_path.exists():
        old = out_path.read_text(encoding="utf-8")
        if _strip_date(old) == _strip_date(new_full):
            changed = False  # nothing but the date would move — keep the original compose date

    if changed and not check:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(new_full, encoding="utf-8")
    return {"profile": profile_id, "path": str(out_path.relative_to(paths.REPO_ROOT)),
            "hash": cfg_hash, "changed": changed}


def main() -> None:
    ap = argparse.ArgumentParser(description="Compose a profile's Application Companion binding.")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--all", action="store_true", help="compose every profile")
    ap.add_argument("--check", action="store_true",
                    help="do not write; exit 1 if composing would change any file (CI)")
    args = ap.parse_args()

    if args.all:
        # A companion binding needs Notion targets; dry-run demo profiles have none, so --all
        # skips them (an explicit --profile <demo> still composes for a portability smoke).
        ids = [p for p in paths.list_profiles() if not _is_dry_run(p)]
    elif args.profile:
        ids = [args.profile]
    else:
        ids = [paths.get_profile()]

    drift = 0
    for pid in ids:
        r = compose(pid, check=args.check)
        state = ("WOULD CHANGE" if args.check else "wrote") if r["changed"] else "unchanged"
        print(f"[compose] {pid}: {state} — {r['path']} (config-hash {r['hash']})")
        if r["changed"] and args.check:
            drift += 1
    if args.check and drift:
        raise SystemExit(f"[compose] {drift} binding(s) out of date — run compose_assistant.py "
                         "--all and commit the result")


if __name__ == "__main__":
    main()
