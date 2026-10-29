#!/usr/bin/env python3
"""Run the standard cross-platform local validation gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from collections.abc import Sequence
from enum import Enum
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LINT_PATHS = ("src", "tests", "scripts")

Command = tuple[str, ...]
Step = tuple[str, Command]


class Mode(Enum):
    QUICK = "quick"
    STANDARD = "standard"


def _sphinx_step(builder: str) -> Step:
    """Build ``docs/`` with one Sphinx builder, treating warnings as errors."""
    command = (
        "sphinx-build",
        "-W",
        "--keep-going",
        "-b",
        builder,
        "docs",
        f"docs/_build/{builder}",
    )
    return (f"Sphinx {builder}", ("uv", "run", "--no-sync", *command))


SYNC_STEP: Step = ("Dependency sync", ("uv", "sync", "--locked", "--group", "docs"))
QUALITY_STEPS: tuple[Step, ...] = (
    ("Ruff format", ("uv", "run", "--no-sync", "ruff", "format", "--check", *LINT_PATHS)),
    ("Ruff lint", ("uv", "run", "--no-sync", "ruff", "check", *LINT_PATHS)),
    ("mypy", ("uv", "run", "--no-sync", "mypy", *LINT_PATHS)),
)
QUICK_TEST_STEP: Step = ("pytest", ("uv", "run", "--no-sync", "pytest"))
STANDARD_STEPS: tuple[Step, ...] = (
    ("pytest with coverage", ("uv", "run", "--no-sync", "pytest", "--cov", "--cov-report=term")),
    _sphinx_step("html"),
    _sphinx_step("doctest"),
    ("Build distributions", ("uv", "build")),
)


def build_plan(mode: Mode) -> tuple[Step, ...]:
    quality = (SYNC_STEP, *QUALITY_STEPS)
    if mode is Mode.QUICK:
        return (*quality, QUICK_TEST_STEP, _sphinx_step("doctest"))
    return (*quality, *STANDARD_STEPS)


def run_plan(mode: Mode, repository: Path = REPOSITORY_ROOT) -> int:
    plan = build_plan(mode)
    total_started = time.monotonic()
    print(f"aerocoeff local validation: {mode.value}", flush=True)
    for index, (name, command) in enumerate(plan, start=1):
        print(f"\n[{index}/{len(plan)}] {name}", flush=True)
        print(f"$ {subprocess.list2cmdline(command)}", flush=True)
        step_started = time.monotonic()
        try:
            returncode = subprocess.run(list(command), cwd=repository).returncode
        except FileNotFoundError as error:
            print(f"FAILED: {name} ({error})", file=sys.stderr)
            return 127
        elapsed = time.monotonic() - step_started
        if returncode != 0:
            print(f"FAILED: {name} ({elapsed:.2f} s)", file=sys.stderr)
            print(f"\nFAILED: {mode.value} total", file=sys.stderr)
            return returncode
        print(f"PASSED: {name} ({elapsed:.2f} s)", flush=True)
    total_elapsed = time.monotonic() - total_started
    print(f"\nPASSED: {mode.value} total ({total_elapsed:.2f} s)", flush=True)
    return 0


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--quick",
        dest="mode",
        action="store_const",
        const=Mode.QUICK,
        help="run formatting, lint, mypy, pytest, and documentation doctests",
    )
    modes.add_argument(
        "--standard",
        dest="mode",
        action="store_const",
        const=Mode.STANDARD,
        help="run the push/PR gate: quick checks plus coverage, docs, and distribution build",
    )
    parser.set_defaults(mode=Mode.STANDARD)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    return run_plan(args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
