# Version: 0.6.13-examples-runner.4
"""Compatibility wrapper for the shared Pythonista example runner script."""

from __future__ import annotations

from pathlib import Path
import runpy
import sys


def main() -> None:
    """Run the shared example runner from the tools folder."""
    tools_dir = Path(__file__).resolve().parent / "tools"
    sys.path.insert(0, str(tools_dir))
    runpy.run_path(str(tools_dir / "pythonista_run_example_job.py"), run_name="__main__")


if __name__ == "__main__":
    main()
