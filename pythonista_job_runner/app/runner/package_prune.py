# Version: 0.6.13-package-prune.2
"""Package storage usage accounting, pruning, and purge helpers."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from runner import package_envs
from utils import utc_now


@dataclass(frozen=True)
class _Candidate:
    """One removable package-store item."""

    category: str
    path: Path
    size_bytes: int
    sort_key: tuple[str, str]
    environment_key: str = ""


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    """Read JSON with a deterministic fallback payload."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON deterministically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _has_full_store(paths: object) -> bool:
    """Return whether package store paths include the full persistent layout."""
    required = (
        "private_root",
        "public_root",
        "pip_cache_dir",
        "http_cache_dir",
        "wheelhouse_downloaded_dir",
        "wheelhouse_built_dir",
        "wheelhouse_imported_dir",
        "jobs_package_reports_dir",
        "profiles_root",
        "venvs_root",
        "state_root",
        "package_index_path",
        "storage_stats_path",
        "eviction_log_path",
        "venv_index_path",
    )
    return all(hasattr(paths, name) for name in required)


def _dir_size_bytes(root: Path, *, max_files: int = 500_000) -> int:
    """Return best-effort size of regular files under one directory tree."""
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return 0
    total = 0
    files_seen = 0
    for current_root, dirs, files in os.walk(str(root)):
        dirs.sort()
        files.sort()
        for name in files:
            path = Path(current_root) / name
            try:
                if not path.is_file() or path.is_symlink():
                    continue
                total += int(path.stat().st_size)
            except OSError:
                continue
            files_seen += 1
            if files_seen >= max_files:
                return total
    return total


def _path_mtime_key(path: Path) -> str:
    """Return a stable mtime key for least-recently-used ordering."""
    try:
        return f"{float(path.stat().st_mtime):020.6f}"
    except OSError:
        return "00000000000000000000"


def _current_storage_payload(paths: object) -> dict[str, Any]:
    """Return detailed current storage usage payload."""
    private_root = Path(getattr(paths, "private_root"))
    public_root = Path(getattr(paths, "public_root"))
    breakdown = {
        "cache_pip_bytes": _dir_size_bytes(Path(getattr(paths, "pip_cache_dir"))),
        "cache_http_bytes": _dir_size_bytes(Path(getattr(paths, "http_cache_dir"))),
        "wheelhouse_downloaded_bytes": _dir_size_bytes(Path(getattr(paths, "wheelhouse_downloaded_dir"))),
        "wheelhouse_built_bytes": _dir_size_bytes(Path(getattr(paths, "wheelhouse_built_dir"))),
        "wheelhouse_imported_bytes": _dir_size_bytes(Path(getattr(paths, "wheelhouse_imported_dir"))),
        "jobs_package_reports_bytes": _dir_size_bytes(Path(getattr(paths, "jobs_package_reports_dir"))),
        "profiles_private_bytes": _dir_size_bytes(Path(getattr(paths, "profiles_root"))),
        "venv_bytes": _dir_size_bytes(Path(getattr(paths, "venvs_root"))),
        "state_bytes": _dir_size_bytes(Path(getattr(paths, "state_root"))),
    }
    private_bytes = sum(int(v) for v in breakdown.values())
    public_bytes = _dir_size_bytes(public_root) if public_root.exists() and public_root.is_dir() and not public_root.is_symlink() else 0

    package_index = _read_json(Path(getattr(paths, "package_index_path")), {"summary": {}})
    venv_index = package_envs.read_venv_index(paths)
    payload = {
        "version": 1,
        "generated_utc": utc_now(),
        "private_root": str(private_root),
        "public_root": str(public_root) if public_root.exists() else None,
        "private_bytes": private_bytes,
        "public_bytes": public_bytes,
        "private_mebibytes": round(private_bytes / (1024 * 1024), 3),
        "public_mebibytes": round(public_bytes / (1024 * 1024), 3),
        "breakdown": breakdown,
        "wheel_count": int(((package_index.get("summary") or {}).get("total_files", 0)) or 0),
        "wheel_bytes": int(((package_index.get("summary") or {}).get("total_bytes", 0)) or 0),
        "venv_count": len([item for item in (venv_index.get("items") or []) if isinstance(item, dict)]),
        "last_prune_utc": None,
        "last_prune_status": None,
        "last_prune_reason": None,
        "last_prune_removed": 0,
        "last_purge_utc": None,
        "last_purge_status": None,
        "last_purge_removed": 0,
    }
    existing = _read_json(Path(getattr(paths, "storage_stats_path")), {"version": 1})
    for key in (
        "last_prune_utc",
        "last_prune_status",
        "last_prune_reason",
        "last_prune_removed",
        "last_prune_bytes_freed",
        "last_purge_utc",
        "last_purge_status",
        "last_purge_removed",
        "last_purge_bytes_freed",
        "last_action_utc",
        "last_action_kind",
        "last_action_reason",
    ):
        if key in existing:
            payload[key] = existing.get(key)
    return payload


def refresh_storage_stats(paths: object) -> dict[str, Any]:
    """Recompute and persist package storage usage statistics."""
    payload = _current_storage_payload(paths)
    _write_json(Path(getattr(paths, "storage_stats_path")), payload)
    return payload


def _append_eviction_event(paths: object, event: dict[str, Any]) -> None:
    """Append one prune or purge event to the eviction log."""
    eviction_path = Path(getattr(paths, "eviction_log_path"))
    payload = _read_json(eviction_path, {"version": 1, "events": []})
    events = payload.get("events")
    if not isinstance(events, list):
        events = []
    events.append(dict(event))
    payload["version"] = 1
    payload["events"] = events[-200:]
    _write_json(eviction_path, payload)


def _remove_file(path: Path) -> None:
    """Remove one file best-effort."""
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _remove_empty_parents(path: Path, stop_at: Path) -> None:
    """Remove empty parents between one path and the chosen root."""
    current = path.parent
    stop = stop_at.resolve()
    while True:
        try:
            if current.resolve() == stop:
                return
        except Exception:
            return
        try:
            current.rmdir()
        except Exception:
            return
        current = current.parent


def _remove_venv_records(paths: object, removed_keys: set[str]) -> None:
    """Remove deleted venvs from the persisted venv index."""
    payload = package_envs.read_venv_index(paths)
    kept = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "") in removed_keys:
            continue
        kept.append(item)
    payload["version"] = 1
    payload["items"] = kept
    package_envs.write_venv_index(paths, payload)


def _runner_active_keys(runner: object, extra_keep_keys: Iterable[str] = ()) -> set[str]:
    """Return active reusable-environment keys that must not be pruned."""
    keys = {str(value) for value in extra_keep_keys if str(value or "").strip()}
    getter = getattr(runner, "active_package_environment_keys", None)
    if callable(getter):
        try:
            keys.update(str(value) for value in getter() if str(value or "").strip())
        except Exception:
            pass
    return keys


def _prune_candidates(paths: object, protected_keys: set[str]) -> list[_Candidate]:
    """Return removable package-store candidates in oldest-first order."""
    candidates: list[_Candidate] = []

    venv_payload = package_envs.read_venv_index(paths)
    for item in venv_payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        if not key or key in protected_keys:
            continue
        path_value = str(item.get("path") or "").strip()
        if not path_value:
            continue
        path = Path(path_value)
        if not package_envs.is_ready_venv(path):
            continue
        size_bytes = int(item.get("size_bytes", 0) or 0)
        if size_bytes <= 0:
            size_bytes = _dir_size_bytes(path)
        sort_key = (str(item.get("last_used_utc") or ""), key)
        candidates.append(_Candidate("venv", path, size_bytes, sort_key, environment_key=key))

    for root_attr, category in (
        ("jobs_package_reports_dir", "package_report"),
        ("wheelhouse_downloaded_dir", "wheel_downloaded"),
        ("wheelhouse_built_dir", "wheel_built"),
        ("wheelhouse_imported_dir", "wheel_imported"),
        ("pip_cache_dir", "pip_cache"),
        ("http_cache_dir", "http_cache"),
    ):
        root = Path(getattr(paths, root_attr))
        if not root.exists() or not root.is_dir() or root.is_symlink():
            continue
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            try:
                if child.is_symlink():
                    continue
                if child.is_dir():
                    size_bytes = _dir_size_bytes(child)
                elif child.is_file():
                    size_bytes = int(child.stat().st_size)
                else:
                    continue
            except OSError:
                continue
            candidates.append(_Candidate(category, child, size_bytes, (_path_mtime_key(child), child.name)))

    candidates.sort(key=lambda item: item.sort_key)
    return candidates


def package_cache_summary(runner: object) -> dict[str, Any]:
    """Return current package storage state with limits and protection info."""
    paths = getattr(runner, "package_store_paths", None)
    if paths is None:
        return {"status": "unavailable"}
    if not _has_full_store(paths):
        return {"status": "skipped_no_store", "cache_enabled": bool(getattr(runner, "package_cache_enabled", True))}
    payload = refresh_storage_stats(paths)
    max_bytes = max(0, int(getattr(runner, "package_cache_max_mb", 0) or 0)) * 1024 * 1024
    payload.update(
        {
            "status": "ok",
            "cache_enabled": bool(getattr(runner, "package_cache_enabled", True)),
            "package_cache_max_mb": int(getattr(runner, "package_cache_max_mb", 0) or 0),
            "package_cache_max_bytes": max_bytes,
            "over_limit": bool(max_bytes > 0 and int(payload.get("private_bytes", 0) or 0) > max_bytes),
            "active_environment_keys": sorted(_runner_active_keys(runner)),
            "eviction_log_path": str(getattr(paths, "eviction_log_path")),
            "storage_stats_path": str(getattr(paths, "storage_stats_path")),
        }
    )
    return payload


def prune_package_store(runner: object, *, reason: str = "manual", actor: dict[str, Any] | None = None, keep_keys: Iterable[str] = ()) -> dict[str, Any]:
    """Prune package storage down to the configured soft limit using LRU order."""
    del actor  # actor is recorded by Runner audit hooks, not inside the helper.
    paths = getattr(runner, "package_store_paths", None)
    if paths is None:
        return {"status": "unavailable", "reason": reason}
    if not _has_full_store(paths):
        return {"status": "skipped_no_store", "reason": reason, "removed": 0, "removed_bytes": 0}

    before = package_cache_summary(runner)
    max_bytes = int(before.get("package_cache_max_bytes", 0) or 0)
    if max_bytes <= 0:
        return {"status": "disabled", "reason": reason, "removed": 0, "removed_bytes": 0, "before_bytes": int(before.get("private_bytes", 0) or 0), "after_bytes": int(before.get("private_bytes", 0) or 0)}

    protected_keys = _runner_active_keys(runner, keep_keys)
    removed: list[dict[str, Any]] = []
    removed_venv_keys: set[str] = set()
    current_bytes = int(before.get("private_bytes", 0) or 0)
    if current_bytes > max_bytes:
        for candidate in _prune_candidates(paths, protected_keys):
            if current_bytes <= max_bytes:
                break
            if candidate.category == "venv":
                package_envs.remove_tree(candidate.path)
                removed_venv_keys.add(candidate.environment_key)
            elif candidate.path.is_dir() and not candidate.path.is_symlink():
                shutil.rmtree(candidate.path, ignore_errors=True)
            else:
                _remove_file(candidate.path)
                root_attr = {
                    "package_report": "jobs_package_reports_dir",
                    "wheel_downloaded": "wheelhouse_downloaded_dir",
                    "wheel_built": "wheelhouse_built_dir",
                    "wheel_imported": "wheelhouse_imported_dir",
                    "pip_cache": "pip_cache_dir",
                    "http_cache": "http_cache_dir",
                }.get(candidate.category)
                if root_attr:
                    _remove_empty_parents(candidate.path, Path(getattr(paths, root_attr)))
            current_bytes = max(0, current_bytes - int(candidate.size_bytes))
            removed.append(
                {
                    "category": candidate.category,
                    "path": str(candidate.path),
                    "size_bytes": int(candidate.size_bytes),
                    "environment_key": candidate.environment_key or None,
                }
            )

    if removed_venv_keys:
        _remove_venv_records(paths, removed_venv_keys)
    after = refresh_storage_stats(paths)
    event = {
        "kind": "prune",
        "created_utc": utc_now(),
        "reason": reason,
        "protected_environment_keys": sorted(protected_keys),
        "removed": len(removed),
        "removed_bytes": sum(int(item.get("size_bytes", 0) or 0) for item in removed),
        "removed_items": removed,
        "before_bytes": int(before.get("private_bytes", 0) or 0),
        "after_bytes": int(after.get("private_bytes", 0) or 0),
        "max_bytes": max_bytes,
        "status": "ok" if int(after.get("private_bytes", 0) or 0) <= max_bytes else "partial",
    }
    _append_eviction_event(paths, event)
    after.update(
        {
            "last_prune_utc": event["created_utc"],
            "last_prune_status": event["status"],
            "last_prune_reason": reason,
            "last_prune_removed": event["removed"],
            "last_prune_bytes_freed": event["removed_bytes"],
            "last_action_utc": event["created_utc"],
            "last_action_kind": "prune",
            "last_action_reason": reason,
        }
    )
    _write_json(Path(getattr(paths, "storage_stats_path")), after)
    event["storage"] = after
    return event


def purge_package_store(
    runner: object,
    *,
    reason: str = "manual",
    include_venvs: bool = False,
    include_imported_wheels: bool = False,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explicitly purge package caches and optional reusable environments."""
    del actor
    paths = getattr(runner, "package_store_paths", None)
    if paths is None:
        return {"status": "unavailable", "reason": reason}
    if not _has_full_store(paths):
        return {"status": "skipped_no_store", "reason": reason, "removed": 0, "removed_bytes": 0}

    before = package_cache_summary(runner)
    protected_keys = _runner_active_keys(runner)
    removed: list[dict[str, Any]] = []
    removed_venv_keys: set[str] = set()

    def _remove_root_contents(root: Path, category: str) -> None:
        if not root.exists() or not root.is_dir() or root.is_symlink():
            return
        for child in sorted(root.iterdir(), key=lambda p: p.name):
            try:
                if child.is_symlink():
                    continue
                if child.is_dir():
                    size_bytes = _dir_size_bytes(child)
                    shutil.rmtree(child, ignore_errors=True)
                elif child.is_file():
                    size_bytes = int(child.stat().st_size)
                    _remove_file(child)
                else:
                    continue
            except OSError:
                continue
            removed.append({"category": category, "path": str(child), "size_bytes": int(size_bytes), "environment_key": None})

    _remove_root_contents(Path(getattr(paths, "pip_cache_dir")), "pip_cache")
    _remove_root_contents(Path(getattr(paths, "http_cache_dir")), "http_cache")
    _remove_root_contents(Path(getattr(paths, "wheelhouse_downloaded_dir")), "wheel_downloaded")
    _remove_root_contents(Path(getattr(paths, "wheelhouse_built_dir")), "wheel_built")
    if include_imported_wheels:
        _remove_root_contents(Path(getattr(paths, "wheelhouse_imported_dir")), "wheel_imported")
    _remove_root_contents(Path(getattr(paths, "jobs_package_reports_dir")), "package_report")

    if include_venvs:
        payload = package_envs.read_venv_index(paths)
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "")
            if not key or key in protected_keys:
                continue
            venv_path = Path(str(item.get("path") or ""))
            size_bytes = int(item.get("size_bytes", 0) or 0)
            if size_bytes <= 0:
                size_bytes = _dir_size_bytes(venv_path)
            package_envs.remove_tree(venv_path)
            removed.append({"category": "venv", "path": str(venv_path), "size_bytes": int(size_bytes), "environment_key": key})
            removed_venv_keys.add(key)
        if removed_venv_keys:
            _remove_venv_records(paths, removed_venv_keys)

    after = refresh_storage_stats(paths)
    event = {
        "kind": "purge",
        "created_utc": utc_now(),
        "reason": reason,
        "include_venvs": bool(include_venvs),
        "include_imported_wheels": bool(include_imported_wheels),
        "protected_environment_keys": sorted(protected_keys),
        "removed": len(removed),
        "removed_bytes": sum(int(item.get("size_bytes", 0) or 0) for item in removed),
        "removed_items": removed,
        "before_bytes": int(before.get("private_bytes", 0) or 0),
        "after_bytes": int(after.get("private_bytes", 0) or 0),
        "status": "ok",
    }
    _append_eviction_event(paths, event)
    after.update(
        {
            "last_purge_utc": event["created_utc"],
            "last_purge_status": event["status"],
            "last_purge_removed": event["removed"],
            "last_purge_bytes_freed": event["removed_bytes"],
            "last_action_utc": event["created_utc"],
            "last_action_kind": "purge",
            "last_action_reason": reason,
        }
    )
    _write_json(Path(getattr(paths, "storage_stats_path")), after)
    event["storage"] = after
    return event
