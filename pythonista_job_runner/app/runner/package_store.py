# Version: 0.6.13-package-store.3
"""Persistent package storage helpers, wheelhouse sync, and status scans."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PUBLIC_CONFIG_ROOT = Path("/config")
_WHEEL_BASENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]*\.whl$")


@dataclass(frozen=True)
class PackageStorePaths:
    """Resolved filesystem paths for persistent package storage."""

    private_root: Path
    cache_root: Path
    pip_cache_dir: Path
    http_cache_dir: Path
    wheelhouse_root: Path
    wheelhouse_downloaded_dir: Path
    wheelhouse_built_dir: Path
    wheelhouse_imported_dir: Path
    venvs_root: Path
    profiles_root: Path
    profiles_manifests_dir: Path
    profiles_locks_dir: Path
    jobs_package_reports_dir: Path
    state_root: Path
    package_index_path: Path
    venv_index_path: Path
    eviction_log_path: Path
    storage_stats_path: Path
    public_root: Path
    public_profiles_dir: Path
    public_wheel_uploads_dir: Path
    public_diagnostics_dir: Path
    public_exports_dir: Path


def sanitise_public_subdir(name: str, default: str = "wheel_uploads") -> str:
    """Return a safe single path component for the public wheel upload folder."""
    value = str(name or "").strip()
    if re.fullmatch(r"[A-Za-z0-9._-]+", value):
        return value
    return default


def build_package_store_paths(
    data_dir: Path,
    *,
    public_root: Path | None = None,
    public_wheelhouse_subdir: str = "wheel_uploads",
) -> PackageStorePaths:
    """Build the private and public package storage paths for the add-on."""
    resolved_public_root = public_root if public_root is not None else PUBLIC_CONFIG_ROOT
    safe_public_subdir = sanitise_public_subdir(public_wheelhouse_subdir)

    private_root = Path(data_dir) / "pythonista_job_runner"
    cache_root = private_root / "cache"
    wheelhouse_root = private_root / "wheelhouse"
    profiles_root = private_root / "profiles"
    state_root = private_root / "state"

    return PackageStorePaths(
        private_root=private_root,
        cache_root=cache_root,
        pip_cache_dir=cache_root / "pip",
        http_cache_dir=cache_root / "http",
        wheelhouse_root=wheelhouse_root,
        wheelhouse_downloaded_dir=wheelhouse_root / "downloaded",
        wheelhouse_built_dir=wheelhouse_root / "built",
        wheelhouse_imported_dir=wheelhouse_root / "imported",
        venvs_root=private_root / "venvs",
        profiles_root=profiles_root,
        profiles_manifests_dir=profiles_root / "manifests",
        profiles_locks_dir=profiles_root / "locks",
        jobs_package_reports_dir=private_root / "jobs" / "package_reports",
        state_root=state_root,
        package_index_path=state_root / "package_index.json",
        venv_index_path=state_root / "venv_index.json",
        eviction_log_path=state_root / "eviction_log.json",
        storage_stats_path=state_root / "storage_stats.json",
        public_root=Path(resolved_public_root),
        public_profiles_dir=Path(resolved_public_root) / "package_profiles",
        public_wheel_uploads_dir=Path(resolved_public_root) / safe_public_subdir,
        public_diagnostics_dir=Path(resolved_public_root) / "diagnostics",
        public_exports_dir=Path(resolved_public_root) / "exports",
    )


def _ensure_directory(path: Path) -> None:
    """Create a directory tree when it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON deterministically."""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_json_if_missing(path: Path, payload: dict[str, Any]) -> None:
    """Initialise a JSON file only when it is missing."""
    if path.exists():
        return
    _write_json(path, payload)


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    """Read JSON from disk with a fallback payload on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback)


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def is_valid_wheel_filename(name: str) -> bool:
    """Return whether a filename is a safe wheel basename."""
    return bool(_WHEEL_BASENAME_RE.fullmatch(str(name or "").strip()))


def public_wheel_import_max_bytes(cache_max_mb: int | None) -> int:
    """Return the maximum accepted public wheel size for one upload."""
    cache_mb = int(cache_max_mb or 0)
    if cache_mb <= 0:
        return 128 * 1024 * 1024
    return max(16 * 1024 * 1024, min(cache_mb * 1024 * 1024 // 2, 512 * 1024 * 1024))


def _iter_regular_wheels(directory: Path) -> list[Path]:
    """Return sorted regular wheel files directly under one directory."""
    if not directory.exists() or not directory.is_dir() or directory.is_symlink():
        return []
    items: list[Path] = []
    for path in sorted(directory.iterdir(), key=lambda p: p.name):
        try:
            if not path.is_file() or path.is_symlink():
                continue
        except OSError:
            continue
        if not is_valid_wheel_filename(path.name):
            continue
        items.append(path)
    return items


def _state_payloads(paths: PackageStorePaths, public_available: bool) -> dict[Path, dict[str, Any]]:
    """Return the initial JSON payloads for package state index files."""
    public_root = str(paths.public_root) if public_available else None
    return {
        paths.package_index_path: {"version": 1, "items": [], "summary": {}},
        paths.venv_index_path: {"version": 1, "items": []},
        paths.eviction_log_path: {"version": 1, "events": []},
        paths.storage_stats_path: {
            "version": 1,
            "generated_utc": None,
            "private_root": str(paths.private_root),
            "public_root": public_root,
            "private_bytes": 0,
            "public_bytes": 0,
            "venv_count": 0,
            "wheel_count": 0,
            "wheel_bytes": 0,
        },
    }


def bootstrap_package_store(paths: PackageStorePaths) -> dict[str, Any]:
    """Create the package storage directory tree and state index files."""
    private_dirs = [
        paths.private_root,
        paths.cache_root,
        paths.pip_cache_dir,
        paths.http_cache_dir,
        paths.wheelhouse_root,
        paths.wheelhouse_downloaded_dir,
        paths.wheelhouse_built_dir,
        paths.wheelhouse_imported_dir,
        paths.venvs_root,
        paths.profiles_root,
        paths.profiles_manifests_dir,
        paths.profiles_locks_dir,
        paths.jobs_package_reports_dir,
        paths.state_root,
    ]
    for directory in private_dirs:
        _ensure_directory(directory)

    public_available = paths.public_root.exists() and paths.public_root.is_dir()
    public_dirs = [
        paths.public_profiles_dir,
        paths.public_wheel_uploads_dir,
        paths.public_diagnostics_dir,
        paths.public_exports_dir,
    ]
    if public_available:
        for directory in public_dirs:
            _ensure_directory(directory)

    for path, payload in _state_payloads(paths, public_available).items():
        _write_json_if_missing(path, payload)

    summary = refresh_package_index(paths)
    return {
        "private_root": str(paths.private_root),
        "public_root": str(paths.public_root),
        "public_available": public_available,
        "state_files": {
            "package_index": str(paths.package_index_path),
            "venv_index": str(paths.venv_index_path),
            "eviction_log": str(paths.eviction_log_path),
            "storage_stats": str(paths.storage_stats_path),
        },
        "wheelhouse": summary,
    }


def scan_wheelhouse(paths: PackageStorePaths) -> dict[str, Any]:
    """Return current wheelhouse counts and entries across internal directories."""
    buckets = {
        "downloaded": paths.wheelhouse_downloaded_dir,
        "built": paths.wheelhouse_built_dir,
        "imported": paths.wheelhouse_imported_dir,
    }
    items: list[dict[str, Any]] = []
    counts = {"downloaded": 0, "built": 0, "imported": 0}
    total_bytes = 0
    for source, directory in buckets.items():
        for wheel_path in _iter_regular_wheels(directory):
            try:
                stat = wheel_path.stat()
            except OSError:
                continue
            counts[source] += 1
            total_bytes += int(stat.st_size)
            items.append(
                {
                    "source": source,
                    "filename": wheel_path.name,
                    "path": str(wheel_path),
                    "size": int(stat.st_size),
                    "sha256": _sha256_file(wheel_path),
                }
            )
    return {
        "private_root": str(paths.private_root),
        "wheelhouse_root": str(paths.wheelhouse_root),
        "downloaded_files": counts["downloaded"],
        "built_files": counts["built"],
        "imported_files": counts["imported"],
        "total_files": counts["downloaded"] + counts["built"] + counts["imported"],
        "total_bytes": total_bytes,
        "items": items,
    }


def refresh_package_index(paths: PackageStorePaths) -> dict[str, Any]:
    """Rewrite package index and storage stats from the current wheelhouse state."""
    summary = scan_wheelhouse(paths)
    existing_stats = _read_json(paths.storage_stats_path, {"version": 1})
    storage_stats = {
        "version": 1,
        "generated_utc": None,
        "private_root": str(paths.private_root),
        "public_root": str(paths.public_root) if paths.public_root.exists() else None,
        "private_bytes": int(existing_stats.get("private_bytes", 0) or 0),
        "public_bytes": int(existing_stats.get("public_bytes", 0) or 0),
        "venv_count": int(existing_stats.get("venv_count", 0) or 0),
        "wheel_count": int(summary["total_files"]),
        "wheel_bytes": int(summary["total_bytes"]),
    }
    _write_json(paths.package_index_path, {"version": 1, "items": summary["items"], "summary": summary})
    _write_json(paths.storage_stats_path, storage_stats)
    return summary


def _is_path_under(root: Path, candidate: Path) -> bool:
    """Return whether one path resolves inside the supplied root."""
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _validate_wheel_archive(path: Path) -> tuple[bool, str]:
    """Return whether a wheel archive looks structurally safe and valid."""
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
    except Exception:
        return (False, "malformed_wheel")
    if not names:
        return (False, "malformed_wheel")
    has_wheel = False
    has_metadata = False
    has_record = False
    for name in names:
        if name.startswith("/") or ".." in Path(name).parts:
            return (False, "suspicious_archive_path")
        lowered = name.lower()
        if lowered.endswith(".dist-info/wheel"):
            has_wheel = True
        elif lowered.endswith(".dist-info/metadata"):
            has_metadata = True
        elif lowered.endswith(".dist-info/record"):
            has_record = True
    if not (has_wheel and has_metadata and has_record):
        return (False, "malformed_wheel")
    return (True, "ok")


def sync_public_wheel_uploads(paths: PackageStorePaths, *, max_import_bytes: int | None = None) -> dict[str, Any]:
    """Copy validated public wheel uploads into the internal imported wheelhouse."""
    result: dict[str, Any] = {
        "status": "skipped",
        "public_dir": str(paths.public_wheel_uploads_dir),
        "imported_dir": str(paths.wheelhouse_imported_dir),
        "copied": 0,
        "updated": 0,
        "unchanged": 0,
        "skipped_invalid": 0,
        "skipped_invalid_name": 0,
        "skipped_invalid_path": 0,
        "skipped_malformed": 0,
        "skipped_oversized": 0,
        "max_import_bytes": int(max_import_bytes or 0),
        "items": [],
    }
    public_dir = paths.public_wheel_uploads_dir
    if not public_dir.exists() or not public_dir.is_dir() or public_dir.is_symlink():
        result["status"] = "public_dir_unavailable"
        return result

    for src in sorted(public_dir.iterdir(), key=lambda p: p.name):
        try:
            if not src.is_file() or src.is_symlink():
                result["skipped_invalid"] += 1
                continue
        except OSError:
            result["skipped_invalid"] += 1
            continue
        if not is_valid_wheel_filename(src.name):
            result["skipped_invalid"] += 1
            result["skipped_invalid_name"] += 1
            continue
        if not _is_path_under(public_dir, src):
            result["skipped_invalid"] += 1
            result["skipped_invalid_path"] += 1
            continue
        try:
            size_bytes = int(src.stat().st_size)
        except OSError:
            result["skipped_invalid"] += 1
            continue
        if max_import_bytes is not None and size_bytes > int(max_import_bytes):
            result["skipped_invalid"] += 1
            result["skipped_oversized"] += 1
            result["items"].append({"filename": src.name, "source_path": str(src), "size_bytes": size_bytes, "action": "skipped_oversized"})
            continue
        archive_ok, archive_reason = _validate_wheel_archive(src)
        if not archive_ok:
            result["skipped_invalid"] += 1
            if archive_reason == "suspicious_archive_path":
                result["skipped_invalid_path"] += 1
            else:
                result["skipped_malformed"] += 1
            result["items"].append({"filename": src.name, "source_path": str(src), "size_bytes": size_bytes, "action": archive_reason})
            continue

        dest = paths.wheelhouse_imported_dir / src.name
        src_sha = _sha256_file(src)
        action = "copied"
        if dest.exists() and dest.is_file() and not dest.is_symlink():
            try:
                if _sha256_file(dest) == src_sha:
                    action = "unchanged"
                else:
                    action = "updated"
            except Exception:
                action = "updated"
        if action in {"copied", "updated"}:
            shutil.copy2(src, dest)
        result[action] += 1
        result["items"].append(
            {
                "filename": src.name,
                "source_path": str(src),
                "dest_path": str(dest),
                "sha256": src_sha,
                "size_bytes": size_bytes,
                "action": action,
            }
        )

    result["status"] = "ok"
    result["summary"] = refresh_package_index(paths)
    return result


def find_links_dirs(paths: PackageStorePaths, work_dir: Path | None = None) -> list[str]:
    """Return deterministic pip --find-links directories for wheel reuse."""
    dirs: list[Path] = [
        paths.wheelhouse_imported_dir,
        paths.wheelhouse_downloaded_dir,
        paths.wheelhouse_built_dir,
    ]
    if work_dir is not None:
        dirs.extend([Path(work_dir) / "vendor", Path(work_dir) / "wheels"])

    out: list[str] = []
    seen: set[str] = set()
    for directory in dirs:
        if not directory.exists() or not directory.is_dir() or directory.is_symlink():
            continue
        if not _iter_regular_wheels(directory):
            continue
        value = str(directory)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
