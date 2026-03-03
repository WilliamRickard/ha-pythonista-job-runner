"""Regression tests for runner_core fixes.

These tests cover edge cases that previously led to timeouts or unsafe behaviour.
"""

from __future__ import annotations

import io
import os
import shutil
import threading
import time
import zipfile

import pytest

import runner_core


def _current_username() -> str:
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:
        return "jobrunner"


def _make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.skipif(shutil.which("python3") is None, reason="python3 not available for subprocess execution")
def test_job_large_stdout_no_newline_completes(temp_data_dir):
    runner = runner_core.Runner(
        {
            "token": "t",
            "job_user": _current_username(),
            "max_concurrent_jobs": 1,
        }
    )

    # 2 MiB of output without a newline: old readline()-based pumping could block
    # until the job timeout triggered.
    payload = (
        "import sys\n"
        "sys.stdout.write('x' * (2 * 1024 * 1024))\n"
        "sys.stdout.flush()\n"
    )
    zip_bytes = _make_zip({"run.py": payload})

    job = runner.new_job(zip_bytes, {"X-Runner-TIMEOUT": "5"}, "127.0.0.1")

    t0 = time.time()
    while time.time() - t0 < 10:
        j = runner.get(job.job_id)
        assert j is not None
        if j.phase in ("done", "error"):
            break
        time.sleep(0.1)

    j = runner.get(job.job_id)
    assert j is not None
    assert j.phase == "done"
    assert j.exit_code == 0
    assert j.state == "done"


def test_queue_max_jobs_is_enforced_under_concurrency(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = runner_core.Runner(
        {
            "token": "t",
            "job_user": _current_username(),
            "queue_max_jobs": 1,
            "max_concurrent_jobs": 1,
        }
    )

    # Prevent background execution so jobs remain active and deterministic.
    monkeypatch.setattr(runner, "_run_job", lambda *_args, **_kwargs: None)

    barrier = threading.Barrier(2)
    results: list[str] = []
    errors: list[str] = []

    def _submit():
        try:
            barrier.wait(timeout=5)
            j = runner.new_job(minimal_job_zip, {}, "127.0.0.1")
            results.append(j.job_id)
        except Exception as e:
            errors.append(type(e).__name__ + ":" + str(e))

    t1 = threading.Thread(target=_submit)
    t2 = threading.Thread(target=_submit)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    # Exactly one job should be accepted.
    assert len(results) == 1
    assert any("queue_full" in e for e in errors)


def test_job_user_missing_is_rejected_when_running_as_root(temp_data_dir, minimal_job_zip, monkeypatch):
    # Simulate root environment.
    monkeypatch.setattr(runner_core.os, "geteuid", lambda: 0)

    runner = runner_core.Runner({"token": "t", "job_user": "definitely_missing_user_xyz"})
    with pytest.raises(RuntimeError, match="job_user_missing"):
        runner.new_job(minimal_job_zip, {}, "127.0.0.1")
