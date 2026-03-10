# Version: 0.6.13-tests-package-envs.1
"""Tests for reusable virtual environment helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from runner import package_envs
from runner import package_store



def _make_ready_venv(path: Path) -> None:
    """Create the minimal on-disk structure for a ready Linux venv."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    (path / "bin" / "python").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")



def test_environment_key_changes_with_requirements_content(tmp_path):
    """Reusable venv keys should change when requirements content changes."""
    req = tmp_path / "requirements.txt"
    req.write_text("wheel==0.45.0\n", encoding="utf-8")
    runner = SimpleNamespace(
        dependency_mode="per_job",
        package_require_hashes=False,
        package_offline_prefer_local=True,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )

    first = package_envs.build_environment_key(runner, req)
    second = package_envs.build_environment_key(runner, req)
    req.write_text("wheel==0.45.1\n", encoding="utf-8")
    third = package_envs.build_environment_key(runner, req)

    assert first == second
    assert first != third



def test_upsert_touch_and_prune_venv_index(tmp_path):
    """Venv index helpers should track usage and prune least-recently-used entries."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    req = tmp_path / "requirements.txt"
    req.write_text("wheel\n", encoding="utf-8")
    venv_a = package_envs.venv_dir(paths, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    venv_b = package_envs.venv_dir(paths, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    _make_ready_venv(venv_a)
    _make_ready_venv(venv_b)

    record_a = package_envs.upsert_venv_record(
        paths,
        environment_key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        venv_path=venv_a,
        requirements_path=req,
        install_source="remote_index",
    )
    record_b = package_envs.upsert_venv_record(
        paths,
        environment_key="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        venv_path=venv_b,
        requirements_path=req,
        install_source="remote_index",
    )
    assert record_a["key"].startswith("a")
    assert record_b["key"].startswith("b")

    package_envs.touch_last_used(paths, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    pruned = package_envs.prune_venvs(paths, max_count=1, keep_keys=["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"])

    assert pruned["removed"] == 1
    assert "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in pruned["removed_keys"]
    assert package_envs.get_venv_record(paths, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa") is None
    assert package_envs.get_venv_record(paths, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb") is not None



def test_attach_venv_to_env_prepends_path(tmp_path):
    """Attaching a venv should prepend its bin directory to PATH."""
    venv_path = tmp_path / "venv"
    _make_ready_venv(venv_path)
    env = {"PATH": "/usr/bin"}

    package_envs.attach_venv_to_env(env, venv_path)

    assert env["PATH"].startswith(str(venv_path / "bin"))
    assert env["VIRTUAL_ENV"] == str(venv_path)
