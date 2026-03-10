# Version: 0.6.13-examples.2
"""Minimal hello-world example job for Pythonista Job Runner."""

from __future__ import annotations

import json
from pathlib import Path

GREETING = "Hello from Pythonista Job Runner example 01."


def main() -> None:
    """Write a deterministic hello-world output bundle."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)

    hello_path = outputs_dir / "hello.txt"
    hello_path.write_text(GREETING + "\n", encoding="utf-8")

    payload = {
        "example_id": "01_hello_world",
        "title": "Hello world",
        "track": "core",
        "status": "implemented",
        "requires_toolchain": False,
        "files_written": ["outputs/hello.txt"],
        "greeting": GREETING,
    }
    details_path = outputs_dir / "details.json"
    details_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("Starting example 01_hello_world")
    print(f"Wrote {hello_path.as_posix()}")
    print(f"Wrote {details_path.as_posix()}")
    print("Example 01_hello_world completed successfully")


if __name__ == "__main__":
    main()
