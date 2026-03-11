# Version: 0.6.12-refactor.7
"""In-memory indexing primitives for job storage."""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from runner.state import JobRegistry


class JobIndex:
    """Encapsulates lock-protected job and process index operations."""

    def __init__(self, runner: object, registry: Optional[JobRegistry] = None) -> None:
        self._runner = runner
        self._registry = registry

    @property
    def lock(self) -> threading.Lock:
        if self._registry is not None:
            return self._registry.lock
        return getattr(self._runner, "_lock")

    @property
    def jobs(self) -> Dict[str, Any]:
        if self._registry is not None:
            return self._registry.jobs
        return getattr(self._runner, "_jobs")

    @property
    def job_order(self) -> List[str]:
        if self._registry is not None:
            return self._registry.job_order
        return getattr(self._runner, "_job_order")

    @property
    def procs(self) -> Dict[str, Any]:
        if self._registry is not None:
            return self._registry.procs
        return getattr(self._runner, "_procs")

    def jobs_values_snapshot(self) -> List[object]:
        with self.lock:
            return list(self.jobs.values())

    def list_jobs(self) -> List[object]:
        with self.lock:
            return [self.jobs[jid] for jid in self.job_order if jid in self.jobs]

    def get_job(self, job_id: str) -> Optional[object]:
        with self.lock:
            return self.jobs.get(job_id)

    def insert_job_front(self, job_id: str, job: object) -> None:
        with self.lock:
            self.jobs[job_id] = job
            self.job_order.insert(0, job_id)

    def set_proc(self, job_id: str, proc: Any) -> None:
        with self.lock:
            self.procs[job_id] = proc

    def get_proc(self, job_id: str) -> Any:
        with self.lock:
            return self.procs.get(job_id)

    def pop_proc(self, job_id: str) -> Any:
        with self.lock:
            return self.procs.pop(job_id, None)

    def discard_job_id(self, job_id: str) -> None:
        with self.lock:
            self.jobs.pop(job_id, None)
            self.procs.pop(job_id, None)
            current_order = list(self.job_order)
            setattr(self._runner, "_job_order", [x for x in current_order if x != job_id])

    def replace(self, jobs: Dict[str, object], order: List[str]) -> None:
        with self.lock:
            self.jobs.clear()
            self.jobs.update(jobs)
            self.job_order.clear()
            self.job_order.extend(order)

    def reserve_pending_slot(self, queue_max_jobs: int) -> None:
        with self.lock:
            active = sum(1 for j in self.jobs.values() if j.state in ("queued", "running"))
            active += int(getattr(self._runner, "_pending_slots", 0))
            if active >= queue_max_jobs:
                raise RuntimeError("queue_full")
            setattr(self._runner, "_pending_slots", int(getattr(self._runner, "_pending_slots", 0)) + 1)

    def release_pending_slot(self) -> None:
        with self.lock:
            setattr(self._runner, "_pending_slots", max(0, int(getattr(self._runner, "_pending_slots", 0)) - 1))
