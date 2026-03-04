# Version: 0.6.12-refactor.7
"""Unit tests for JobStore registry helpers."""

from __future__ import annotations


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
