# Version: 0.6.13-tests-package-prune.1
"""Tests for package storage accounting, pruning, and purge helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from runner import package_envs
from runner import package_prune
from runner import package_store


def _make_ready_venv(path: Path, *, payload_bytes: int = 0) -> None:
    """Create a minimal ready venv with optional payload bytes."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    (path / "bin" / "python").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")
    if payload_bytes > 0:
        (path / "lib").mkdir(parents=True, exist_ok=True)
        (path / "lib" / "payload.bin").write_bytes(b"x" * payload_bytes)


def test_package_cache_summary_reports_usage_and_limit(tmp_path):
    """Package cache summary should include bytes and configured limit."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)
    (paths.pip_cache_dir / "cache.bin").write_bytes(b"x" * 1024)

    runner = SimpleNamespace(package_store_paths=paths, package_cache_max_mb=1, package_cache_enabled=True, active_package_environment_keys=lambda: [])
    summary = package_prune.package_cache_summary(runner)

    assert summary["status"] == "ok"
    assert summary["private_bytes"] >= 1024
    assert summary["package_cache_max_bytes"] == 1024 * 1024


def test_prune_package_store_keeps_active_venv_and_removes_older_cache(tmp_path):
    """Pruning should preserve active environments while removing older items."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    req = tmp_path / "requirements.txt"
    req.write_text("wheel\n", encoding="utf-8")
    old_venv = package_envs.venv_dir(paths, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    active_venv = package_envs.venv_dir(paths, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    _make_ready_venv(old_venv, payload_bytes=900000)
    _make_ready_venv(active_venv, payload_bytes=900000)
    package_envs.upsert_venv_record(paths, environment_key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", venv_path=old_venv, requirements_path=req, install_source="remote_index")
    package_envs.upsert_venv_record(paths, environment_key="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", venv_path=active_venv, requirements_path=req, install_source="remote_index")
    package_envs.touch_last_used(paths, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    (paths.pip_cache_dir / "cache.bin").write_bytes(b"z" * 900000)

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_cache_max_mb=1,
        package_cache_enabled=True,
        active_package_environment_keys=lambda: ["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
    )
    result = package_prune.prune_package_store(runner, reason="manual")

    assert "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" in result["protected_environment_keys"]
    assert active_venv.exists()
    assert result["removed"] >= 1


def test_purge_package_store_keeps_active_venv_but_clears_cache_dirs(tmp_path):
    """Purge should clear cache directories while keeping protected active venvs."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)
    (paths.pip_cache_dir / "cache.bin").write_bytes(b"x" * 512)
    (paths.wheelhouse_built_dir / "wheel.bin").write_bytes(b"x" * 512)

    req = tmp_path / "requirements.txt"
    req.write_text("wheel\n", encoding="utf-8")
    active_venv = package_envs.venv_dir(paths, "cccccccccccccccccccccccccccccccc")
    _make_ready_venv(active_venv, payload_bytes=512)
    package_envs.upsert_venv_record(paths, environment_key="cccccccccccccccccccccccccccccccc", venv_path=active_venv, requirements_path=req, install_source="remote_index")

    runner = SimpleNamespace(package_store_paths=paths, package_cache_max_mb=16, package_cache_enabled=True, active_package_environment_keys=lambda: ["cccccccccccccccccccccccccccccccc"])
    result = package_prune.purge_package_store(runner, include_venvs=True)

    assert result["status"] == "ok"
    assert active_venv.exists()
    assert not any(paths.pip_cache_dir.iterdir())
    assert not any(paths.wheelhouse_built_dir.iterdir())
