# Version: 0.6.12-refactor.7
"""Job storage façade composed from focused index, lifecycle, and persistence helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from runner.process import kill_process_group as kill_process_group  # compat for tests/patching
from runner.state import JobRegistry
from runner.store_index import JobIndex
from runner.store_lifecycle import JobLifecycle
from runner.store_persistence import JobPersistence


class JobStore:
    """Stateful façade for job storage operations used by Runner."""

    def __init__(self, runner: object, registry: Optional[JobRegistry] = None) -> None:
        self._runner = runner
        self._index = JobIndex(runner, registry)
        self._persistence = JobPersistence(runner, self._index)
        self._lifecycle = JobLifecycle(
            runner,
            self._index,
            self._persistence.write_status,
            lambda proc, soft_seconds=2: kill_process_group(proc, soft_seconds=soft_seconds),
        )

    @classmethod
    def for_runner(cls, runner: object) -> "JobStore":
        existing = getattr(runner, "_job_store", None)
        if isinstance(existing, cls):
            return existing
        reg = getattr(runner, "_state", None)
        store = cls(runner, reg if isinstance(reg, JobRegistry) else None)
        setattr(runner, "_job_store", store)
        return store

    def jobs_values_snapshot(self) -> List[object]:
        return self._index.jobs_values_snapshot()

    def get_proc(self, job_id: str) -> Any:
        return self._index.get_proc(job_id)

    def set_proc(self, job_id: str, proc: Any) -> None:
        self._index.set_proc(job_id, proc)

    def pop_proc(self, job_id: str) -> Any:
        return self._index.pop_proc(job_id)

    def discard_job_id(self, job_id: str) -> None:
        self._index.discard_job_id(job_id)

    def list_jobs(self) -> List[object]:
        return self._index.list_jobs()

    def get_job(self, job_id: str) -> Optional[object]:
        return self._index.get_job(job_id)

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> object:
        return self._lifecycle.new_job(zip_bytes, headers, client_ip)

    def finalize_delete(self, job_id: str) -> None:
        self._lifecycle.finalize_delete(job_id)

    def delete_job(self, job_id: str) -> bool:
        return self._lifecycle.delete_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        return self._lifecycle.cancel_job(job_id)

    def purge_jobs(self, states: List[str], older_than_hours: int, dry_run: bool) -> Dict[str, Any]:
        return self._lifecycle.purge_jobs(states, older_than_hours, dry_run)

    def write_status(self, j: object) -> None:
        self._persistence.write_status(j)

    def load_jobs_from_disk(self) -> None:
        self._persistence.load_jobs_from_disk()


def list_jobs(runner: object) -> List[object]:
    return JobStore.for_runner(runner).list_jobs()


def get_job(runner: object, job_id: str) -> Optional[object]:
    return JobStore.for_runner(runner).get_job(job_id)


def new_job(runner: object, zip_bytes: bytes, headers: Any, client_ip: str) -> object:
    return JobStore.for_runner(runner).new_job(zip_bytes, headers, client_ip)


def finalize_delete(runner: object, job_id: str) -> None:
    JobStore.for_runner(runner).finalize_delete(job_id)


def delete_job(runner: object, job_id: str) -> bool:
    return JobStore.for_runner(runner).delete_job(job_id)


def cancel_job(runner: object, job_id: str) -> bool:
    return JobStore.for_runner(runner).cancel_job(job_id)


def purge_jobs(runner: object, states: List[str], older_than_hours: int, dry_run: bool) -> Dict[str, Any]:
    return JobStore.for_runner(runner).purge_jobs(states, older_than_hours, dry_run)


def write_status(runner: object, j: object) -> None:
    JobStore.for_runner(runner).write_status(j)


def load_jobs_from_disk(runner: object) -> None:
    JobStore.for_runner(runner).load_jobs_from_disk()
