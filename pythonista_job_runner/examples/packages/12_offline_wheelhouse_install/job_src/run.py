# Version: 0.6.13-examples.1
"""Offline wheelhouse example that expects the wheel to be imported into /config."""

from __future__ import annotations

import json
from pathlib import Path

import pjr_demo_formatsize  # type: ignore

SAMPLE_SIZES = {
    "energy_dashboard.csv": 768,
    "sensor_history.json": 2048,
    "year_end_archive.zip": 3600000,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON with indentation and stable key ordering."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "
", encoding="utf-8")


def main() -> None:
    """Write deterministic outputs for the offline wheelhouse workflow."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    formatted = {name: pjr_demo_formatsize.naturalsize(size) for name, size in SAMPLE_SIZES.items()}
    _write_json(
        outputs_dir / "offline_install_status.json",
        {
            "dependency_mode_hint": "per_job",
            "example_id": "12_offline_wheelhouse_install",
            "expected_install_source": "local_wheelhouse",
            "files": formatted,
            "requirements_source": "public wheelhouse import",
        },
    )
    summary_lines = [
        "# Offline wheelhouse install example",
        "",
        "This job does not bundle the wheel inside the zip.",
        "Instead, it expects the wheel to be copied into `/config/wheel_uploads/` first.",
        "",
        "Check `package/package_diagnostics.json` for `install_source: local_wheelhouse` or `local_only_status: ok`.",
        "",
        "Generated sizes:",
    ]
    for name in sorted(formatted):
        summary_lines.append(f"- `{name}` -> `{formatted[name]}`")
    (outputs_dir / "summary.md").write_text("
".join(summary_lines) + "
", encoding="utf-8")
    print("Offline wheelhouse install example completed.", flush=True)
    for name in sorted(formatted):
        print(f"{name}: {formatted[name]}", flush=True)


if __name__ == "__main__":
    main()
