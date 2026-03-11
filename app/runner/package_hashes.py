# Version: 0.6.13-package-hashes.1
"""Helpers for validating hash-enforced requirements lock files."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _logical_lines(path: Path) -> list[tuple[int, str]]:
    """Return logical requirement lines with continuation handling."""
    raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[tuple[int, str]] = []
    current = ""
    first_line = 1
    for idx, raw in enumerate(raw_lines, start=1):
        line = raw.rstrip()
        if not current:
            first_line = idx
        if line.endswith("\\"):
            current += line[:-1].rstrip() + " "
            continue
        current += line
        out.append((first_line, current.strip()))
        current = ""
    if current.strip():
        out.append((first_line, current.strip()))
    return out


def _requires_hash(line: str) -> bool:
    """Return whether one logical requirement line should include hashes."""
    value = str(line or "").strip()
    if not value or value.startswith("#"):
        return False
    if value.startswith(("-r ", "--requirement ", "-c ", "--constraint ")):
        return False
    if value.startswith(("--index-url", "--extra-index-url", "--find-links", "--trusted-host", "--no-index", "--only-binary", "--prefer-binary")):
        return False
    if value.startswith(("./", "../", "/")):
        return False
    if "://" in value or value.startswith("file:"):
        return False
    return True


def validate_requirements_lock_hashes(path: Path) -> dict[str, Any]:
    """Validate that a lock file contains hashes on each package requirement line."""
    issues: list[dict[str, Any]] = []
    for line_no, logical in _logical_lines(path):
        if not _requires_hash(logical):
            continue
        if " --hash=" in logical or logical.startswith("--hash="):
            continue
        issues.append(
            {
                "line": line_no,
                "text": logical,
                "reason": "missing_hash",
            }
        )
    return {
        "status": "ok" if not issues else "error",
        "path": str(path),
        "issue_count": len(issues),
        "issues": issues,
    }
