#!/usr/bin/env python3
"""health.py — Layer 1 of Platform Health & Self-Healing (HEALTH_MONITORING.md).

"Scripts flag, Claude decides," applied to board rot. This module is the MECHANICAL
half: it reads the runs.json telemetry a scan already writes and computes per-platform
trends against a trailing baseline, emitting severity-flagged findings. It makes NO
network calls, NO judgment, and NO repairs — diagnosis + catalog fixes are the Layer-2
Claude "platform health review," which this report is the cue for.

The signals (HEALTH_MONITORING.md):
  SYSTEMIC          all/most active boards at ~zero in the latest run — a core/network
                    problem, not board rot (fires alone; per-board flags are symptoms of it)
  SELECTOR_SUSPECT  reached the board (HTTP 200 + body) but parsed 0 rows, having produced
                    many historically — THE SILENT BREAK the honest-failure floor misses,
                    because source_down alone doesn't catch a 200-that-parses-empty
  DOWN_STREAK       hard-down (never reached) N runs in a row
  YIELD_COLLAPSE    still producing, but raw fell far below its trailing median
  NEVER_PRODUCED    active board seen across many runs that has logged zero candidates ever

`compute_health()` is a pure function over plain telemetry (unit-tested in
tests/unit_health.py). The CLI loads runs.json + the profile's thresholds/active boards,
prints the report, and ACKS the health-review counter (running the review resets it).

Run: python3 core/health.py [--profile <id>] [--json] [--no-ack]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths

# Severity ranking — lower sorts first (most urgent on top).
SEVERITY = {"SYSTEMIC": 0, "SELECTOR_SUSPECT": 1, "DOWN_STREAK": 1,
            "YIELD_COLLAPSE": 2, "NEVER_PRODUCED": 3}
_SEV_LABEL = {0: "critical", 1: "high", 2: "medium", 3: "low"}

# System-wide + immutable — mirrors core/defaults.yaml `health:` (the fallback when a
# profile can't load). Not user-configurable by design; see defaults.yaml for the rationale.
_DEFAULT_TH = {
    "window": 6, "down_streak": 4, "yield_collapse_factor": 0.15,
    "min_baseline": 3, "never_produced_min_runs": 4, "systemic_frac": 0.7,
    # minimum active boards present before a SYSTEMIC verdict is even possible — below this,
    # "most boards at zero" is too small a sample to call a platform-wide outage. Hoisted from
    # an inline `>= 4` literal (2026-07-21 pass, finding D1): its sibling `systemic_frac` was
    # already a declared/overridable threshold, so this half of the same rule lived undeclared.
    "systemic_min_boards": 4,
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _stats_of(rec: dict) -> dict[str, dict]:
    """Per-platform {raw, source_down, http_ok} for one run. Uses the platform_stats block
    when present; for legacy runs written before it existed, reconstructs what it can from
    platforms_covered / sources_down (raw unknown → None, so yield math skips them)."""
    ps = rec.get("platform_stats")
    if ps:
        return {name: {"raw": s.get("raw"),
                       "source_down": bool(s.get("source_down")),
                       "http_ok": bool(s.get("http_ok"))}
                for name, s in ps.items()}
    out: dict[str, dict] = {}
    for name in rec.get("platforms_covered", []):
        out[name] = {"raw": None, "source_down": False, "http_ok": True}
    for name in rec.get("sources_down", []):
        out[name] = {"raw": None, "source_down": True, "http_ok": False}
    return out


def _flatten(runs: dict) -> list[tuple[str, str, dict]]:
    """runs.json → chronological [(date, label, record)], counter blocks skipped."""
    entries: list[tuple[str, str, dict]] = []
    for day, labels in runs.items():
        if not _DATE_RE.match(day) or not isinstance(labels, dict):
            continue
        for label, rec in labels.items():
            if isinstance(rec, dict):
                entries.append((day, label, rec))
    entries.sort(key=lambda e: e[2].get("ran_at") or f"{e[0]}T{'00' if e[1] == 'AM' else '12'}:00")
    return entries


def _is_zero(s: dict) -> bool:
    return bool(s["source_down"]) or (s.get("raw") is not None and s["raw"] == 0)


def _hard_down(s: dict) -> bool:
    # a true outage: went down AND never got a usable 200 body (distinct from a 200-parses-0)
    return bool(s["source_down"]) and not s.get("http_ok")


def compute_health(runs: dict, active_names: list[str] | None = None,
                   thresholds: dict | None = None) -> dict:
    """Pure trend analysis over the runs.json telemetry. Returns a report dict; makes no
    I/O. `active_names` scopes NEVER_PRODUCED to currently-active boards (unknown → skip)."""
    th = {**_DEFAULT_TH, **(thresholds or {})}
    active = set(active_names or [])
    entries = _flatten(runs)
    window = int(th["window"])
    analyzed = entries[-window:] if window > 0 else entries
    if not analyzed:
        return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "window": window, "runs_analyzed": 0, "latest_run": None,
                "findings": [], "counts": {}, "healthy": True,
                "note": "no runs recorded yet — nothing to baseline"}

    run_stats = [_stats_of(rec) for (_, _, rec) in analyzed]
    latest = run_stats[-1]
    ld, ll, _ = analyzed[-1]
    findings: list[dict] = []

    def emit(platform, flag, detail, evidence):
        findings.append({"platform": platform, "flag": flag,
                         "severity": _SEV_LABEL[SEVERITY[flag]], "detail": detail,
                         "evidence": evidence})

    # --- SYSTEMIC first: if most active boards are at ~0 this run, per-board flags are just
    #     symptoms of one core/network failure — report the one cause, not 15 symptoms.
    present = [n for n in latest if n in active] if active else list(latest)
    zeros = [n for n in present if _is_zero(latest[n])]
    frac = len(zeros) / len(present) if present else 0.0
    systemic = len(present) >= th["systemic_min_boards"] and frac >= th["systemic_frac"]
    if systemic:
        emit("(platform-wide)", "SYSTEMIC",
             f"{len(zeros)}/{len(present)} active boards at ~zero in the latest run "
             f"({frac:.0%}) — likely a core/network problem, not board rot",
             {"zero_boards": sorted(zeros), "present": len(present)})

    # --- per-board signals (suppressed when SYSTEMIC — they're downstream of it)
    all_names = sorted({n for rs in run_stats for n in rs})
    for name in all_names:
        appearances = [rs[name] for rs in run_stats if name in rs]
        cur = latest.get(name)
        prior_yields = [s["raw"] for rs in run_stats[:-1] if name in rs
                        for s in [rs[name]]
                        if s.get("raw") is not None and not s["source_down"] and s["raw"] > 0]
        median = _median(prior_yields) if prior_yields else None

        flag = None
        if not systemic and cur is not None:
            reached_empty = cur.get("http_ok") and cur.get("raw") == 0
            if reached_empty and median is not None and median >= th["min_baseline"]:
                flag = "SELECTOR_SUSPECT"
                emit(name, flag,
                     f"reached (HTTP 200) but parsed 0 rows; trailing median was "
                     f"{median:g} — markup/selector likely changed",
                     {"raw": cur.get("raw"), "trailing_median": median, "http_ok": True})
            else:
                streak = 0
                for rs in reversed(run_stats):
                    if name not in rs:
                        break
                    if _hard_down(rs[name]):
                        streak += 1
                    else:
                        break
                if streak >= th["down_streak"]:
                    flag = "DOWN_STREAK"
                    emit(name, flag,
                         f"source down (unreachable) {streak} runs in a row",
                         {"streak": streak})
                elif (cur.get("raw") is not None and cur["raw"] > 0 and not cur["source_down"]
                      and median is not None and median >= th["min_baseline"]
                      and cur["raw"] < th["yield_collapse_factor"] * median):
                    flag = "YIELD_COLLAPSE"
                    emit(name, flag,
                         f"raw {cur['raw']} is far below trailing median {median:g} "
                         f"(< {th['yield_collapse_factor']:.0%})",
                         {"raw": cur["raw"], "trailing_median": median})

        # NEVER_PRODUCED is structural (independent of the latest run) but only when no other
        # flag already explains this board, and only for boards we know are active.
        if flag is None and name in active and len(appearances) >= th["never_produced_min_runs"]:
            known = [s["raw"] for s in appearances if s.get("raw") is not None]
            reached_ever = any(s.get("http_ok") for s in appearances)
            if known and max(known) == 0 and reached_ever:
                emit(name, "NEVER_PRODUCED",
                     f"active and reached across {len(appearances)} runs but has logged "
                     f"zero candidates — empty config or wrong endpoint/slug",
                     {"runs_seen": len(appearances)})

    findings.sort(key=lambda f: (SEVERITY[f["flag"]], f["platform"]))
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["flag"]] = counts.get(f["flag"], 0) + 1
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "window": window, "runs_analyzed": len(analyzed),
            "latest_run": f"{ld} {ll}", "findings": findings, "counts": counts,
            "healthy": not findings}


def format_report(report: dict, profile: str | None = None) -> str:
    """Human summary for the ledger / chat — the Layer-2 review reads this first."""
    lines = [f"## Platform health — {profile or ''} — {report.get('latest_run') or 'no runs'}".rstrip()]
    lines.append(f"analyzed {report['runs_analyzed']} runs (window {report['window']})")
    findings = report["findings"]
    if not findings:
        lines.append("✓ healthy — no flagged boards")
        if report.get("note"):
            lines.append(f"  ({report['note']})")
        return "\n".join(lines)
    counts = ", ".join(f"{k}×{v}" for k, v in report["counts"].items())
    lines.append(f"⚠ {len(findings)} finding(s): {counts}")
    for f in findings:
        lines.append(f"  [{f['severity']:>8}] {f['flag']:16} {f['platform']}: {f['detail']}")
    lines.append("→ diagnose each flagged board live and apply the catalog fix through the "
                 "validator (Layer 2 — never an ad-hoc scanner edit).")
    return "\n".join(lines)


def _ack_counter(runs: dict, runs_path: Path) -> None:
    """Running the review acks the health-review-due counter (resets sessions_since)."""
    hr = runs.setdefault("health_review", {"due_at_sessions": 6})
    hr["sessions_since"] = 0
    hr["last"] = date.today().isoformat()
    runs_path.write_text(json.dumps(runs, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Layer-1 platform health signals from runs.json")
    ap.add_argument("--profile", default=None, help="profile id under profiles/")
    ap.add_argument("--json", action="store_true", help="print the raw JSON report")
    ap.add_argument("--no-ack", action="store_true",
                    help="do not reset the health-review-due counter (read-only peek)")
    args = ap.parse_args()

    profile = args.profile or paths.get_profile()
    runs_path = paths.runs_path(profile)
    if not runs_path.exists():
        print(f"no runs.json for profile {profile!r} — run a scan first", file=sys.stderr)
        return 1
    runs = json.loads(runs_path.read_text(encoding="utf-8"))

    # thresholds + active board names from the resolved profile config (best-effort — the
    # signals still compute on defaults if the profile can't load for some reason).
    thresholds, active_names = None, None
    try:
        import profile_loader
        cfg = profile_loader.load(profile)
        thresholds = cfg.get("health")
        active_names = [p["name"] for p in cfg["platforms"] if p.get("active")]
    except SystemExit as exc:
        print(f"[health] profile load failed ({exc}); using default thresholds", file=sys.stderr)

    report = compute_health(runs, active_names, thresholds)
    report["profile"] = profile
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(format_report(report, profile))
    if not args.no_ack:
        _ack_counter(runs, runs_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
