"""Tests for backup pause/resume behavior."""

from __future__ import annotations

from pathlib import Path

from runner.store_lifecycle import JobLifecycle


REPO_PACKAGE_ROOT = Path(__file__).resolve().parents[1]


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


def test_runner_core_contains_pause_restore_methods() -> None:
    text = (REPO_PACKAGE_ROOT / "app/runner_core.py").read_text(encoding="utf-8")
    assert "def pause_for_backup" in text
    assert "def resume_after_backup" in text
    assert "def pause_status" in text
