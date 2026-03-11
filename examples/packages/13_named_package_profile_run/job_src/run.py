# Version: 0.6.13-examples.1
"""Profile mode example that expects a named package profile to be attached."""

from __future__ import annotations

import json
from pathlib import Path

import pjr_demo_formatsize  # type: ignore

PROFILE_NAME = "demo_formatsize_profile"
SAMPLE_SIZES = {
    "buyout_summary.csv": 1024,
    "liability_curve.json": 2816,
    "trustee_pack.zip": 5200000,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON with indentation and stable key ordering."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "
", encoding="utf-8")


def main() -> None:
    """Write deterministic outputs for the profile-mode workflow."""
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    formatted = {name: pjr_demo_formatsize.naturalsize(size) for name, size in SAMPLE_SIZES.items()}
    _write_json(
        outputs_dir / "profile_run_status.json",
        {
            "dependency_mode_hint": "profile",
            "example_id": "13_named_package_profile_run",
            "expected_install_source": "profile_venv",
            "files": formatted,
            "profile_name": PROFILE_NAME,
        },
    )
    summary_lines = [
        "# Named package profile run example",
        "",
        f"This job expects the add-on to attach the `{PROFILE_NAME}` package profile.",
        "It does not ship its own `requirements.txt`.",
        "",
        "Check `package/package_diagnostics.json` for `profile_name` and `install_source: profile_venv`.",
        "",
        "Generated sizes:",
    ]
    for name in sorted(formatted):
        summary_lines.append(f"- `{name}` -> `{formatted[name]}`")
    (outputs_dir / "summary.md").write_text("
".join(summary_lines) + "
", encoding="utf-8")
    print("Named package profile run example completed.", flush=True)
    for name in sorted(formatted):
        print(f"{name}: {formatted[name]}", flush=True)


if __name__ == "__main__":
    main()
