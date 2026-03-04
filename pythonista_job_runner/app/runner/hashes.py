# Version: 0.6.12-refactor.1
"""Small hashing helpers used by the runner."""

from __future__ import annotations

import hashlib


def hashlib_sha256_bytes(b: bytes) -> str:
    """Return SHA-256 hex digest for bytes."""
    return hashlib.sha256(b).hexdigest()
