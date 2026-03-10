# Version: 0.6.13-examples-tools.3
"""Validate the structure of the examples suite without third-party dependencies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable
import zipfile

REQUIRED_TOP_LEVEL_KEYS = {
    "_version",
    "schema_version",
    "examples_version",
    "tracks",
    "examples",
}
REQUIRED_ENTRY_KEYS = {
    "id",
    "order",
    "track",
    "title",
    "status",
    "requires_toolchain",
    "folder",
    "readme",
    "job_src",
    "job_zip",
    "notes",
}
VALID_TRACKS = {"core", "toolchain"}
VALID_STATUSES = {"scaffold", "implemented", "validated"}


def zip_contains_root_run_py(zip_path: Path) -> bool:
    """Return True when a built example zip contains `run.py` at archive root."""
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = {name.rstrip("/") for name in archive.namelist()}
    return "run.py" in names


def load_manifest(examples_root: Path) -> dict:
    """Load the examples manifest from disk."""
    return json.loads((examples_root / "manifest.json").read_text(encoding="utf-8"))


def validate_manifest_shape(manifest: dict) -> list[str]:
    """Return manifest-level validation errors."""
    errors: list[str] = []
    missing = REQUIRED_TOP_LEVEL_KEYS.difference(manifest)
    if missing:
        errors.append(f"Manifest missing top-level keys: {sorted(missing)}")
    if not isinstance(manifest.get("examples", []), list):
        errors.append("Manifest key `examples` must be a list.")
    if not isinstance(manifest.get("tracks", []), list):
        errors.append("Manifest key `tracks` must be a list.")
    return errors


def _validate_expected_result(folder: Path, entry_id: str) -> list[str]:
    """Return validation errors for optional checked-in expected result artefacts."""
    errors: list[str] = []
    expected_manifest_path = folder / "expected_result_manifest.json"
    expected_result_dir = folder / "expected_result"
    expected_result_zip = folder / "expected_result.zip"

    if not expected_manifest_path.exists() and not expected_result_dir.exists() and not expected_result_zip.exists():
        return errors

    if not expected_manifest_path.is_file():
        errors.append(f"{entry_id}: missing expected_result_manifest.json")
        return errors
    if not expected_result_dir.is_dir():
        errors.append(f"{entry_id}: missing expected_result/ directory")
    if not expected_result_zip.is_file():
        errors.append(f"{entry_id}: missing expected_result.zip")

    try:
        manifest = json.loads(expected_manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{entry_id}: expected_result_manifest.json is invalid JSON: {exc}")
        return errors

    for item in manifest.get("files", []):
        rel_path = Path(str(item.get("path", "")))
        if not rel_path.as_posix():
            errors.append(f"{entry_id}: expected result manifest entry missing path")
            continue
        file_path = expected_result_dir / rel_path
        if not file_path.is_file():
            errors.append(f"{entry_id}: expected result file missing: {rel_path.as_posix()}")

    return errors


def validate_entry(entry: dict, examples_root: Path, seen_ids: set[str], require_built_zips: bool) -> list[str]:
    """Return validation errors for one example manifest entry."""
    errors: list[str] = []
    missing_keys = REQUIRED_ENTRY_KEYS.difference(entry)
    entry_id = str(entry.get("id", "<missing-id>"))
    if missing_keys:
        errors.append(f"{entry_id}: missing manifest keys {sorted(missing_keys)}")
        return errors

    if entry_id in seen_ids:
        errors.append(f"{entry_id}: duplicate example id")
    seen_ids.add(entry_id)

    track = str(entry["track"])
    status = str(entry["status"])
    if track not in VALID_TRACKS:
        errors.append(f"{entry_id}: invalid track `{track}`")
    if status not in VALID_STATUSES:
        errors.append(f"{entry_id}: invalid status `{status}`")

    folder = examples_root / str(entry["folder"])
    readme = examples_root / str(entry["readme"])
    job_src = examples_root / str(entry["job_src"])
    job_zip = examples_root / str(entry["job_zip"])
    run_py = job_src / "run.py"

    prefix = entry_id.split("_", 1)[0]
    if not prefix.isdigit():
        errors.append(f"{entry_id}: folder name must start with a numeric prefix")
    else:
        expected_order = int(prefix)
        if int(entry["order"]) != expected_order:
            errors.append(
                f"{entry_id}: manifest order {entry['order']} does not match folder prefix {expected_order}"
            )

    if not folder.is_dir():
        errors.append(f"{entry_id}: missing folder {folder.relative_to(examples_root)}")
    if not readme.is_file():
        errors.append(f"{entry_id}: missing README {readme.relative_to(examples_root)}")
    if not job_src.is_dir():
        errors.append(f"{entry_id}: missing job_src folder {job_src.relative_to(examples_root)}")
    if not run_py.is_file():
        errors.append(f"{entry_id}: missing job_src/run.py")
    if require_built_zips and not job_zip.is_file():
        errors.append(f"{entry_id}: missing built zip {job_zip.relative_to(examples_root)}")
    elif require_built_zips and not zip_contains_root_run_py(job_zip):
        errors.append(f"{entry_id}: built zip is missing run.py at archive root")

    errors.extend(_validate_expected_result(folder, entry_id))
    return errors


def validate_examples_root(examples_root: Path, *, require_built_zips: bool = True) -> list[str]:
    """Return all validation errors for the examples suite."""
    manifest = load_manifest(examples_root)
    errors = validate_manifest_shape(manifest)
    seen_ids: set[str] = set()
    for entry in manifest.get("examples", []):
        errors.extend(validate_entry(entry, examples_root, seen_ids, require_built_zips))
    return errors


def format_errors(errors: Iterable[str]) -> str:
    """Format validation errors as a readable multi-line block."""
    items = list(errors)
    if not items:
        return "Validation passed."
    return "Validation failed:\n- " + "\n- ".join(items)


def main() -> None:
    """Parse arguments, run validation, and print the result."""
    parser = argparse.ArgumentParser(description="Validate example folders and manifest entries.")
    parser.add_argument("--examples-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--skip-built-zips", action="store_true")
    args = parser.parse_args()

    examples_root = Path(args.examples_root).resolve()
    errors = validate_examples_root(examples_root, require_built_zips=not args.skip_built_zips)
    print(format_errors(errors))


if __name__ == "__main__":
    main()
