# Version: 0.6.12-supportbundle.2
"""Support-bundle builders with redaction-safe diagnostics content."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

SECRET_KEYS = {
    "token",
    "password",
    "api_key",
    "secret",
    "authorization",
    "x-runner-token",
    "pip_index_url",
    "pip_extra_index_url",
}


def _redact_key_value(key: str, value: Any) -> Any:
    """Redact known secret-like keys in nested mappings and lists."""
    key_l = str(key).lower()
    if any(secret in key_l for secret in SECRET_KEYS):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {str(k): _redact_key_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_key_value(key, v) for v in value]
    return value


def redacted_options_summary(opts: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted options summary suitable for diagnostics output."""
    return {str(k): _redact_key_value(str(k), v) for k, v in (opts or {}).items()}


def _tail_jsonl(path: Path, max_lines: int = 30) -> list[dict[str, Any]]:
    """Read up to ``max_lines`` JSONL entries from the end of file."""
    if not path.exists():
        return []

    recent_lines: deque[str] = deque(maxlen=max(0, int(max_lines)))
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                recent_lines.append(line.rstrip("\n"))
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for line in recent_lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            out.append(_redact_key_value("event", row))
    return out


def build_support_bundle(runner: Any) -> dict[str, Any]:
    """Build a redacted support bundle payload for add-on troubleshooting."""
    jobs_snapshot = runner.list_jobs()

    jobs = []
    for job in jobs_snapshot[:20]:
        status = job.status_dict()
        jobs.append(
            {
                "job_id": status.get("job_id"),
                "state": status.get("state"),
                "created_utc": status.get("created_utc"),
                "started_utc": status.get("started_utc"),
                "finished_utc": status.get("finished_utc"),
                "duration_seconds": status.get("duration_seconds"),
                "exit_code": status.get("exit_code"),
                "error": status.get("error"),
            }
        )

    audit_recent = _tail_jsonl(getattr(runner, "audit_log_path"), max_lines=50)
    return {
        "service": "pythonista_job_runner",
        "version": getattr(runner, "addon_version", "unknown"),
        "included": [
            "redacted_options_summary",
            "stats",
            "recent_jobs_metadata",
            "recent_audit_events",
            "queue_state_summary",
        ],
        "excluded": [
            "raw_job_payloads",
            "job_output_file_contents",
            "tokens_passwords_secrets",
            "supervisor_token",
        ],
        "options": redacted_options_summary(getattr(runner, "_opts", {}) or {}),
        "stats": runner.stats_dict(),
        "queue": {
            "jobs_total": len(jobs_snapshot),
            "jobs_running": sum(
                1 for job in jobs_snapshot if getattr(job, "state", "") == "running"
            ),
            "jobs_queued": sum(
                1 for job in jobs_snapshot if getattr(job, "state", "") == "queued"
            ),
            "jobs_error": sum(
                1 for job in jobs_snapshot if getattr(job, "state", "") == "error"
            ),
        },
        "recent_jobs": jobs,
        "audit_recent": audit_recent,
    }
