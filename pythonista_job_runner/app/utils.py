from __future__ import annotations

"""
Utilities for Pythonista Job Runner.

Keep this module dependency-light; it is used by both runner_core and http_api.
"""

import hashlib
import ipaddress
import json
import os
import stat
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def utc_now() -> str:
    """Return UTC timestamp in the format used by this add-on."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> Optional[float]:
    """Parse our UTC timestamp format and return epoch seconds."""
    try:
        if not s:
            return None
        s2 = s[:-1] if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        return dt.replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return None


def clamp_int(v: Optional[str], default: int, lo: int, hi: int) -> int:
    if v is None or v == "":
        return default
    try:
        n = int(str(v).strip())
    except Exception:
        return default
    return max(lo, min(hi, n))


def read_head_tail_text(path: Path, head_chars: int, tail_chars: int) -> Dict[str, str]:
    if not path.exists():
        return {"head": "", "tail": ""}
    try:
        data = path.read_bytes()
    except Exception:
        return {"head": "", "tail": ""}
    if not data:
        return {"head": "", "tail": ""}
    text = data.decode("utf-8", errors="replace")
    head = text[:head_chars] if head_chars > 0 else ""
    tail = text[-tail_chars:] if tail_chars > 0 else ""
    return {"head": head, "tail": tail}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class TailBuffer:
    """A small in-memory tail buffer (chars). Thread-safe."""

    def __init__(self, max_chars: int) -> None:
        self._max_chars = max_chars
        self._buf = ""
        self._lock = __import__("threading").Lock()

    def append_bytes(self, b: bytes) -> None:
        if not b:
            return
        s = b.decode("utf-8", errors="replace")
        with self._lock:
            self._buf += s
            if len(self._buf) > self._max_chars:
                self._buf = self._buf[-self._max_chars :]

    def get(self) -> str:
        with self._lock:
            return self._buf

    def seed_from_file_tail(self, path: Path) -> None:
        """Seed buffer from the tail of a file (best-effort)."""
        if self._max_chars <= 0 or not path.exists():
            return
        try:
            data = path.read_bytes()
        except Exception:
            return
        if not data:
            return
        text = data.decode("utf-8", errors="replace")
        with self._lock:
            self._buf = text[-self._max_chars :]


def read_file_delta(path: Path, start: int, max_bytes: int) -> Tuple[str, int, int]:
    """Read up to max_bytes from file starting at byte offset start.

    Returns: (text, new_offset, file_size_bytes)
    """
    try:
        if start < 0:
            start = 0
        data = b""
        size = 0
        if path.exists():
            size = path.stat().st_size
            with path.open("rb") as f:
                if start > 0:
                    f.seek(start)
                data = f.read(max_bytes)
        text = data.decode("utf-8", errors="replace")
        new_off = start + len(data)
        return text, new_off, size
    except Exception:
        return "", start, 0


def file_tail_text(path: Path, max_chars: int) -> str:
    """Return tail of a text file (chars). Best-effort."""
    if max_chars <= 0 or not path.exists():
        return ""
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    if not data:
        return ""
    text = data.decode("utf-8", errors="replace")
    return text[-max_chars:]


def stream_file(path: Path, write_fn, chunk_size: int = 1024 * 1024) -> None:
    """Stream a file to a write function (write_fn), chunked."""
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            write_fn(b)


@dataclass(frozen=True)
class SafeZipLimits:
    max_members: int = 2000
    max_total_uncompressed: int = 200 * 1024 * 1024
    max_single_uncompressed: int = 50 * 1024 * 1024


def _is_symlink_member(zi: zipfile.ZipInfo) -> bool:
    # Unix symlink bit is stored in the upper 16 bits of external_attr.
    mode = (zi.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def safe_extract_zip_bytes(zip_bytes: bytes, dst_dir: Path, limits: SafeZipLimits) -> None:
    """Safely extract a zip into dst_dir with guardrails.

    Rejects:
    - absolute paths
    - drive-letter paths (Windows)
    - any '..' traversal
    - symlinks
    Enforces limits based on zip header file_size values.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        infos = zf.infolist()
        if len(infos) > limits.max_members:
            raise RuntimeError(f"zip_too_many_members: {len(infos)} > {limits.max_members}")

        total = 0
        for zi in infos:
            if _is_symlink_member(zi):
                raise RuntimeError("zip_symlink_not_allowed")
            if zi.file_size < 0:
                raise RuntimeError("zip_invalid_size")
            if zi.file_size > limits.max_single_uncompressed:
                raise RuntimeError(f"zip_member_too_large: {zi.filename}")
            total += int(zi.file_size)
            if total > limits.max_total_uncompressed:
                raise RuntimeError("zip_total_uncompressed_too_large")

            name = zi.filename.replace("\\", "/")
            # disallow absolute and drive-letter
            if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
                raise RuntimeError(f"zip_bad_path: {zi.filename}")
            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts:
                if zi.is_dir():
                    continue
                raise RuntimeError(f"zip_empty_member_path: {zi.filename}")
            if any(p == ".." for p in parts):
                raise RuntimeError(f"zip_path_traversal: {zi.filename}")

            out_path = (dst_dir / "/".join(parts)).resolve()
            if not str(out_path).startswith(str(dst_dir.resolve()) + os.sep) and out_path != dst_dir.resolve():
                raise RuntimeError(f"zip_path_escape: {zi.filename}")

            if zi.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(zi, "r") as src, out_path.open("wb") as dst:
                    while True:
                        b = src.read(1024 * 1024)
                        if not b:
                            break
                        dst.write(b)


def ip_in_cidrs(ip_str: str, cidrs: List[str]) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except Exception:
        return False
    for c in cidrs:
        try:
            net = ipaddress.ip_network(c, strict=False)
        except Exception:
            continue
        if ip in net:
            return True
    return False

