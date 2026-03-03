"""Edge and boundary condition tests for runner_core."""

from __future__ import annotations

import os

import runner_core


def test_duration_seconds_handles_invalid_timestamps():
    job = runner_core.Job(job_id="test")
    job.started_utc = "not-a-timestamp"
    job.finished_utc = "also-not-a-timestamp"

    d = job.duration_seconds()
    assert isinstance(d, int)
    assert d >= 0


def test_cpu_limit_mode_is_stored_as_given(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "cpu_limit_mode": "invalid_mode"})
    assert runner.cpu_limit_mode == "invalid_mode"


def test_allow_env_filters_invalid_names(temp_data_dir):
    runner = runner_core.Runner(
        {
            "token": "t",
            "allow_env": ["VALID_VAR", "123invalid", "also-invalid", "ANOTHER_VALID"],
        }
    )

    assert "VALID_VAR" in runner.allow_env
    assert "ANOTHER_VALID" in runner.allow_env
    assert "123invalid" not in runner.allow_env
    assert "also-invalid" not in runner.allow_env


def test_semaphore_allows_at_least_one_acquire(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "max_concurrent_jobs": 0})

    ok = runner._sema.acquire(blocking=False)
    assert ok is True
    runner._sema.release()


def test_negative_retention_hours_is_stored(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "job_retention_hours": -10})
    assert runner.retention_hours == 1
