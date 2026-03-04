# Version: 0.6.12-refactor.1
"""Home Assistant notification formatting."""

from __future__ import annotations

from typing import Callable, Optional

from utils import file_tail_text

from runner.redact import redact_pip_text


def notification_id(runner: object, j: object) -> Optional[str]:
    """Return notification id for this job, or None if disabled."""
    if not bool(getattr(runner, "notify_on_completion", False)):
        return None
    if str(getattr(runner, "notification_mode", "latest")) == "per_job":
        return f"{getattr(runner, 'notification_id_prefix')}_{getattr(j, 'job_id')}"
    return f"{getattr(runner, 'notification_id_prefix')}_latest"


def notify_done(runner: object, j: object, send_fn: Callable[[str, str, Optional[str]], None]) -> None:
    """Send a completion notification via the provided send function."""
    if not bool(getattr(runner, "notify_on_completion", False)):
        return

    title = "Pythonista Job Runner"

    who = getattr(j, "submitted_by_display_name", None) or getattr(j, "submitted_by_name", None) or "unknown user"
    if getattr(j, "submitted_by_id", None):
        who = f"{who} ({getattr(j, 'submitted_by_id')})"

    base = getattr(j, "ingress_path", None) or ""
    job_link = ""
    if base:
        job_link = f"\n\n[Open Web UI]({base}/?job={getattr(j, 'job_id')})"

    excerpt = ""
    excerpt_chars = int(getattr(runner, "notification_excerpt_chars", 0))
    if excerpt_chars > 0:
        if getattr(j, "state") == "error":
            ex = file_tail_text(getattr(j, "stderr_path"), excerpt_chars)
            if not ex:
                ex = file_tail_text(getattr(j, "stdout_path"), excerpt_chars)
        else:
            ex = file_tail_text(getattr(j, "stdout_path"), excerpt_chars)

        if ex:
            ex = redact_pip_text(ex, [str(getattr(runner, "pip_index_url", "") or ""), str(getattr(runner, "pip_extra_index_url", "") or "")])
            excerpt = "\n\n```text\n" + ex[-excerpt_chars:] + "\n```"

    msg = (
        f"Job {getattr(j, 'job_id')} finished.\n"
        f"State: {getattr(j, 'state')}\n"
        f"Exit code: {getattr(j, 'exit_code')}\n"
        f"Error: {getattr(j, 'error')}\n"
        f"Duration (s): {getattr(j, 'duration_seconds')()}\n"
        f"Submitted by: {who}"
        f"{job_link}"
        f"{excerpt}"
    )

    send_fn(title, msg, notification_id(runner, j))
