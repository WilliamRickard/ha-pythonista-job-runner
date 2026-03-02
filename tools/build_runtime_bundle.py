# Version: 0.1.0

"""Build a runtime bundle zip and manifest.

Creates:
- dist/ghkit_runtime_<tag>.zip
- dist/manifest_<tag>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from datetime import datetime, timezone


INCLUDE_DIRS = ["ghkit", "ghkit_pythonista", "pythonista_wrappers"]


def _sha256_bytes(data: bytes) -> str:
    """Compute sha256 hex digest for bytes."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def build_bundle(repo_root: Path, tag: str, dist_dir: Path) -> tuple[Path, Path]:
    """Build runtime zip and manifest."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / f"ghkit_runtime_{tag}.zip"
    manifest_path = dist_dir / f"manifest_{tag}.json"
    files: list[dict[str, object]] = []

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for d in INCLUDE_DIRS:
            base = repo_root / d
            if not base.exists():
                continue
            for p in sorted(base.rglob("*")):
                if p.is_dir():
                    continue
                rel = p.relative_to(repo_root).as_posix()
                data = p.read_bytes()
                zf.writestr(rel, data)
                files.append({"path": rel, "sha256": _sha256_bytes(data), "bytes": len(data)})

    manifest = {
        "version": tag.lstrip("v"),
        "built_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "min_python": "3.10",
        "files": files,
        "notes": "Scaffold bundle",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return zip_path, manifest_path


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser()
    p.add_argument("--tag", required=True, help="Tag name, e.g. v0.1.0")
    p.add_argument("--repo-root", default=".", help="Repo root path")
    p.add_argument("--dist-dir", default="dist", help="Output directory")
    return p.parse_args()


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    dist_dir = (repo_root / args.dist_dir).resolve()
    zip_path, manifest_path = build_bundle(repo_root, args.tag, dist_dir)
    print(f"Wrote: {zip_path}")
    print(f"Wrote: {manifest_path}")


if __name__ == "__main__":
    main()
