# Version: 0.6.13-examples.1
"""Scaffold placeholder job for 05_requirements_optional."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    """Write placeholder outputs for the scaffold example layout."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    status_text = (
        "Example 05_requirements_optional is a Phase 1 scaffold placeholder. "
        "The final implementation will be added in a later phase."
    )
    (outputs_dir / "status.txt").write_text(status_text + "\n", encoding="utf-8")
    payload = {
        "example_id": "05_requirements_optional",
        "title": "Optional requirements install",
        "track": "core",
        "status": "scaffold",
        "requires_toolchain": False,
    }
    (outputs_dir / "details.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Running scaffold placeholder: {payload['example_id']}")
    print(status_text)


if __name__ == "__main__":
    main()
