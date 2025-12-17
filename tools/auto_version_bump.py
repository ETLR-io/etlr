#!/usr/bin/env python
"""Automatic version bump utility for ETLR CLI.

Rules:
- If any staged commit message (latest commit if run pre-commit) contains 'BREAKING:' or 'MAJOR:' -> major bump.
- Else if commit message contains 'feat:' or 'MINOR:' -> minor bump.
- Else -> patch bump.

The script updates pyproject.toml in place.
It is idempotent per run (re-reading updated version only once).

Usage (pre-commit hook):
  python tools/auto_version_bump.py

Environment overrides:
  FORCE_BUMP=major|minor|patch  force a particular bump.
  NO_BUMP=1                     skip bump (useful in CI scenarios).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

SEMVER_RE = re.compile(r"^version\s*=\s*\"(\d+)\.(\d+)\.(\d+)\"", re.MULTILINE)


def read_version() -> tuple[int, int, int, str]:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = SEMVER_RE.search(text)
    if not m:
        raise SystemExit("Could not find version in pyproject.toml")
    major, minor, patch = map(int, m.groups())
    return major, minor, patch, text


def write_version(text: str, new_version: str) -> None:
    new_text = SEMVER_RE.sub(f'version = "{new_version}"', text, count=1)
    PYPROJECT.write_text(new_text, encoding="utf-8")
    print(f"Version bumped to {new_version}")  # noqa: T201


def latest_commit_message() -> str:
    try:
        return subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
    except subprocess.CalledProcessError:
        return ""


def decide_bump() -> str:
    forced = os.getenv("FORCE_BUMP")
    if forced in {"major", "minor", "patch"}:
        return forced
    if os.getenv("NO_BUMP"):
        return "none"
    msg = latest_commit_message().lower()
    if "breaking:" in msg or "major:" in msg:
        return "major"
    if "feat:" in msg or "minor:" in msg:
        return "minor"
    return "patch"


def bump(major: int, minor: int, patch: int, kind: str) -> str:
    if kind == "none":
        return f"{major}.{minor}.{patch}"
    if kind == "major":
        major += 1
        minor = 0
        patch = 0
    elif kind == "minor":
        minor += 1
        patch = 0
    elif kind == "patch":
        patch += 1
    return f"{major}.{minor}.{patch}"


def main():
    kind = decide_bump()
    if kind == "none":
        print("Skipping version bump (NO_BUMP set)")  # noqa: T201
        return 0
    major, minor, patch, text = read_version()
    new_version = bump(major, minor, patch, kind)
    if f"{major}.{minor}.{patch}" == new_version:
        print("Version unchanged")  # noqa: T201
        return 0
    write_version(text, new_version)
    # Stage pyproject.toml so the bump is part of the commit
    try:
        subprocess.check_call(["git", "add", str(PYPROJECT)])
    except subprocess.CalledProcessError:
        print("Warning: failed to stage pyproject.toml")  # noqa: T201
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
