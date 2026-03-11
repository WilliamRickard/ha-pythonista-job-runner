# Version: 0.6.13-examples.4
"""Optional requirements example that installs a vendored offline dependency."""

from __future__ import annotations

import json
import os
from pathlib import Path

SAMPLE_SIZES = {
    "backup_snapshot.tar": 512,
    "camera_archive.zip": 1536,
    "grafana_export.json": 1250000,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON with indentation and stable key ordering."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_formatter_module():
    """Import the vendored dependency unless failure is forced for tests."""
    if os.environ.get("PJR_FORCE_MISSING_DEPENDENCY") == "1":
        raise ImportError("Forced missing dependency for test mode")
    import pjr_demo_formatsize  # type: ignore

    return pjr_demo_formatsize


def main() -> None:
    """Use the vendored dependency when installed, otherwise fail clearly."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    try:
        formatter = _load_formatter_module()
    except ImportError as exc:
        failure_payload = {
            "example_id": "05_requirements_optional",
            "dependency": "pjr_demo_formatsize",
            "status": "missing_dependency",
            "message": "Enable per-job requirements installation, then rerun the example.",
            "requirements_source": "local wheel",
        }
        _write_json(outputs_dir / "requirements_error.json", failure_payload)
        (outputs_dir / "next_steps.txt").write_text(
            "This example needs the vendored `pjr_demo_formatsize` wheel. Enable per-job requirements installation and rerun.\n",
            encoding="utf-8",
        )
        print("Dependency `pjr_demo_formatsize` is not available.", flush=True)
        raise RuntimeError(
            "pjr_demo_formatsize dependency missing. Enable per-job requirements installation and rerun."
        ) from exc

    formatted = {name: formatter.naturalsize(size) for name, size in SAMPLE_SIZES.items()}
    success_payload = {
        "example_id": "05_requirements_optional",
        "dependency": "pjr_demo_formatsize",
        "status": "dependency_available",
        "requirements_source": "local wheel",
        "files": formatted,
    }
    _write_json(outputs_dir / "humanized_sizes.json", success_payload)
    _write_json(
        outputs_dir / "requirements_status.json",
        {
            "example_id": "05_requirements_optional",
            "dependency": "pjr_demo_formatsize",
            "requirements_source": "local wheel",
            "status": "ok",
        },
    )
    summary_lines = [
        "# Optional requirements example",
        "",
        "The vendored `pjr_demo_formatsize` wheel was installed and imported successfully.",
        "",
        "Generated sizes:",
    ]
    for name in sorted(formatted):
        summary_lines.append(f"- `{name}` -> `{formatted[name]}`")
    (outputs_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print("Vendored optional dependency imported successfully.", flush=True)
    for name in sorted(formatted):
        print(f"{name}: {formatted[name]}", flush=True)


if __name__ == "__main__":
    main()
