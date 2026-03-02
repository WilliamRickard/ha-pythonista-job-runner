"""Smoke tests that ensure the app modules are syntactically valid."""

from __future__ import annotations

import py_compile
from pathlib import Path


def test_app_modules_compile() -> None:
    """All app/*.py files should compile.

    This catches syntax errors without relying on imports, so pytest collection
    remains robust.
    """
    app_dir = (Path(__file__).resolve().parent.parent / "app").resolve()
    for path in sorted(app_dir.glob("*.py")):
        py_compile.compile(str(path), doraise=True)
