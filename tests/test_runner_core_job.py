"""Tests for runner_core.Job."""

from __future__ import annotations

from datetime import datetime, timezone

import runner_core
from utils import utc_now


def test_job_initialisation_defaults() -> None:
    job = runner_core.Job(job_id="test123")

    assert job.job_id == "test123"
    assert job.state == "queued"
    assert job.phase == "queued"
    assert job.exit_code is None
    assert job.error is None
    assert job.cpu_percent == 25
    assert job.mem_mb == 4096
    assert job.timeout_seconds == 3600
    assert job.threads == 1
    assert job.cancel_requested is False


def test_job_initialisation_with_params() -> None:
    job = runner_core.Job(
        job_id="custom123",
        state="running",
        phase="running",
        cpu_percent=50,
        mem_mb=8192,
        timeout_seconds=7200,
        threads=4,
        submitted_by_name="testuser",
        client_ip="192.168.1.1",
    )

    assert job.job_id == "custom123"
    assert job.state == "running"
    assert job.phase == "running"
    assert job.cpu_percent == 50
    assert job.mem_mb == 8192
    assert job.timeout_seconds == 7200
    assert job.threads == 4
    assert job.submitted_by_name == "testuser"
    assert job.client_ip == "192.168.1.1"


def test_duration_seconds_none_if_not_started() -> None:
    job = runner_core.Job(job_id="test")
    assert job.duration_seconds() is None


def test_duration_seconds_running_is_non_negative() -> None:
    # Set started time to 10 seconds ago deterministically.
    start = datetime.now(timezone.utc).timestamp() - 10
    job = runner_core.Job(job_id="test")
    job.started_utc = datetime.fromtimestamp(start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    d = job.duration_seconds()
    assert d is not None
    assert 9 <= d <= 11


def test_duration_seconds_finished_uses_finished_timestamp() -> None:
    start = datetime.now(timezone.utc).timestamp() - 100
    job = runner_core.Job(job_id="test")
    job.started_utc = datetime.fromtimestamp(start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    job.finished_utc = datetime.fromtimestamp(start + 50, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    assert job.duration_seconds() == 50


def test_status_dict_structure() -> None:
    job = runner_core.Job(job_id="test")
    job.state = "done"
    job.phase = "done"
    job.exit_code = 0

    status = job.status_dict()

    assert status["job_id"] == "test"
    assert status["state"] == "done"
    assert status["phase"] == "done"
    assert status["exit_code"] == 0
    assert status["runner_version"] == runner_core.ADDON_VERSION
    assert status["limits"]["cpu_percent"] == 25


def test_status_dict_includes_duration_field() -> None:
    job = runner_core.Job(job_id="test")
    job.started_utc = utc_now()

    status = job.status_dict()
    assert "duration_seconds" in status
    assert status["duration_seconds"] is not None
