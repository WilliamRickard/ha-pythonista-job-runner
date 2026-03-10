# Version: 0.6.13-examples-tools.2
"""Build `job.zip` files for every example from the contents of `job_src/`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

ZIP_TIMESTAMP = (2026, 3, 10, 0, 0, 0)
IGNORED_PART_NAMES = {"__pycache__", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def load_manifest(examples_root: Path) -> dict:
    """Load and return the examples manifest JSON document."""
    manifest_path = examples_root / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def iter_example_entries(manifest: dict, only_ids: set[str] | None = None) -> list[dict]:
    """Return the manifest entries filtered by optional example IDs."""
    entries = list(manifest.get("examples", []))
    if not only_ids:
        return entries
    return [entry for entry in entries if str(entry.get("id")) in only_ids]


def should_include_in_job_zip(path: Path, job_src_dir: Path) -> bool:
    """Return True when a file should be included in a built example job zip."""
    relative = path.relative_to(job_src_dir)
    if any(part in IGNORED_PART_NAMES for part in relative.parts):
        return False
    if path.name in IGNORED_PART_NAMES:
        return False
    if path.suffix.lower() in IGNORED_SUFFIXES:
        return False
    return path.is_file()


def build_zip_from_job_src(job_src_dir: Path, destination_zip: Path) -> None:
    """Create a deterministic zip containing the contents of one `job_src/` folder."""
    destination_zip.parent.mkdir(parents=True, exist_ok=True)
    files = [path for path in sorted(job_src_dir.rglob("*")) if should_include_in_job_zip(path, job_src_dir)]
    with zipfile.ZipFile(destination_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            arcname = path.relative_to(job_src_dir).as_posix()
            info = zipfile.ZipInfo(filename=arcname, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> None:
    """Parse arguments, build zips, and print a short summary."""
    parser = argparse.ArgumentParser(description="Build example job zip files.")
    parser.add_argument("--examples-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--only", nargs="*", default=[])
    args = parser.parse_args()

    examples_root = Path(args.examples_root).resolve()
    manifest = load_manifest(examples_root)
    entries = iter_example_entries(manifest, set(args.only))
    built_paths: list[Path] = []

    for entry in entries:
        job_src = examples_root / str(entry["job_src"])
        destination = examples_root / str(entry["job_zip"])
        build_zip_from_job_src(job_src, destination)
        built_paths.append(destination)
        print(f"Built {destination.relative_to(examples_root)} from {job_src.relative_to(examples_root)}")

    print(f"Built {len(built_paths)} example zip file(s).")


if __name__ == "__main__":
    main()
