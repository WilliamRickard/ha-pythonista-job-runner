"""Tests for runner_core.Runner that avoid executing real jobs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import runner_core


@pytest.fixture
def basic_opts():
    return {
        "token": "test_token",
        "bind_host": "0.0.0.0",
        "bind_port": 8787,
        "job_user": "root" if hasattr(os, "getuid") else "jobrunner",
    }


def test_runner_initialisation_defaults(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)

    assert runner.token == "test_token"
    assert runner.bind_host == "0.0.0.0"
    assert runner.bind_port == 8787
    assert runner.timeout_seconds == 3600
    assert runner.max_upload_mb == 50
    assert runner.default_cpu == 25
    assert runner.max_cpu == 50
    assert runner.default_mem == 4096
    assert runner.max_mem == 4096
    assert runner.max_threads == 1
    assert runner.max_concurrent_jobs == 1
    assert runner.queue_max_jobs == 10


def test_runner_initialisation_custom_options(temp_data_dir):
    runner = runner_core.Runner(
        {
            "token": "custom_token",
            "bind_port": 9090,
            "timeout_seconds": 7200,
            "max_upload_mb": 100,
            "default_cpu_percent": 50,
            "max_cpu_percent": 100,
            "max_concurrent_jobs": 5,
            "queue_max_jobs": 20,
            "notify_on_completion": False,
        }
    )

    assert runner.token == "custom_token"
    assert runner.bind_port == 9090
    assert runner.timeout_seconds == 7200
    assert runner.max_upload_mb == 100
    assert runner.default_cpu == 50
    assert runner.max_cpu == 100
    assert runner.max_concurrent_jobs == 5
    assert runner.queue_max_jobs == 20
    assert runner.notify_on_completion is False


def test_runner_invalid_port_falls_back(temp_data_dir, basic_opts):
    basic_opts = dict(basic_opts)
    basic_opts["bind_port"] = 99999

    runner = runner_core.Runner(basic_opts)
    assert runner.bind_port == 8787


def test_stats_dict_empty(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)
    stats = runner.stats_dict()

    assert stats["runner_version"] == runner_core.ADDON_VERSION
    assert stats["jobs_total"] == 0
    assert stats["jobs_running"] == 0
    assert stats["jobs_done"] == 0
    assert stats["jobs_error"] == 0
    assert stats["jobs_queued"] == 0


def test_list_jobs_and_get(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)
    assert runner.list_jobs() == []
    assert runner.get("missing") is None


def test_build_job_env_filters_supervisor_token(temp_data_dir, basic_opts, monkeypatch):
    monkeypatch.setenv("CUSTOM_VAR", "custom_value")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "should_not_leak")

    runner = runner_core.Runner({"token": "t", "allow_env": ["CUSTOM_VAR", "SUPERVISOR_TOKEN"]})
    env = runner._build_job_env(threads=4)

    assert env.get("CUSTOM_VAR") == "custom_value"
    assert "SUPERVISOR_TOKEN" not in env
    assert env["OMP_NUM_THREADS"] == "4"


def test_new_job_queue_full_is_stable(temp_data_dir, basic_opts, minimal_job_zip, monkeypatch):
    basic_opts = dict(basic_opts)
    basic_opts["queue_max_jobs"] = 1

    runner = runner_core.Runner(basic_opts)

    # Prevent background execution so the first job remains active.
    monkeypatch.setattr(runner, "_run_job", lambda *_args, **_kwargs: None)

    _ = runner.new_job(minimal_job_zip, {}, "127.0.0.1")

    with pytest.raises(RuntimeError, match="queue_full"):
        runner.new_job(minimal_job_zip, {}, "127.0.0.1")


def test_new_job_missing_run_py(temp_data_dir, basic_opts, monkeypatch):
    runner = runner_core.Runner(basic_opts)

    monkeypatch.setattr(runner, "_run_job", lambda *_args, **_kwargs: None)

    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("other.txt", "x")

    with pytest.raises(RuntimeError, match="zip_missing_run_py"):
        runner.new_job(buf.getvalue(), {}, "127.0.0.1")


def test_delete_and_cancel_nonexistent(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)
    assert runner.delete("missing") is False
    assert runner.cancel("missing") is False


def test_purge_dry_run_keeps_jobs(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)

    job = runner_core.Job(job_id="test123", state="done")
    runner._jobs["test123"] = job
    runner._job_order.append("test123")

    res = runner.purge(states=["done"], older_than_hours=0, dry_run=True)
    assert res["ok"] is True
    assert res["dry_run"] is True
    assert "test123" in res["deleted"]
    assert runner.get("test123") is not None


def test_purge_filters_by_state(temp_data_dir, basic_opts):
    runner = runner_core.Runner(basic_opts)

    runner._jobs["done1"] = runner_core.Job(job_id="done1", state="done")
    runner._jobs["error1"] = runner_core.Job(job_id="error1", state="error")
    runner._jobs["running1"] = runner_core.Job(job_id="running1", state="running")
    runner._job_order = ["done1", "error1", "running1"]

    res = runner.purge(states=["done"], older_than_hours=0, dry_run=True)
    assert "done1" in res["deleted"]
    assert "error1" not in res["deleted"]
    assert "running1" not in res["deleted"]


def test_notification_id_modes(temp_data_dir):
    runner = runner_core.Runner(
        {
            "token": "test",
            "notify_on_completion": True,
            "notification_mode": "per_job",
            "notification_id_prefix": "prefix",
        }
    )
    job = runner_core.Job(job_id="job123")
    assert runner._notification_id(job) == "prefix_job123"

    runner2 = runner_core.Runner(
        {
            "token": "test",
            "notify_on_completion": True,
            "notification_mode": "latest",
            "notification_id_prefix": "prefix",
        }
    )
    assert runner2._notification_id(job) == "prefix_latest"

    runner3 = runner_core.Runner({"token": "test", "notify_on_completion": False})
    assert runner3._notification_id(job) is None


def test_list_jobs_preserves_order(temp_data_dir):
    runner = runner_core.Runner({"token": "test"})

    runner._jobs["first"] = runner_core.Job(job_id="first")
    runner._jobs["second"] = runner_core.Job(job_id="second")
    runner._jobs["third"] = runner_core.Job(job_id="third")
    runner._job_order = ["third", "second", "first"]

    jobs = runner.list_jobs()
    assert [j.job_id for j in jobs] == ["third", "second", "first"]


def test_options_version_matches_config_yaml():
    # Lightweight metadata check: the configured add-on version should match runner_core.
    cfg = Path(__file__).resolve().parent.parent / "config.yaml"
    cfg_text = cfg.read_text(encoding="utf-8")

    version = None
    for ln in cfg_text.splitlines():
        s = ln.strip()
        if s.startswith("version:"):
            version = s.split(":", 1)[1].strip().strip('"\'')
            break

    assert version
    assert version == runner_core.ADDON_VERSION
