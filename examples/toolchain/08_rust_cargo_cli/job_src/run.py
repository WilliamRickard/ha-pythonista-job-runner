# Version: 0.6.13-examples.1
"""Scaffold placeholder job for 08_rust_cargo_cli."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    """Write placeholder outputs for the scaffold example layout."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    status_text = (
        "Example 08_rust_cargo_cli is a Phase 1 scaffold placeholder. "
        "The final implementation will be added in a later phase."
    )
    (outputs_dir / "status.txt").write_text(status_text + "\n", encoding="utf-8")
    payload = {
        "example_id": "08_rust_cargo_cli",
        "title": "Rust Cargo CLI",
        "track": "toolchain",
        "status": "scaffold",
        "requires_toolchain": True,
    }
    (outputs_dir / "details.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Running scaffold placeholder: {payload['example_id']}")
    print(status_text)


if __name__ == "__main__":
    main()
