"""Unit tests for safe zip extraction."""

from __future__ import annotations

import io
import stat
import zipfile
from pathlib import Path

import pytest

from utils import SafeZipLimits, safe_extract_zip_bytes


def _zip_with_member(name: str, content: str = "x") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, content)
    return buf.getvalue()


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    z = _zip_with_member("../evil.txt", "nope")
    with pytest.raises(RuntimeError, match=r"zip_(path_traversal|path_escape)"):
        safe_extract_zip_bytes(z, tmp_path / "out", SafeZipLimits())


def test_safe_extract_rejects_absolute_paths(tmp_path: Path) -> None:
    z = _zip_with_member("/abs.txt", "nope")
    with pytest.raises(RuntimeError, match=r"zip_bad_path"):
        safe_extract_zip_bytes(z, tmp_path / "out", SafeZipLimits())


def test_safe_extract_rejects_windows_drive_paths(tmp_path: Path) -> None:
    z = _zip_with_member("C:\\evil.txt", "nope")
    with pytest.raises(RuntimeError, match=r"zip_bad_path"):
        safe_extract_zip_bytes(z, tmp_path / "out", SafeZipLimits())


def test_safe_extract_rejects_symlinks(tmp_path: Path) -> None:
    buf = io.BytesIO()
    zi = zipfile.ZipInfo("link")
    zi.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(zi, "target")

    with pytest.raises(RuntimeError, match=r"zip_symlink_not_allowed"):
        safe_extract_zip_bytes(buf.getvalue(), tmp_path / "out", SafeZipLimits())


def test_safe_extract_allows_normal_files(tmp_path: Path) -> None:
    z = _zip_with_member("a/b/run.py", "print('ok')\n")
    out = tmp_path / "out"
    safe_extract_zip_bytes(z, out, SafeZipLimits())

    assert (out / "a" / "b" / "run.py").exists()


def test_safe_extract_rejects_bad_zip_bytes(tmp_path: Path) -> None:
    with pytest.raises(zipfile.BadZipFile):
        safe_extract_zip_bytes(b"not-a-zip", tmp_path / "out", SafeZipLimits())


def test_safe_extract_rejects_too_many_members(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("run.py", "print('ok')\n")
        zf.writestr("extra.txt", "x")

    with pytest.raises(RuntimeError, match=r"zip_too_many_members"):
        safe_extract_zip_bytes(buf.getvalue(), tmp_path / "out", SafeZipLimits(max_members=1))
