"""Tests for backup pause/resume behavior."""

from __future__ import annotations

from pathlib import Path

from runner.store_lifecycle import JobLifecycle

import runner_core


class _DummyIndex:
    def reserve_pending_slot(self, _max_jobs: int) -> None:
        return

    def release_pending_slot(self) -> None:
        return


class _Runner:
    _paused = True


def test_lifecycle_rejects_new_job_when_paused() -> None:
    lifecycle = JobLifecycle(_Runner(), _DummyIndex(), lambda _: None)
    try:
        lifecycle.new_job(Path("/tmp/does_not_matter"), {}, "127.0.0.1")
    except RuntimeError as exc:
        assert str(exc) == "runner_paused_for_backup"
    else:
        raise AssertionError("Expected RuntimeError when runner is paused")


def test_runner_pause_resume_status_runtime_contract(temp_data_dir) -> None:
    runner = runner_core.Runner({"token": "t"}, start_reaper=False)

    assert runner.pause_status() == {"paused": False, "reason": ""}

    paused = runner.pause_for_backup(reason="ha_backup")
    assert paused == {"paused": True, "reason": "ha_backup"}
    assert runner.pause_status() == {"paused": True, "reason": "ha_backup"}

    resumed = runner.resume_after_backup()
    assert resumed == {"paused": False, "previous_reason": "ha_backup"}
    assert runner.pause_status() == {"paused": False, "reason": ""}
