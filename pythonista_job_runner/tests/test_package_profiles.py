# Version: 0.6.13-tests-package-profiles.5
"""Tests for package profile discovery, build, and attach helpers."""

from __future__ import annotations

import zipfile
from pathlib import Path
from types import SimpleNamespace

from runner import package_envs
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


def test_setup_status_reports_missing_wheel_and_mode(tmp_path):
    """Setup status should explain the most important example-5 blockers."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    profile_dir = paths.public_profiles_dir / "demo_formatsize_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.txt").write_text("pjr_demo_formatsize==0.1.0\n", encoding="utf-8")
    (profile_dir / "manifest.json").write_text('{"display_name": "Demo formatsize"}\n', encoding="utf-8")

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="",
        dependency_mode="per_job",
        install_requirements=False,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )

    payload = package_profiles.setup_status(runner)

    assert payload["wheel_present"] is False
    assert payload["profile_present"] is True
    assert payload["ready_for_example_5"] is False
    assert payload["ready_state"] == "restart_required"
    assert payload["build_available"] is True
    assert payload["build_recommended"] is True
    assert payload["target_profile_status"] == "not_built"
    assert "package_profile_default: demo_formatsize_profile" in payload["config_snippet"]
    assert payload["restart_required"] is True
    assert any("Install requirements.txt automatically" in item for item in payload["blockers"])
    assert any("Dependency handling mode" in item for item in payload["blockers"])
    assert any("default package profile" in item for item in payload["blockers"])
    assert any("Build demo_formatsize_profile" in item for item in payload["next_steps"])



def test_setup_status_marks_build_failure_and_wheelhouse_blocker(tmp_path):
    """Setup status should surface profile build failure and wheelhouse config blockers."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    wheel_path = paths.public_wheel_uploads_dir / "pjr_demo_formatsize-0.1.0-py3-none-any.whl"
    wheel_path.write_bytes(b"wheel")

    profile_dir = paths.public_profiles_dir / "demo_formatsize_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.txt").write_text("pjr_demo_formatsize==0.1.0\n", encoding="utf-8")
    (profile_dir / "manifest.json").write_text('{"display_name": "Demo formatsize"}\n', encoding="utf-8")

    state_path = package_profiles._profile_state_path(paths, "demo_formatsize_profile")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        '{\n'
        '  "status": "error",\n'
        '  "last_error": "pip install failed",\n'
        '  "last_build_utc": "2026-03-11T17:00:00Z"\n'
        '}\n',
        encoding="utf-8",
    )

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_formatsize_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=False,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )

    payload = package_profiles.setup_status(runner)

    assert payload["ready_state"] == "build_failed"
    assert payload["restart_required"] is True
    assert payload["target_profile_last_error"] == "pip install failed"
    assert any("public wheelhouse support" in item for item in payload["blockers"])
    assert any("Rebuild demo_formatsize_profile" in item for item in payload["next_steps"])


def _write_profile_zip(
    path: Path,
    *,
    rooted: bool,
    profile_name: str = "demo_formatsize_profile",
    include_requirements: bool = True,
    traversal: bool = False,
) -> None:
    """Write one small package-profile archive for upload tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        prefix = f"{profile_name}/" if rooted else ""
        if traversal:
            zf.writestr("../escape.txt", "bad\n")
            return
        zf.writestr(f"{prefix}manifest.json", '{"profile_name": "demo_formatsize_profile", "display_name": "Demo formatsize"}\n')
        if include_requirements:
            zf.writestr(f"{prefix}requirements.txt", "pjr_demo_formatsize==0.1.0\n")
        zf.writestr(f"{prefix}README.md", "demo\n")


def test_upload_profile_zip_accepts_rooted_archive(tmp_path):
    """Profile archive upload should accept one rooted archive and publish the profile."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_formatsize_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        max_upload_mb=10,
    )

    upload_path = tmp_path / "profile.zip"
    _write_profile_zip(upload_path, rooted=True)

    result = package_profiles.upload_profile_zip(runner, upload_path, filename="profile.zip", overwrite=False)

    assert result["status"] == "ok"
    assert result["profile_name"] == "demo_formatsize_profile"
    assert (paths.public_profiles_dir / "demo_formatsize_profile" / "manifest.json").is_file()
    assert result["archive"]["archive_layout"] == "rooted"


def test_upload_profile_zip_accepts_flat_archive(tmp_path):
    """Profile archive upload should also accept a flat archive with manifest and requirements."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_formatsize_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        max_upload_mb=10,
    )

    upload_path = tmp_path / "profile.zip"
    _write_profile_zip(upload_path, rooted=False)

    result = package_profiles.upload_profile_zip(runner, upload_path, filename="profile.zip", overwrite=False)

    assert result["status"] == "ok"
    assert result["archive"]["archive_layout"] == "flat"
    assert (paths.public_profiles_dir / "demo_formatsize_profile" / "requirements.txt").is_file()


def test_upload_profile_zip_rejects_traversal_and_missing_requirements(tmp_path):
    """Profile archive upload should reject unsafe paths and incomplete profiles."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_formatsize_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        max_upload_mb=10,
    )

    traversal_zip = tmp_path / "traversal.zip"
    _write_profile_zip(traversal_zip, rooted=False, traversal=True)
    traversal_result = package_profiles.upload_profile_zip(runner, traversal_zip, filename="traversal.zip", overwrite=False)
    assert traversal_result["status"] == "error"
    assert traversal_result["error"] == "suspicious_archive_path"

    missing_req_zip = tmp_path / "missing_req.zip"
    _write_profile_zip(missing_req_zip, rooted=False, include_requirements=False)
    missing_req_result = package_profiles.upload_profile_zip(runner, missing_req_zip, filename="missing_req.zip", overwrite=False)
    assert missing_req_result["status"] == "error"
    assert missing_req_result["error"] == "profile_requirements_missing"


def test_delete_uploaded_profile_removes_public_and_cached_build_paths(tmp_path):
    """Deleting one uploaded profile should also remove cached state and built venv paths."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    profile_dir = paths.public_profiles_dir / "demo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.lock").write_text("wheel==0.45.1\n", encoding="utf-8")
    (profile_dir / "manifest.json").write_text('{"display_name": "Demo profile"}\n', encoding="utf-8")

    runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        active_package_environment_keys=lambda: [],
    )

    summary = package_profiles.list_profiles(runner)["profiles"][0]
    environment_key = summary["environment_key"]
    _make_ready_venv(Path(summary["venv_path"]))
    exports_dir = Path(summary["exports_dir"])
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "diagnostics_bundle.zip").write_bytes(b"zip")
    diagnostics_dir = Path(summary["diagnostics_dir"])
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    (diagnostics_dir / "pip_install_stdout.txt").write_text("ok\n", encoding="utf-8")
    state_path = paths.profiles_manifests_dir / "demo_profile.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"status": "ready"}\n', encoding="utf-8")
    package_envs.write_venv_index(paths, {"version": 1, "items": [{"environment_key": environment_key}]})

    result = package_profiles.delete_uploaded_profile(runner, "demo_profile")

    assert result["status"] == "ok"
    assert result["removed_cached_venv"] is True
    assert not profile_dir.exists()
    assert not Path(summary["venv_path"]).exists()
    assert not exports_dir.exists()
    assert not diagnostics_dir.exists()
    assert not state_path.exists()
    assert package_profiles.list_profiles(runner)["profile_count"] == 0


def test_delete_uploaded_profile_rejects_active_environment(tmp_path):
    """Deleting one uploaded profile should fail while its reusable venv is active."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    profile_dir = paths.public_profiles_dir / "demo_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "requirements.lock").write_text("wheel==0.45.1\n", encoding="utf-8")
    (profile_dir / "manifest.json").write_text('{"display_name": "Demo profile"}\n', encoding="utf-8")

    base_runner = SimpleNamespace(
        package_store_paths=paths,
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
        dependency_mode="profile",
        install_requirements=True,
        package_allow_public_wheelhouse=True,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    env_key = package_profiles.list_profiles(base_runner)["profiles"][0]["environment_key"]
    runner = SimpleNamespace(**base_runner.__dict__, active_package_environment_keys=lambda: [env_key])

    result = package_profiles.delete_uploaded_profile(runner, "demo_profile")

    assert result["status"] == "error"
    assert result["error"] == "profile_in_use"
    assert profile_dir.exists()
