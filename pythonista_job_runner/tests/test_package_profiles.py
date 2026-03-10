# Version: 0.6.13-tests-package-profiles.1
"""Tests for package profile discovery, build, and attach helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from runner import package_profiles
from runner import package_store



def _make_ready_venv(path: Path) -> None:
    """Create the minimal on-disk structure for one ready Linux venv."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    (path / "bin" / "python").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")



def test_list_profiles_discovers_public_profiles(tmp_path):
    """Public profile folders should appear in the profile inventory."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    profile_dir = paths.public_profiles_dir / "demo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.lock").write_text("wheel==0.45.1\n", encoding="utf-8")
    (profile_dir / "manifest.json").write_text(
        '{"display_name": "Demo profile"}\n',
        encoding="utf-8",
    )

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
        dependency_mode="profile",
        package_require_hashes=False,
        package_offline_prefer_local=True,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )

    payload = package_profiles.list_profiles(runner)

    assert payload["default_profile"] == "demo_profile"
    assert payload["profile_count"] == 1
    assert payload["profiles"][0]["name"] == "demo_profile"
    assert payload["profiles"][0]["display_name"] == "Demo profile"
    assert payload["profiles"][0]["requirements_kind"] == "requirements.lock"



def test_build_profile_creates_ready_venv_and_exports_bundle(tmp_path, monkeypatch):
    """Building one profile should create a ready venv and exported diagnostics."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    profile_dir = paths.public_profiles_dir / "demo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.lock").write_text("wheel==0.45.1\n", encoding="utf-8")

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
        dependency_mode="profile",
        package_require_hashes=False,
        package_offline_prefer_local=True,
        package_allow_public_wheelhouse=True,
        package_cache_enabled=True,
        pip_timeout_seconds=30,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        venv_max_count=20,
    )

    def _fake_run(cmd, **kwargs):
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("ok\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if cmd[:3] == ["python3", "-m", "venv"]:
            _make_ready_venv(Path(cmd[-1]))
        elif cmd[-2:] == ["pip", "inspect"] or cmd[-3:] == ["-m", "pip", "inspect"]:
            stdout_path.write_text('{"version":"1"}\n', encoding="utf-8")
        return {
            "cmd": list(cmd),
            "rc": 0,
            "exec_error": None,
            "duration_seconds": 0.01,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }

    monkeypatch.setattr(package_profiles, "_run_command", _fake_run)

    result = package_profiles.build_profile(runner, "demo_profile", rebuild=False)

    assert result["status"] == "ready"
    assert Path(result["venv_path"]).exists()
    assert Path(result["effective_requirements_path"]).exists()
    assert Path(result["diagnostics_bundle_path"]).exists()



def test_attach_profile_for_job_uses_built_profile(tmp_path, monkeypatch):
    """Attaching a profile to one job should set package metadata and env."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
    )
    venv_path = paths.venvs_root / "abc123"
    _make_ready_venv(venv_path)

    monkeypatch.setattr(
        package_profiles,
        "build_profile",
        lambda _runner, _profile_name, rebuild=False: {
            "status": "ready",
            "display_name": "Demo profile",
            "environment_key": "abc123",
            "venv_path": str(venv_path),
            "effective_requirements_path": "/config/exports/package_profiles/demo_profile/effective_requirements.lock",
            "diagnostics_bundle_path": "/config/exports/package_profiles/demo_profile/diagnostics_bundle.zip",
            "action": "reused",
            "install_duration_seconds": 0,
        },
    )

    env = {"PATH": "/usr/bin"}
    package_meta = {"status": "skipped"}

    err = package_profiles.attach_profile_for_job(runner, env, package_meta)

    assert err is None
    assert package_meta["profile_name"] == "demo_profile"
    assert package_meta["install_source"] == "profile_venv"
    assert env["VIRTUAL_ENV"] == str(venv_path)
