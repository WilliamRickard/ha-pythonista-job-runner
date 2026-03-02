# Version: 0.1.0

"""Command result schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class CommandError:
    """A serialisable error for a command result."""

    code: str
    message: str
    hint: str = ""
    http_status: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommandResult:
    """A serialisable command result."""

    ok: bool
    command: str
    started_at: str
    finished_at: str
    summary: str
    artifacts: list[str] = field(default_factory=list)
    run_dir: str = ""
    diagnostics_path: str = ""
    error: CommandError | None = None

    @staticmethod
    def now_iso() -> str:
        """Return current time as ISO-8601."""
        return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
