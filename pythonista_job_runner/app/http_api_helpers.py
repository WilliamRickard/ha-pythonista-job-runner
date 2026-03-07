from __future__ import annotations

"""Helper utilities shared by the HTTP API request handler."""

import re
from typing import Any
from urllib.parse import urlparse


def parse_int(value: str | None, default: int) -> int:
    """Return `value` parsed as int, or `default` when parsing fails."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def job_id_from_path(path: str, prefix: str, suffix: str) -> str:
    """Extract a safe job id from a URL path for `prefix...suffix` routes."""
    path_only = urlparse(path).path
    if not path_only.startswith(prefix) or (suffix and not path_only.endswith(suffix)):
        return ""
    tail = path_only[len(prefix) :]
    if suffix:
        tail = tail[: -len(suffix)]
    job_id = tail.strip("/")
    if not job_id or "/" in job_id or job_id in (".", ".."):
        return ""
    return job_id


def normalised_content_type(content_type_header: str | None) -> str:
    """Return lower-cased media type without optional parameters."""
    return (content_type_header or "").split(";", 1)[0].strip().lower()


def is_allowed_content_type(content_type_header: str | None, allowed_types: set[str], *, optional: bool = True) -> bool:
    """Return whether the request content type is accepted by the allowlist."""
    content_type = normalised_content_type(content_type_header)
    if not content_type and optional:
        return True
    return content_type in allowed_types


def safe_runtime_error_code(exc: RuntimeError) -> str:
    """Return safe API error code derived from RuntimeError text."""
    err = str(exc).strip()
    primary = err.split(":", 1)[0].strip()
    if re.fullmatch(r"[a-z0-9_]+", primary):
        return primary
    return "job_creation_failed"


def info_payload(version: str) -> dict[str, Any]:
    """Return the service info payload for root and /info.json."""
    return {
        "service": "pythonista_job_runner",
        "version": version,
        "endpoints": {
            "health": "/health",
            "run": "POST /run",
            "tail": "/tail/<job_id>.json",
            "result": "/result/<job_id>.zip",
            "jobs": "/jobs.json",
            "job": "/job/<job_id>.json",
            "stdout": "/stdout/<job_id>.txt",
            "stderr": "/stderr/<job_id>.txt",
            "stats": "/stats.json",
            "purge": "POST /purge",
            "cancel": "POST /cancel/<job_id>",
            "delete": "DELETE /job/<job_id>",
        },
    }
