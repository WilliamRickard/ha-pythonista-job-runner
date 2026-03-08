"""Focused tests for runner dependency install/process fallback/fs-safety helpers."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from runner import deps as deps_mod
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
