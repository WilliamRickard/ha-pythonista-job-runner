# Version: 0.6.12-refactor.1
"""File system safety helpers.

These helpers avoid following symlinks where possible.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


def safe_write_text_no_symlink(path: Path, text: str) -> None:
    """Write text to a path, avoiding symlink-following where possible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
        fd = os.open(str(path), flags, 0o660)
        with os.fdopen(fd, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)
    except Exception:
        # Fallback: best-effort with a pre-check.
        try:
            if path.exists() and path.is_symlink():
                return
        except Exception:
            return
        try:
            path.write_text(text, encoding="utf-8", errors="replace")
        except Exception:
            return


def safe_zip_write(zf: zipfile.ZipFile, path: Path, arcname: str, base_dir: Path) -> None:
    """Add a file to a zip if it is a regular file inside base_dir (no symlinks)."""
    try:
        if not path.exists():
            return
        if path.is_symlink():
            return
        if not path.is_file():
            return
        base = base_dir.resolve()
        rp = path.resolve()
        if rp != base and not str(rp).startswith(str(base) + os.sep):
            return
        zf.write(path, arcname)
    except Exception:
        return
