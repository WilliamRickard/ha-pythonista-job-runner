# Version: 0.6.13-examples.3
"""Long-running job example intended for cancellation testing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import time

DEFAULT_HEARTBEATS = 90
DEFAULT_SLEEP_SECONDS = 1.0
_CANCEL_REQUESTED = False
_CANCEL_SIGNAL = None


def _handle_signal(signum: int, _frame: object) -> None:
    """Record that cancellation has been requested by a process signal."""
    global _CANCEL_REQUESTED, _CANCEL_SIGNAL
    _CANCEL_REQUESTED = True
    _CANCEL_SIGNAL = signum
    print(f"Cancellation signal received: {signum}", flush=True)


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def _env_int(name: str, default: int) -> int:
    """Return an integer environment override when present."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return max(1, int(raw_value))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    """Return a float environment override when present."""
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return default


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON with indentation and stable key ordering."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_progress(outputs_dir: Path, heartbeat_lines: list[str], completed: int, total: int) -> None:
    """Persist current progress so partial outputs survive cancellation."""
    (outputs_dir / "heartbeat_history.txt").write_text("\n".join(heartbeat_lines) + "\n", encoding="utf-8")
    payload = {
        "example_id": "04_cancel_long_running_job",
        "heartbeat_count_completed": completed,
        "heartbeat_count_total": total,
        "cancellation_requested": _CANCEL_REQUESTED,
        "cancel_signal": _CANCEL_SIGNAL,
    }
    _write_json(outputs_dir / "last_known_progress.json", payload)


def main() -> None:
    """Run a long heartbeat loop and preserve useful partial outputs."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    total_heartbeats = _env_int("PJR_CANCEL_TOTAL_HEARTBEATS", DEFAULT_HEARTBEATS)
    sleep_seconds = _env_float("PJR_CANCEL_SLEEP_SECONDS", DEFAULT_SLEEP_SECONDS)
    heartbeat_lines: list[str] = []

    print("long-running cancellation example starting", flush=True)
    for heartbeat in range(1, total_heartbeats + 1):
        line = f"heartbeat {heartbeat}/{total_heartbeats}: job still running"
        print(line, flush=True)
        heartbeat_lines.append(line)
        if heartbeat % 5 == 0:
            print(f"checkpoint after {heartbeat} heartbeats", flush=True)
        _write_progress(outputs_dir, heartbeat_lines, heartbeat, total_heartbeats)
        time.sleep(sleep_seconds)
        if _CANCEL_REQUESTED:
            cancellation_note = (
                "Cancellation was requested. Partial progress was written to "
                "outputs/heartbeat_history.txt and outputs/last_known_progress.json."
            )
            (outputs_dir / "cancellation_note.txt").write_text(cancellation_note + "\n", encoding="utf-8")
            print("Stopping after cancellation request", flush=True)
            raise KeyboardInterrupt(f"Cancellation requested via signal {_CANCEL_SIGNAL}")

    completed_payload = {
        "example_id": "04_cancel_long_running_job",
        "heartbeat_count_completed": total_heartbeats,
        "status": "completed_without_cancellation",
    }
    _write_json(outputs_dir / "completed_summary.json", completed_payload)
    print("long-running cancellation example finished without cancellation", flush=True)


if __name__ == "__main__":
    main()
