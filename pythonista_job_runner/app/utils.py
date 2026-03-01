# Version: 0.1.0
from __future__ import annotations

"""
Utilities for Pythonista Job Runner.

Keep this module dependency-light; it is used by both runner_core and http_api.
"""

import codecs
import hashlib
import ipaddress
import logging
import os
import stat
import threading
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())

_COPY_CHUNK_SIZE = 1024 * 1024


def utc_now() -> str:
    """Return UTC timestamp in the format used by this add-on."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> Optional[float]:
    """Parse our UTC timestamp format and return epoch seconds.

    Accepted inputs:
    - The native format emitted by utc_now(), for example 2026-03-01T12:34:56Z
    - ISO 8601 strings without a trailing 'Z'
    - ISO 8601 strings with an explicit offset, for example +01:00

    Returns None for empty/invalid values.
    """
    if not s:
        return None

    s2 = s[:-1] if s.endswith("Z") else s
    try:
        dt = datetime.fromisoformat(s2)
    except (TypeError, ValueError):
        return None

    # If timezone info is present, normalise to UTC. If not, assume UTC.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    return dt.timestamp()


def clamp_int(v: Optional[str], default: int, lo: int, hi: int) -> int:
    """Parse an integer from v and clamp it to [lo, hi].

    Returns default when v is None/empty or cannot be parsed as an integer.
    """
    if v is None or v == "":
        return default
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _read_utf8_head(path: Path, head_chars: int) -> str:
    if head_chars <= 0:
        return ""
    # UTF-8 is up to 4 bytes per code point; add a small safety margin.
    max_bytes = head_chars * 4 + 64
    with path.open("rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="replace")[:head_chars]


def _read_utf8_tail(path: Path, tail_chars: int) -> str:
    if tail_chars <= 0:
        return ""
    max_bytes = tail_chars * 4 + 64
    size = path.stat().st_size
    read_bytes = min(size, max_bytes)
    with path.open("rb") as f:
        if read_bytes < size:
            f.seek(size - read_bytes)
        data = f.read(read_bytes)
    return data.decode("utf-8", errors="replace")[-tail_chars:]


def read_head_tail_text(
    path: Path,
    head_chars: int,
    tail_chars: int,
) -> Dict[str, str]:
    """Read the head and tail of a UTF-8-ish text file (best-effort).

    This avoids reading the whole file into memory by reading bounded byte
    ranges.
    """
    if not path.exists():
        return {"head": "", "tail": ""}
    try:
        head = _read_utf8_head(path, head_chars)
        tail = _read_utf8_tail(path, tail_chars)
        return {"head": head, "tail": tail}
    except OSError:
        return {"head": "", "tail": ""}


def sha256_file(path: Path, chunk_size: int = _COPY_CHUNK_SIZE) -> str:
    """Compute SHA-256 hex digest of a file."""
    if chunk_size <= 0:
        chunk_size = _COPY_CHUNK_SIZE
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
        self._lock = threading.Lock()
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def append_bytes(self, b: bytes) -> None:
        if not b or self._max_chars <= 0:
            return
        with self._lock:
            s = self._decoder.decode(b)
            if not s:
                return
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
            text = _read_utf8_tail(path, self._max_chars)
        except OSError:
            return
        with self._lock:
            self._buf = text
            # Reset decoder state so subsequent append_bytes starts cleanly.
            self._decoder.reset()


def read_file_delta(
    path: Path,
    start: int,
    max_bytes: int,
) -> Tuple[str, int, int]:
    """Read up to max_bytes from file starting at byte offset start.

    Returns: (text, new_offset, file_size_bytes)

    Notes:
    - Decodes using UTF-8 with replacement. If start falls mid-codepoint,
      the first character may be '�'.
    - new_offset is a byte offset, suitable for the next call.
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
                if max_bytes > 0:
                    data = f.read(max_bytes)
        text = data.decode("utf-8", errors="replace")
        new_off = start + len(data)
        return text, new_off, size
    except OSError:
        return "", start, 0


def file_tail_text(path: Path, max_chars: int) -> str:
    """Return tail of a text file (chars). Best-effort."""
    if max_chars <= 0 or not path.exists():
        return ""
    try:
        return _read_utf8_tail(path, max_chars)
    except OSError:
        return ""


def stream_file(
    path: Path,
    write_fn: Callable[[bytes], None],
    chunk_size: int = _COPY_CHUNK_SIZE,
) -> None:
    """Stream a file to a write function (write_fn), chunked."""
    if chunk_size <= 0:
        chunk_size = _COPY_CHUNK_SIZE
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


def safe_extract_zip_bytes(
    zip_bytes: bytes,
    dst_dir: Path,
    limits: SafeZipLimits,
) -> None:
    """Safely extract a zip into dst_dir with guardrails.

    Rejects:
    - absolute paths
    - drive-letter paths (Windows)
    - any '..' traversal
    - symlinks

    Enforces limits based on zip header file_size values.
    """
    if dst_dir.exists() and not dst_dir.is_dir():
        raise RuntimeError("dst_dir_exists_and_is_not_directory")

    dst_dir.mkdir(parents=True, exist_ok=True)
    dst_root = dst_dir.resolve()

    with zipfile.ZipFile(BytesIO(zip_bytes), "r") as zf:
        infos = zf.infolist()
        if len(infos) > limits.max_members:
            raise RuntimeError(
                f"zip_too_many_members: {len(infos)} > {limits.max_members}"
            )

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
            if name.startswith("/") or (len(name) >= 2 and name[1] == ":"):
                raise RuntimeError(f"zip_bad_path: {zi.filename}")

            parts = [p for p in name.split("/") if p not in ("", ".")]
            if not parts:
                if zi.is_dir():
                    continue
                raise RuntimeError(f"zip_empty_member_path: {zi.filename}")
            if any(p == ".." for p in parts):
                raise RuntimeError(f"zip_path_traversal: {zi.filename}")

            rel = Path(*parts)
            out_path = (dst_root / rel).resolve()
            try:
                is_safe = out_path.is_relative_to(dst_root)
            except AttributeError:
                # Python < 3.9 fallback
                root_prefix = str(dst_root) + os.sep
                is_safe = str(out_path).startswith(root_prefix)
                is_safe = is_safe or out_path == dst_root

            if not is_safe:
                raise RuntimeError(f"zip_path_escape: {zi.filename}")

            if zi.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue

            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(zi, "r") as src, out_path.open("wb") as dst:
                while True:
                    b = src.read(_COPY_CHUNK_SIZE)
                    if not b:
                        break
                    dst.write(b)


def ip_in_cidrs(ip_str: str, cidrs: List[str]) -> bool:
    """Return True if ip_str is contained in any CIDR in cidrs.

    Invalid CIDR entries are skipped (and logged at warning level).
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for c in cidrs:
        try:
            net = ipaddress.ip_network(c, strict=False)
        except ValueError:
            _logger.warning("Invalid CIDR entry skipped: %s", c)
            continue
        if ip in net:
            return True
    return False
