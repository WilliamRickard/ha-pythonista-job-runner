# Version: 0.6.12-refactor.9
"""Unit tests for JobStore registry helpers."""

from __future__ import annotations


import io
import threading
from pathlib import Path

import runner.executor as executor_mod

import pytest
import runner_core
from runner.store import JobStore
import runner.store as store_mod


def _make_runner(temp_data_dir) -> runner_core.Runner:
    # Minimal opts; temp_data_dir fixture patches runner_core paths before this is called.
    return runner_core.Runner({})


def test_discard_job_id_removes_job_proc_and_order(temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-1"
    runner._jobs[jid] = runner_core.Job(job_id=jid)
    runner._job_order = [jid, "other"]

    proc = object()
    store.set_proc(jid, proc)

    store.discard_job_id(jid)

    assert jid not in runner._jobs
    assert jid not in runner._job_order
    assert jid not in runner._procs


def test_discard_job_id_when_not_in_order_preserves_other_entries(temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-2"
    runner._jobs[jid] = runner_core.Job(job_id=jid)
    runner._job_order = ["a", "b", "c"]

    store.discard_job_id(jid)

    assert jid not in runner._jobs
    assert runner._job_order == ["a", "b", "c"]


def test_discard_job_id_removes_proc_even_without_job(temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-3"
    runner._job_order = [jid]
    store.set_proc(jid, object())

    store.discard_job_id(jid)

    assert jid not in runner._job_order
    assert jid not in runner._procs
class _DummyProc:
    def __init__(self, running: bool = True) -> None:
        self._running = running

    def poll(self):
        return None if self._running else 0


def test_set_proc_cancel_kills_running_and_pop_proc_clears(monkeypatch, temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-cancel"
    job = runner_core.Job(job_id=jid, state="running")
    runner._jobs[jid] = job
    runner._job_order.append(jid)

    proc = _DummyProc(running=True)
    store.set_proc(jid, proc)

    calls = []

    def _stub_kill(p, soft_seconds=0):
        calls.append((p, soft_seconds))

    monkeypatch.setattr(store_mod, "kill_process_group", _stub_kill)

    assert runner.cancel(jid) is True
    assert job.cancel_requested is True
    assert calls == [(proc, 2)]

    # cancel does not clear the proc entry; executor will clear later
    assert store.get_proc(jid) is proc
    assert store.pop_proc(jid) is proc
    assert store.get_proc(jid) is None


def test_delete_done_job_discards_proc_entry(temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-delete-done"
    job = runner_core.Job(job_id=jid, state="done")
    runner._jobs[jid] = job
    runner._job_order.append(jid)

    proc = _DummyProc(running=False)
    store.set_proc(jid, proc)

    assert runner.delete(jid) is True

    assert runner.get(jid) is None
    assert jid not in runner._job_order
    assert store.get_proc(jid) is None

def test_delete_running_job_marks_delete_and_cancel_but_keeps_registry(monkeypatch, temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-delete-running"
    job = runner_core.Job(job_id=jid, state="running")
    runner._jobs[jid] = job
    runner._job_order.append(jid)

    proc = _DummyProc(running=True)
    store.set_proc(jid, proc)

    calls = []

    def _stub_kill(p, soft_seconds=0):
        calls.append((p, soft_seconds))

    monkeypatch.setattr(store_mod, "kill_process_group", _stub_kill)

    assert runner.delete(jid) is True

    # For running jobs, delete marks flags and cancels, but does not remove from registry yet.
    assert job.delete_requested is True
    assert job.cancel_requested is True
    assert runner.get(jid) is job
    assert jid in runner._job_order
    assert store.get_proc(jid) is proc
    assert calls == [(proc, 2)]


class _BlockingPopen:
    def __init__(self, *args, **kwargs) -> None:
        self.stdout = io.BytesIO(b"stdout\n")
        self.stderr = io.BytesIO(b"stderr\n")
        self._running = True

    def poll(self):
        return None if self._running else 0


def test_delete_requested_finalizes_after_executor_exit(monkeypatch, temp_data_dir):
    runner = _make_runner(temp_data_dir)
    store = JobStore.for_runner(runner)

    jid = "job-delete-finalize"
    job_dir = Path(runner_core.JOBS_DIR) / jid
    work_dir = job_dir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "run.py").write_text("print('ok')\n", encoding="utf-8")

    job = runner_core.Job(job_id=jid, state="queued")
    job.job_dir = job_dir
    job.work_dir = work_dir
    job.stdout_path = job_dir / "stdout.txt"
    job.stderr_path = job_dir / "stderr.txt"
    job.status_path = job_dir / "status.json"
    job.result_zip = job_dir / "result.zip"

    runner._jobs[jid] = job
    runner._job_order.append(jid)

    proc_set = threading.Event()
    orig_set_proc = store.set_proc

    def _set_proc(job_id, proc):
        orig_set_proc(job_id, proc)
        proc_set.set()

    # Patch the store instance so executor.run_job sees the event when it registers the proc.
    monkeypatch.setattr(store, "set_proc", _set_proc)

    kill_calls = []

    def _stub_kill(p, soft_seconds=0):
        kill_calls.append((p, soft_seconds))
        if hasattr(p, "_running"):
            p._running = False

    # delete() calls store_mod.kill_process_group; executor calls executor_mod.kill_process_group.
    monkeypatch.setattr(store_mod, "kill_process_group", _stub_kill)
    monkeypatch.setattr(executor_mod, "kill_process_group", _stub_kill)

    monkeypatch.setattr(executor_mod.subprocess, "Popen", _BlockingPopen)
    monkeypatch.setattr(executor_mod.time, "sleep", lambda _s: None)

    # Keep the test focused on lifecycle; result/notify are covered elsewhere.
    monkeypatch.setattr(runner, "_make_result_zip", lambda _j: None)
    monkeypatch.setattr(runner, "_notify_done", lambda _j: None)

    t = threading.Thread(target=runner._run_job, args=(jid,), daemon=True)
    t.start()

    assert proc_set.wait(timeout=2), "executor never started the job subprocess"
    assert runner.delete(jid) is True

    t.join(timeout=5)
    assert not t.is_alive(), "executor thread did not exit"

    assert runner.get(jid) is None
    assert jid not in runner._job_order
    assert store.get_proc(jid) is None
    assert not job_dir.exists()

    assert kill_calls, "expected a kill_process_group call when cancelling the running job"
