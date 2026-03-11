# Version: 0.6.13-package-envs.2
"""Reusable virtual environment helpers for package dependency execution."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable

from utils import utc_now


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    """Read one JSON file with a deterministic fallback payload."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback)



def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON file deterministically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def _iter_existing_items(index_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the venv index items list in a safe normalised form."""
    items = index_payload.get("items")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            out.append(dict(item))
    return out



def _dir_size_bytes(path: Path) -> int:
    """Return the total size of regular files under one directory tree."""
    total = 0
    if not path.exists() or not path.is_dir() or path.is_symlink():
        return 0
    for root, dirs, files in os.walk(str(path)):
        dirs.sort()
        files.sort()
        for name in files:
            item = Path(root) / name
            try:
                if not item.is_file() or item.is_symlink():
                    continue
                total += int(item.stat().st_size)
            except OSError:
                continue
    return total



def requirements_sha256(req: Path) -> str:
    """Return the SHA-256 digest for one requirements file."""
    return hashlib.sha256(req.read_bytes()).hexdigest()



def build_environment_key_from_payload(payload: dict[str, Any]) -> str:
    """Return the deterministic reusable-environment key for one normalised payload."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return digest[:32]



def build_environment_key(runner: object, req: Path) -> str:
    """Return the deterministic reusable-environment key for one dependency set."""
    payload = {
        "requirements_sha256": requirements_sha256(req),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "machine": platform.machine(),
        "platform": sys.platform,
        "dependency_mode": str(getattr(runner, "dependency_mode", "per_job") or "per_job"),
        "require_hashes": bool(getattr(runner, "package_require_hashes", False)),
        "offline_prefer_local": bool(getattr(runner, "package_offline_prefer_local", True)),
        "pip_index_url": str(getattr(runner, "pip_index_url", "") or ""),
        "pip_extra_index_url": str(getattr(runner, "pip_extra_index_url", "") or ""),
        "pip_trusted_hosts": list(getattr(runner, "pip_trusted_hosts", []) or []),
    }
    return build_environment_key_from_payload(payload)



def venv_dir(paths: object, environment_key: str) -> Path:
    """Return the final venv directory for one environment key."""
    return Path(getattr(paths, "venvs_root")) / str(environment_key)



def staging_venv_dir(paths: object, environment_key: str) -> Path:
    """Return the temporary staging venv directory for one environment key."""
    return Path(getattr(paths, "venvs_root")) / f".{environment_key}.building"



def venv_bin_dir(venv_path: Path) -> Path:
    """Return the bin directory for one venv."""
    return Path(venv_path) / "bin"



def venv_python_path(venv_path: Path) -> Path:
    """Return the Python executable path for one venv."""
    return venv_bin_dir(venv_path) / "python"



def venv_site_packages_path(venv_path: Path) -> Path:
    """Return the expected site-packages path for one Linux add-on venv."""
    py_minor = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return Path(venv_path) / "lib" / py_minor / "site-packages"



def is_ready_venv(venv_path: Path) -> bool:
    """Return whether a venv path looks usable."""
    cfg = Path(venv_path) / "pyvenv.cfg"
    py = venv_python_path(venv_path)
    return bool(cfg.is_file() and py.is_file() and not cfg.is_symlink() and not py.is_symlink())



def prepare_staging_dir(staging_path: Path) -> None:
    """Reset the staging directory before creating a fresh venv build."""
    if staging_path.exists():
        shutil.rmtree(staging_path, ignore_errors=True)
    staging_path.parent.mkdir(parents=True, exist_ok=True)



def remove_tree(path: Path) -> None:
    """Remove one directory tree best-effort."""
    shutil.rmtree(path, ignore_errors=True)



def attach_venv_to_env(env: Dict[str, str], venv_path: Path) -> None:
    """Mutate one process environment so child commands use the supplied venv."""
    current_path = str(env.get("PATH") or "")
    env["PATH"] = str(venv_bin_dir(venv_path)) + (os.pathsep + current_path if current_path else "")
    env["VIRTUAL_ENV"] = str(venv_path)



def read_venv_index(paths: object) -> dict[str, Any]:
    """Return the current venv index payload."""
    venv_index_path = Path(getattr(paths, "venv_index_path"))
    return _read_json(venv_index_path, {"version": 1, "items": []})



def write_venv_index(paths: object, payload: dict[str, Any]) -> None:
    """Persist the venv index payload."""
    venv_index_path = Path(getattr(paths, "venv_index_path"))
    _write_json(venv_index_path, payload)



def get_venv_record(paths: object, environment_key: str) -> dict[str, Any] | None:
    """Return the stored index record for one environment key."""
    items = _iter_existing_items(read_venv_index(paths))
    for item in items:
        if str(item.get("key") or "") == str(environment_key):
            return item
    return None



def _storage_stats_payload(paths: object, venv_items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Return the updated storage stats payload for current venv metadata."""
    storage_stats_path = Path(getattr(paths, "storage_stats_path"))
    existing = _read_json(storage_stats_path, {"version": 1})
    items = list(venv_items)
    venv_count = 0
    venv_bytes = 0
    for item in items:
        path_value = str(item.get("path") or "").strip()
        if not path_value:
            continue
        venv_count += 1
        size_value = item.get("size_bytes")
        if isinstance(size_value, int):
            venv_bytes += size_value
        else:
            venv_bytes += _dir_size_bytes(Path(path_value))
    payload = dict(existing)
    payload.update(
        {
            "version": 1,
            "generated_utc": utc_now(),
            "private_root": str(getattr(paths, "private_root")),
            "public_root": str(getattr(paths, "public_root")) if Path(getattr(paths, "public_root")).exists() else None,
            "venv_count": venv_count,
            "venv_bytes": venv_bytes,
        }
    )
    return payload



def _write_storage_stats(paths: object, items: Iterable[dict[str, Any]]) -> None:
    """Persist storage statistics for the current venv index items."""
    storage_stats_path = Path(getattr(paths, "storage_stats_path"))
    _write_json(storage_stats_path, _storage_stats_payload(paths, items))



def upsert_venv_record(
    paths: object,
    *,
    environment_key: str,
    venv_path: Path,
    requirements_path: Path,
    install_source: str,
    status: str = "ready",
) -> dict[str, Any]:
    """Insert or update one reusable-venv index record."""
    now = utc_now()
    req_hash = requirements_sha256(requirements_path)
    size_bytes = _dir_size_bytes(venv_path)
    payload = read_venv_index(paths)
    items = _iter_existing_items(payload)
    kept: list[dict[str, Any]] = []
    created_utc = now
    for item in items:
        if str(item.get("key") or "") == str(environment_key):
            created_utc = str(item.get("created_utc") or now)
            continue
        kept.append(item)
    record = {
        "key": str(environment_key),
        "status": str(status),
        "path": str(venv_path),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "machine": platform.machine(),
        "requirements_sha256": req_hash,
        "install_source": str(install_source or "unknown"),
        "size_bytes": size_bytes,
        "created_utc": created_utc,
        "last_used_utc": now,
    }
    kept.append(record)
    payload["version"] = 1
    payload["items"] = sorted(kept, key=lambda item: str(item.get("key") or ""))
    write_venv_index(paths, payload)
    _write_storage_stats(paths, payload["items"])
    return record



def touch_last_used(paths: object, environment_key: str) -> dict[str, Any] | None:
    """Update the last-used timestamp for one reusable environment."""
    payload = read_venv_index(paths)
    items = _iter_existing_items(payload)
    now = utc_now()
    updated: dict[str, Any] | None = None
    out: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("key") or "") == str(environment_key):
            item = dict(item)
            item["last_used_utc"] = now
            size_value = item.get("size_bytes")
            if not isinstance(size_value, int):
                item["size_bytes"] = _dir_size_bytes(Path(str(item.get("path") or "")))
            updated = item
        out.append(item)
    payload["version"] = 1
    payload["items"] = sorted(out, key=lambda item: str(item.get("key") or ""))
    write_venv_index(paths, payload)
    _write_storage_stats(paths, payload["items"])
    return updated



def prune_venvs(paths: object, *, max_count: int, keep_keys: Iterable[str] = ()) -> dict[str, Any]:
    """Prune least-recently-used ready venvs down to the configured cap."""
    keep = {str(value) for value in keep_keys}
    payload = read_venv_index(paths)
    items = _iter_existing_items(payload)
    if int(max_count) <= 0:
        _write_storage_stats(paths, items)
        return {"status": "disabled", "removed": 0, "kept": len(items), "max_count": int(max_count)}

    candidates = [
        item
        for item in items
        if str(item.get("status") or "") == "ready"
        and str(item.get("key") or "") not in keep
        and is_ready_venv(Path(str(item.get("path") or "")))
    ]
    ready_count = len(candidates) + sum(1 for item in items if str(item.get("key") or "") in keep and str(item.get("status") or "") == "ready")
    removed: list[dict[str, Any]] = []
    if ready_count > int(max_count):
        candidates.sort(key=lambda item: (str(item.get("last_used_utc") or ""), str(item.get("key") or "")))
        to_remove = ready_count - int(max_count)
        for item in candidates[:to_remove]:
            path_value = str(item.get("path") or "").strip()
            if path_value:
                remove_tree(Path(path_value))
            removed.append(item)

    removed_keys = {str(item.get("key") or "") for item in removed}
    kept_items = [item for item in items if str(item.get("key") or "") not in removed_keys]
    payload["version"] = 1
    payload["items"] = sorted(kept_items, key=lambda item: str(item.get("key") or ""))
    write_venv_index(paths, payload)
    _write_storage_stats(paths, payload["items"])
    return {
        "status": "ok",
        "removed": len(removed),
        "removed_keys": sorted(removed_keys),
        "kept": len(kept_items),
        "max_count": int(max_count),
    }
