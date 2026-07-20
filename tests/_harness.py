"""Tiny self-asserting test harness — the project's convention (no pytest, matching
core/validate.py + sims/). Each tests/*.py defines main() -> list[str] of failures and is
runnable standalone (`python3 tests/unit_detectors.py`) or via tests/run_all.py. Puts core/
on the path so `import scan`, `import dedup`, … resolve exactly as they do in the engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))


class Suite:
    def __init__(self, name: str) -> None:
        self.name = name
        self.n = 0
        self.fails: list[str] = []

    def eq(self, got, want, label: str) -> None:
        self.n += 1
        cond = got == want
        print(("  ✓ " if cond else "  ✗ ") + label
              + ("" if cond else f"  (got {got!r}, want {want!r})"))
        if not cond:
            self.fails.append(f"{self.name}: {label}")

    def ok(self, cond: bool, label: str) -> None:
        self.n += 1
        print(("  ✓ " if cond else "  ✗ ") + label)
        if not cond:
            self.fails.append(f"{self.name}: {label}")

    def done(self) -> list[str]:
        print(f"[{self.name}] {self.n - len(self.fails)}/{self.n} passed")
        return self.fails
