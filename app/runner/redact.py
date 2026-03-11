# Version: 0.6.12-refactor.1
"""Redaction helpers for pip output and URLs."""

from __future__ import annotations

import re
from typing import List


def redact_basic_auth_in_urls(text: str) -> str:
    """Redact basic-auth credentials in URLs within a string."""
    if not text:
        return text

    def _mask_authority(match: re.Match[str]) -> str:
        scheme = match.group(1)
        authority = match.group(2)
        if "@" not in authority:
            return match.group(0)

        userinfo, hostpart = authority.rsplit("@", 1)
        if ":" not in userinfo:
            return match.group(0)

        username, _sep, _password = userinfo.partition(":")
        return f"{scheme}{username}:***@{hostpart}"

    # Match scheme://<authority> and redact credentials in authority section only.
    return re.sub(r"(https?://)([^/\s]+)", _mask_authority, text)


def redact_common_query_secrets(text: str) -> str:
    """Redact common secret-like query parameters."""
    if not text:
        return text
    return re.sub(r"(?i)\b(token|password|passwd|api_key|apikey)=[^&\s]+", r"\1=***", text)


def redact_pip_text(text: str, urls: List[str]) -> str:
    """Redact likely secrets from pip output/status strings."""
    if not text:
        return text
    out = redact_common_query_secrets(redact_basic_auth_in_urls(text))
    for u in urls:
        try:
            raw = str(u or "")
            if not raw:
                continue
            red = redact_basic_auth_in_urls(raw)
            if raw != red:
                out = out.replace(raw, red)
        except Exception:
            continue
    return out
