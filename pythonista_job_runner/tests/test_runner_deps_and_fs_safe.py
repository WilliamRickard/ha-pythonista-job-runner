# Version: 0.6.13-tests-deps-fs-safe.4
"""Focused tests for runner dependency install/process fallback/fs-safety helpers."""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import deps as deps_mod
from runner import package_envs as package_envs_mod
from runner import package_store as package_store_mod
from runner import fs_safe as fs_safe_mod
from runner import process as process_mod


class _DummyProc:
    def __init__(self, return_code: int = 0):
        self._return_code = return_code

    def wait(self, timeout: int | float | None = None) -> int:
        _ = timeout
        return self._return_code


def test_deps_non_root_missing_uid_gid_does_not_disable_install(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=120,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir)
    env: dict[str, str] = {}

    monkeypatch.setattr(deps_mod.subprocess, "Popen", lambda *args, **kwargs: _DummyProc(0))

    err = deps_mod.maybe_install_requirements(runner, job, env)

    assert err is None
    assert env.get("PYTHONPATH")


def test_deps_root_missing_uid_gid_is_disabled(tmp_path):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        _is_root=True,
        _job_uid=None,
        _job_gid=None,
    )
    job = SimpleNamespace(work_dir=work_dir)

    err = deps_mod.maybe_install_requirements(runner, job, {})
    assert err == "pip_install_disabled_no_job_user"


def test_kill_process_group_fallback_escalates_to_kill(monkeypatch):
    class _Proc:
        def __init__(self):
            self.pid = 123
            self.terminate_called = 0
            self.kill_called = 0
            self.poll_calls = 0

        def terminate(self):
            self.terminate_called += 1

        def poll(self):
            self.poll_calls += 1
            return None

        def kill(self):
            self.kill_called += 1

    proc = _Proc()
    monkeypatch.setattr(process_mod.os, "getpgid", lambda _pid: (_ for _ in ()).throw(ProcessLookupError("no pgid")))

    process_mod.kill_process_group(proc, soft_seconds=0)

    assert proc.terminate_called == 1
    assert proc.kill_called == 1


def test_safe_write_text_no_symlink_refuses_symlink(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("orig", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(target)

    fs_safe_mod.safe_write_text_no_symlink(link, "new")

    assert target.read_text(encoding="utf-8") == "orig"


def test_safe_zip_write_refuses_paths_outside_base_dir(tmp_path):
    base = tmp_path / "base"
    base.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        fs_safe_mod.safe_zip_write(zf, outside, "outside.txt", base)

    with zipfile.ZipFile(io.BytesIO(zbuf.getvalue()), "r") as zf:
        assert "outside.txt" not in zf.namelist()


def test_deps_timeout_returns_timeout_and_writes_redacted_debug(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="https://alice:p@ss@example.com/simple",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir)

    class _TimeoutProc:
        def wait(self, timeout=None):
            raise deps_mod.subprocess.TimeoutExpired(cmd="pip", timeout=timeout)

    monkeypatch.setattr(deps_mod.subprocess, "Popen", lambda *args, **kwargs: _TimeoutProc())
    monkeypatch.setattr(deps_mod, "kill_process_group", lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        deps_mod,
        "file_tail_text",
        lambda _path, _max: "index https://alice:p@ss@example.com/simple",
    )

    err = deps_mod.maybe_install_requirements(runner, job, {})

    assert err is not None
    assert err.startswith("pip_install_timeout:")
    assert "alice:***@example.com" in err
    assert "p@ss" not in err


def test_deps_nonzero_rc_returns_rc_error(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir)

    monkeypatch.setattr(deps_mod.subprocess, "Popen", lambda *args, **kwargs: _DummyProc(7))
    monkeypatch.setattr(deps_mod, "file_tail_text", lambda _path, _max: "pip failed")

    err = deps_mod.maybe_install_requirements(runner, job, {})

    assert err is not None
    assert err.startswith("pip_install_rc_7:")



def test_deps_sets_pip_cache_dir_and_report_paths(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    report_root = tmp_path / "reports"
    pip_cache_dir = tmp_path / "pip-cache"
    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="per_job",
        package_cache_enabled=True,
        package_store_paths=SimpleNamespace(jobs_package_reports_dir=report_root, pip_cache_dir=pip_cache_dir),
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir, job_id="job-1")
    env: dict[str, str] = {}
    calls: list[dict[str, object]] = []

    def _fake_run(cmd, **kwargs):
        calls.append({"cmd": list(cmd), **kwargs})
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        if "install" in cmd:
            stdout_path.write_text("Using cached wheel\n", encoding="utf-8")
        elif "inspect" in cmd:
            stdout_path.write_text('{"version":"1"}\n', encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return (0, None)

    monkeypatch.setattr(deps_mod, "_run_pip_command", _fake_run)

    err = deps_mod.maybe_install_requirements(runner, job, env)

    assert err is None
    assert env["PYTHONPATH"].endswith(str(work_dir / "_deps"))
    assert calls[0]["env"]["PIP_CACHE_DIR"] == str(pip_cache_dir)
    assert "--no-cache-dir" not in calls[0]["cmd"]
    assert "--report" in calls[0]["cmd"]
    assert job.package["cache_hit"] is True
    assert Path(job.package["install_report"]).name == "pip_install_report.json"
    assert Path(job.package["inspect_report"]).name == "pip_inspect_report.json"


def test_deps_writes_package_diagnostics_on_nonzero_rc(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    report_root = tmp_path / "reports"
    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="per_job",
        package_cache_enabled=False,
        package_store_paths=SimpleNamespace(jobs_package_reports_dir=report_root, pip_cache_dir=tmp_path / "pip-cache"),
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir, job_id="job-2")

    def _fake_run(cmd, **kwargs):
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("downloaded file\n", encoding="utf-8")
        stderr_path.write_text("pip failed\n", encoding="utf-8")
        return (9, None)

    monkeypatch.setattr(deps_mod, "_run_pip_command", _fake_run)

    err = deps_mod.maybe_install_requirements(runner, job, {})

    assert err is not None
    assert err.startswith("pip_install_rc_9:")
    diagnostics = json.loads((report_root / "job-2" / "package_diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["status"] == "error"
    assert diagnostics["reason"] == "pip_install_rc_9"



def _make_ready_venv(path: Path) -> None:
    """Create the minimal on-disk structure used by venv reuse tests."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    (path / "bin" / "python").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")


def test_deps_reuses_existing_venv_without_py_path_injection(tmp_path):
    """An existing keyed venv should be reused without installing into _deps."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store_mod.build_package_store_paths(tmp_path, public_root=public_root)
    package_store_mod.bootstrap_package_store(paths)

    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    req = work_dir / "requirements.txt"
    req.write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="per_job",
        package_cache_enabled=True,
        package_allow_public_wheelhouse=False,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        venv_reuse_enabled=True,
        venv_max_count=5,
        package_store_paths=paths,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir, job_id="job-venv-reuse")

    environment_key = package_envs_mod.build_environment_key(runner, req)
    venv_path = package_envs_mod.venv_dir(paths, environment_key)
    _make_ready_venv(venv_path)
    package_envs_mod.upsert_venv_record(
        paths,
        environment_key=environment_key,
        venv_path=venv_path,
        requirements_path=req,
        install_source="remote_index",
    )

    env = {"PATH": "/usr/bin"}
    err = deps_mod.maybe_install_requirements(runner, job, env)

    assert err is None
    assert env["PATH"].startswith(str(venv_path / "bin"))
    assert env["VIRTUAL_ENV"] == str(venv_path)
    assert "PYTHONPATH" not in env
    assert job.package["install_source"] == "reused_venv"
    assert job.package["venv_reused"] is True


def test_deps_venv_create_failure_falls_back_to_per_job_install(tmp_path, monkeypatch):
    """A venv bootstrap failure should fall back to the older per-job _deps flow."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store_mod.build_package_store_paths(tmp_path, public_root=public_root)
    package_store_mod.bootstrap_package_store(paths)

    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "requirements.txt").write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="per_job",
        package_cache_enabled=True,
        package_allow_public_wheelhouse=False,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        venv_reuse_enabled=True,
        venv_max_count=5,
        package_store_paths=paths,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )
    job = SimpleNamespace(work_dir=work_dir, job_id="job-venv-fallback")

    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if cmd[:3] == ["python3", "-m", "venv"]:
            return (1, None)
        if cmd[:3] == ["python3", "-m", "pip"] and "install" in cmd:
            return (0, None)
        if cmd[:3] == ["python3", "-m", "pip"] and "inspect" in cmd:
            stdout_path.write_text('{"version":"1"}\n', encoding="utf-8")
            return (0, None)
        return (0, None)

    monkeypatch.setattr(deps_mod, "_run_pip_command", _fake_run)

    env = {"PATH": "/usr/bin"}
    err = deps_mod.maybe_install_requirements(runner, job, env)

    assert err is None
    assert env["PYTHONPATH"].endswith(str(work_dir / "_deps"))
    assert job.package["venv_action"] == "fallback_per_job"
    assert job.package["install_source"] in {"remote_index", "remote_with_find_links"}


def test_deps_creates_and_then_reuses_keyed_venv(tmp_path, monkeypatch):
    """The first run should create a keyed venv and the second should reuse it."""
    public_root = tmp_path / "public"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store_mod.build_package_store_paths(tmp_path, public_root=public_root)
    package_store_mod.bootstrap_package_store(paths)

    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    req = work_dir / "requirements.txt"
    req.write_text("wheel\n", encoding="utf-8")

    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="per_job",
        package_cache_enabled=True,
        package_allow_public_wheelhouse=False,
        package_offline_prefer_local=True,
        package_require_hashes=False,
        venv_reuse_enabled=True,
        venv_max_count=5,
        package_store_paths=paths,
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
    )

    def _fake_run(cmd, **kwargs):
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if cmd[:3] == ["python3", "-m", "venv"]:
            staging_path = Path(cmd[-1])
            _make_ready_venv(staging_path)
            return (0, None)
        if len(cmd) >= 4 and cmd[1:4] == ["-m", "pip", "install"]:
            return (0, None)
        if len(cmd) >= 4 and cmd[1:4] == ["-m", "pip", "inspect"]:
            stdout_path.write_text('{"version":"1"}\n', encoding="utf-8")
            return (0, None)
        return (0, None)

    monkeypatch.setattr(deps_mod, "_run_pip_command", _fake_run)

    first_job = SimpleNamespace(work_dir=work_dir, job_id="job-venv-create-1")
    first_env = {"PATH": "/usr/bin"}
    first_err = deps_mod.maybe_install_requirements(runner, first_job, first_env)

    environment_key = package_envs_mod.build_environment_key(runner, req)
    venv_path = package_envs_mod.venv_dir(paths, environment_key)
    assert first_err is None
    assert venv_path.is_dir()
    assert first_job.package["venv_action"] == "created"
    assert first_env["VIRTUAL_ENV"] == str(venv_path)

    second_job = SimpleNamespace(work_dir=work_dir, job_id="job-venv-create-2")
    second_env = {"PATH": "/usr/bin"}
    second_err = deps_mod.maybe_install_requirements(runner, second_job, second_env)

    assert second_err is None
    assert second_job.package["venv_action"] == "reused"
    assert second_job.package["venv_reused"] is True
    assert second_env["VIRTUAL_ENV"] == str(venv_path)


def test_profile_mode_attaches_default_profile_without_job_requirements(tmp_path, monkeypatch):
    """Profile mode should attach the default profile even when the job zip has no requirements.txt."""
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    runner = SimpleNamespace(
        install_requirements=True,
        dependency_mode="profile",
        package_cache_enabled=True,
        package_store_paths=SimpleNamespace(jobs_package_reports_dir=tmp_path / "reports"),
        package_profiles_enabled=True,
        package_profile_default="demo_profile",
        _is_root=False,
        _job_uid=None,
        _job_gid=None,
        package_allow_public_wheelhouse=False,
        pip_timeout_seconds=10,
        pip_index_url="",
        pip_extra_index_url="",
        pip_trusted_hosts=[],
        venv_reuse_enabled=True,
        venv_max_count=20,
    )
    job = SimpleNamespace(work_dir=work_dir, job_id="job-profile")
    env: dict[str, str] = {}

    def _fake_attach_profile(_runner, env_obj, package_meta):
        env_obj["VIRTUAL_ENV"] = "/data/pythonista_job_runner/venvs/demo"
        package_meta["status"] = "ok"
        package_meta["profile_name"] = "demo_profile"
        package_meta["profile_status"] = "ready"
        return None

    monkeypatch.setattr(deps_mod.package_profiles, "attach_profile_for_job", _fake_attach_profile)

    err = deps_mod.maybe_install_requirements(runner, job, env)

    assert err is None
    assert env["VIRTUAL_ENV"].endswith("/demo")
    assert job.package["profile_name"] == "demo_profile"
    assert job.package["profile_status"] == "ready"
