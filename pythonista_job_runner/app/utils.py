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
    """
    Get the current UTC timestamp in the add-on's canonical format.
    
    Returns:
        utc (str): Timestamp formatted as "YYYY-MM-DDTHH:MM:SSZ" (UTC).
    """
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(s: str) -> Optional[float]:
    """
    Parse a UTC timestamp in the module's ISO-like format and produce epoch seconds.
    
    Parameters:
        s (str): Timestamp string in ISO 8601 form; a trailing "Z" is accepted to denote UTC. An empty string will be treated as missing.
    
    Returns:
        epoch_seconds (Optional[float]): Seconds since the UNIX epoch (UTC) on success, `None` if the input is empty or cannot be parsed.
    """
    try:
        if not s:
            return None
        s2 = s[:-1] if s.endswith("Z") else s
        dt = datetime.fromisoformat(s2)
        return dt.replace(tzinfo=timezone.utc).timestamp()
    except Exception:
        return None


def clamp_int(v: Optional[str], default: int, lo: int, hi: int) -> int:
    """
    Parse a text value as an integer and clamp it to the inclusive range, falling back to a default on invalid input.
    
    Parameters:
    	v (Optional[str]): Text to parse as an integer; if None or empty the `default` is used.
    	default (int): Value returned when `v` is missing or cannot be parsed as an integer.
    	lo (int): Minimum allowed value (inclusive).
    	hi (int): Maximum allowed value (inclusive).
    
    Returns:
    	int: `default` if `v` is None, empty, or not a valid integer; otherwise the parsed integer constrained to the range [lo, hi].
    """
    if v is None or v == "":
        return default
    try:
        n = int(str(v).strip())
    except Exception:
        return default
    return max(lo, min(hi, n))


def read_head_tail_text(path: Path, head_chars: int, tail_chars: int) -> Dict[str, str]:
    """
    Return the first `head_chars` and last `tail_chars` characters of a text file as UTF-8.
    
    If the file does not exist, is empty, or cannot be read, both values are empty strings. The file is decoded as UTF-8 with replacement for invalid bytes.
    
    Parameters:
        path (Path): Path to the file to read.
        head_chars (int): Number of characters to include from the start; non-positive values yield an empty head.
        tail_chars (int): Number of characters to include from the end; non-positive values yield an empty tail.
    
    Returns:
        dict: A mapping with keys `"head"` and `"tail"` containing the requested text snippets.
    """
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
    """
    Compute the SHA-256 hex digest of a file's contents.
    
    Parameters:
        path (Path): Path to the file to hash.
        chunk_size (int): Size in bytes of each read operation; used to limit memory usage when hashing large files.
    
    Returns:
        hex_digest (str): Lowercase hexadecimal SHA-256 digest of the file contents.
    """
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
        """
        Initialise the tail buffer with a maximum character capacity.
        
        Parameters:
            max_chars (int): Maximum number of characters the buffer will retain. If `max_chars` is less than
                or equal to zero the buffer will not retain content.
        """
        self._max_chars = max_chars
        self._buf = ""
        self._lock = __import__("threading").Lock()

    def append_bytes(self, b: bytes) -> None:
        """
        Append decoded UTF-8 bytes to the internal tail buffer, trimming the buffer to the configured maximum size.
        
        Appends the provided byte sequence (decoded as UTF-8 with replacement for invalid sequences) to the buffer under the instance lock, ensuring thread-safe mutation. If the buffer exceeds the maximum character capacity it is truncated to keep only the most recent characters. Passing an empty bytes object is a no-op.
        
        Parameters:
            b (bytes): Byte sequence to append; decoded as UTF-8 with replacement for malformed input.
        """
        if not b:
            return
        s = b.decode("utf-8", errors="replace")
        with self._lock:
            self._buf += s
            if len(self._buf) > self._max_chars:
                self._buf = self._buf[-self._max_chars :]

    def get(self) -> str:
        """
        Return the current contents of the tail buffer.
        
        This method is thread-safe and returns a snapshot of the buffer's contents.
        
        Returns:
            str: The buffer contents.
        """
        with self._lock:
            return self._buf

    def seed_from_file_tail(self, path: Path) -> None:
        """
        Seed the buffer with the final portion of a file's text, up to the buffer's maximum size.
        
        This performs a best-effort read of `path`: if `max_chars` is <= 0, the file does not exist, the file is empty, or a read error occurs, the method does nothing and no exception is raised. When successful, the file bytes are decoded as UTF-8 (replacement for invalid sequences) and the buffer is set to the last `max_chars` characters of that text.
        """
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
    """
    Read up to max_bytes from a file beginning at the given byte offset and return the read text and offsets.
    
    Parameters:
        path (Path): File to read.
        start (int): Byte offset to begin reading from; negative values are treated as zero.
        max_bytes (int): Maximum number of bytes to read.
    
    Returns:
        tuple: (text, new_offset, file_size_bytes) where `text` is the UTF-8 decoded content with invalid bytes replaced, `new_offset` is the byte offset immediately after the bytes read, and `file_size_bytes` is the total size of the file in bytes (returns 0 on error).
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
    """
    Return the last characters of a text file up to a given maximum.
    
    The file is decoded as UTF-8 with replacement for invalid sequences. If max_chars is less than or equal to zero, the file does not exist, the file is empty, or reading fails, an empty string is returned.
    
    Returns:
    	str: The final up to `max_chars` characters of the file, or an empty string on error or when `max_chars` <= 0.
    """
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
    """
    Stream a file's bytes to a writer function in fixed-size chunks.
    
    Read the file at `path` in binary mode and invoke `write_fn` with each chunk until end of file is reached.
    
    Parameters:
        path (Path): Path to the file to stream.
        write_fn (Callable[[bytes], Any]): Callable invoked with each bytes chunk read from the file.
        chunk_size (int): Maximum number of bytes to read per chunk; must be a positive integer.
    """
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
    """
    Determine whether a ZipInfo entry represents a Unix symbolic link.
    
    Detection is performed by inspecting the Unix mode bits encoded in ZipInfo.external_attr.
    
    Returns:
        `True` if the ZipInfo denotes a symbolic link, `False` otherwise.
    """
    mode = (zi.external_attr >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def safe_extract_zip_bytes(zip_bytes: bytes, dst_dir: Path, limits: SafeZipLimits) -> None:
    """
    Extract a ZIP archive from bytes into a destination directory while enforcing safety guardrails.
    
    Validates archive entries and aborts extraction on disallowed paths, symlinks or size limits to prevent traversal, symlink attacks and excessive uncompressed data.
    
    Parameters:
        zip_bytes (bytes): ZIP archive data.
        dst_dir (Path): Destination directory to extract into; created if missing.
        limits (SafeZipLimits): Guardrails for extraction (maximum members, total uncompressed bytes, per-member uncompressed bytes).
    
    Raises:
        RuntimeError: If any safety check fails, with one of the following messages:
            - "zip_too_many_members: {found} > {max}" when the archive contains more entries than allowed.
            - "zip_symlink_not_allowed" when a zip entry represents a symlink.
            - "zip_invalid_size" when a zip entry reports a negative uncompressed size.
            - "zip_member_too_large: {filename}" when a single member exceeds per-member size limit.
            - "zip_total_uncompressed_too_large" when the summed uncompressed sizes exceed the total limit.
            - "zip_bad_path: {filename}" for absolute or drive-letter paths.
            - "zip_path_traversal: {filename}" when a path contains ".." traversal.
            - "zip_path_escape: {filename}" when an entry would extract outside dst_dir.
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
    """
    Check whether an IP address belongs to any of the given CIDR networks.
    
    Parameters:
        ip_str (str): IP address as a string (IPv4 or IPv6). If this is not a valid IP the function returns `False`.
        cidrs (List[str]): Iterable of CIDR network strings (for example '192.0.2.0/24' or '2001:db8::/32'); invalid CIDR entries are ignored.
    
    Returns:
        bool: `True` if the parsed IP is contained in at least one valid CIDR network from `cidrs`, `False` otherwise.
    """
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

