# Version: 0.6.13-examples.2
"""Live logging example that emits deterministic progress over time."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

STEP_MESSAGES = [
    "prepare workspace",
    "load sample configuration",
    "validate inputs",
    "start processing",
    "write checkpoint",
    "verify checkpoint",
    "finalise outputs",
    "complete job",
]
STDERR_STEPS = {3, 6}
DEFAULT_SLEEP_SECONDS = 1.0


def _sleep_seconds() -> float:
    """Return the configured sleep interval between progress updates."""
    raw_value = os.environ.get("PJR_EXAMPLE_SLEEP_SECONDS", str(DEFAULT_SLEEP_SECONDS))
    try:
        return max(0.0, float(raw_value))
    except ValueError:
        return DEFAULT_SLEEP_SECONDS


def main() -> None:
    """Emit deterministic stdout and stderr lines and write summary outputs."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    sleep_seconds = _sleep_seconds()
    timeline_lines: list[str] = []
    stderr_count = 0

    print("live-logs example starting", flush=True)
    for step_number, message in enumerate(STEP_MESSAGES, start=1):
        line = f"step {step_number}/{len(STEP_MESSAGES)}: {message}"
        print(line, flush=True)
        timeline_lines.append(line)
        if step_number in STDERR_STEPS:
            stderr_line = f"warning at step {step_number}: simulated stderr event"
            print(stderr_line, file=sys.stderr, flush=True)
            stderr_count += 1
        time.sleep(sleep_seconds)

    print("live-logs example finished", flush=True)
    timeline_lines.append("job complete")
    progress_summary = {
        "example_id": "02_live_logs_progress",
        "step_count": len(STEP_MESSAGES),
        "stderr_event_count": stderr_count,
        "status": "complete",
    }
    (outputs_dir / "progress_summary.json").write_text(
        json.dumps(progress_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (outputs_dir / "progress_timeline.txt").write_text(
        "\n".join(timeline_lines) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
