# Version: 0.6.13-examples.1
"""Cached per-job requirements example that highlights reuse diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

import pjr_demo_formatsize  # type: ignore

SAMPLE_SIZES = {
    "backup_snapshot.tar": 512,
    "camera_archive.zip": 1536,
    "grafana_export.json": 1250000,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON with indentation and stable key ordering."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "
", encoding="utf-8")


def main() -> None:
    """Write deterministic outputs and point the user to add-on package diagnostics."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    formatted = {name: pjr_demo_formatsize.naturalsize(size) for name, size in SAMPLE_SIZES.items()}
    _write_json(
        outputs_dir / "cache_probe.json",
        {
            "dependency_mode_hint": "per_job",
            "example_id": "11_cached_per_job_requirements",
            "files": formatted,
            "next_check": "Run the same example again and compare package/package_diagnostics.json for reused_venv.",
            "requirements_source": "vendored local wheel",
        },
    )
    summary_lines = [
        "# Cached per-job requirements example",
        "",
        "This job uses per-job requirements with a vendored wheel so it stays offline-safe.",
        "",
        "Run it twice. The second run should normally show package reuse in the add-on diagnostics.",
        "",
        "Check these add-on result files after each run:",
        "- `package/package_diagnostics.json`",
        "- `summary.txt`",
        "- `result_manifest.json`",
        "",
        "Generated sizes:",
    ]
    for name in sorted(formatted):
        summary_lines.append(f"- `{name}` -> `{formatted[name]}`")
    (outputs_dir / "summary.md").write_text("
".join(summary_lines) + "
", encoding="utf-8")
    print("Cached per-job requirements example completed.", flush=True)
    for name in sorted(formatted):
        print(f"{name}: {formatted[name]}", flush=True)


if __name__ == "__main__":
    main()
