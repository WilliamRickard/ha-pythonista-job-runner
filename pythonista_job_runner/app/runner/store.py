# Version: 0.6.12-refactor.4
"""Job storage and lifecycle operations.

This module provides a stateful JobStore façade used by Runner.

For compatibility, the historic module-level functions still exist with the
same signatures. They delegate to JobStore so external callers and the test
suite do not need to change.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils import TailBuffer, clamp_int, parse_utc, safe_extract_zip_bytes, utc_now

from runner.fs_safe import safe_write_text_no_symlink
from runner.hashes import hashlib_sha256_bytes
from runner.process import kill_process_group
from runner.state import JobRegistry


class JobStore:
    """Stateful façade for job storage operations."""

    def __init__(self, runner: object, registry: Optional[JobRegistry] = None) -> None:
        self._runner = runner
        self._registry = registry

    def _lock(self) -> threading.Lock:
        if self._registry is not None:
            return self._registry.lock
        return getattr(self._runner, "_lock")

    def _jobs(self) -> Dict[str, Any]:
        if self._registry is not None:
            return self._registry.jobs
        return getattr(self._runner, "_jobs")

    def _job_order(self) -> List[str]:
        if self._registry is not None:
            return self._registry.job_order
        return getattr(self._runner, "_job_order")

    def _procs(self) -> Dict[str, Any]:
        if self._registry is not None:
            return self._registry.procs
        return getattr(self._runner, "_procs")

    @classmethod
    def for_runner(cls, runner: object) -> "JobStore":
        """Return the cached JobStore for runner, creating one if needed."""

        existing = getattr(runner, "_job_store", None)
        if isinstance(existing, cls):
            return existing

        reg = getattr(runner, "_state", None)
        store = cls(runner, reg if isinstance(reg, JobRegistry) else None)
        setattr(runner, "_job_store", store)
        return store

    def list_jobs(self) -> List[object]:
        lock = self._lock()
        jobs = self._jobs()
        job_order = self._job_order()
        with lock:
            return [jobs[jid] for jid in job_order if jid in jobs]

    def get_job(self, job_id: str) -> Optional[object]:
        lock = self._lock()
        jobs = self._jobs()
        with lock:
            return jobs.get(job_id)

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> object:
        runner = self._runner
        if bool(getattr(runner, "_is_root", False)) and (
            getattr(runner, "_job_uid", None) is None or getattr(runner, "_job_gid", None) is None
        ):
            # Refuse to execute untrusted code as root due to misconfiguration.
            raise RuntimeError("job_user_missing")

        slot_reserved = False
        job_registered = False
        job_dir: Optional[Path] = None

        try:
            lock = self._lock()
            jobs = self._jobs()

            with lock:
                active = sum(1 for j in jobs.values() if j.state in ("queued", "running"))
                active += int(getattr(runner, "_pending_slots", 0))
                if active >= int(getattr(runner, "queue_max_jobs", 0)):
                    raise RuntimeError("queue_full")
                setattr(runner, "_pending_slots", int(getattr(runner, "_pending_slots", 0)) + 1)
                slot_reserved = True

            try:
                getattr(runner, "_ensure_min_free_space")()
            except Exception:
                pass

            cpu = clamp_int(
                headers.get("X-Runner-CPU-PCT"),
                int(getattr(runner, "default_cpu", 25)),
                1,
                int(getattr(runner, "max_cpu", 50)),
            )
            mem = clamp_int(
                headers.get("X-Runner-MEM-MB"),
                int(getattr(runner, "default_mem", 4096)),
                256,
                int(getattr(runner, "max_mem", 4096)),
            )
            thr = clamp_int(
                headers.get("X-Runner-THREADS"),
                int(getattr(runner, "max_threads", 1)),
                1,
                int(getattr(runner, "max_threads", 1)),
            )
            timeout = clamp_int(
                headers.get("X-Runner-TIMEOUT"),
                int(getattr(runner, "timeout_seconds", 3600)),
                1,
                int(getattr(runner, "timeout_seconds", 3600)),
            )

            job_id = uuid.uuid4().hex
            jobs_dir = getattr(runner, "jobs_dir")
            job_dir = jobs_dir / job_id
            work_dir = job_dir / "work"
            job_dir.mkdir(parents=True, exist_ok=True)
            work_dir.mkdir(parents=True, exist_ok=True)

            safe_extract_zip_bytes(zip_bytes, work_dir, getattr(runner, "safe_zip_limits"))
            getattr(runner, "_prepare_work_dir")(work_dir)

            run_py = work_dir / "run.py"
            if not run_py.exists():
                raise RuntimeError("zip_missing_run_py")

            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

            cpu_count = os.cpu_count() or 1
            mode = str(getattr(runner, "cpu_limit_mode", "single_core"))
            if mode not in ("single_core", "total_machine"):
                mode = "single_core"
            eff = cpu
            if mode == "total_machine":
                eff = min(cpu * cpu_count, 100 * cpu_count)

            JobCls = getattr(runner, "Job")

            j = JobCls(
                job_id=job_id,
                cpu_percent=cpu,
                cpu_limit_mode=mode,
                cpu_count=cpu_count,
                cpu_cpulimit_pct=eff,
                mem_mb=mem,
                threads=thr,
                timeout_seconds=timeout,
                job_dir=job_dir,
                work_dir=work_dir,
                stdout_path=job_dir / "stdout.txt",
                stderr_path=job_dir / "stderr.txt",
                status_path=job_dir / "status.json",
                result_zip=job_dir / f"result_{stamp}_{job_id}.zip",
                tail_stdout=TailBuffer(int(getattr(runner, "tail_chars", 8000))),
                tail_stderr=TailBuffer(int(getattr(runner, "tail_chars", 8000))),
                client_ip=client_ip,
                input_sha256=hashlib_sha256_bytes(zip_bytes),
            )

            ingress_proxy_ip = str(getattr(runner, "ingress_proxy_ip", ""))
            if client_ip == ingress_proxy_ip:
                j.submitted_by_id = headers.get("X-Remote-User-Id")
                j.submitted_by_name = headers.get("X-Remote-User-Name")
                j.submitted_by_display_name = headers.get("X-Remote-User-Display-Name")
                j.ingress_path = headers.get("X-Ingress-Path")

            with lock:
                jobs[job_id] = j
                self._job_order().insert(0, job_id)
                job_registered = True
                if slot_reserved:
                    setattr(
                        runner,
                        "_pending_slots",
                        max(0, int(getattr(runner, "_pending_slots", 0)) - 1),
                    )
                    slot_reserved = False

            self.write_status(j)
            threading.Thread(target=getattr(runner, "_run_job"), args=(job_id,), daemon=True).start()
            return j

        except Exception:
            if (not job_registered) and job_dir is not None:
                try:
                    shutil.rmtree(job_dir, ignore_errors=True)
                except Exception:
                    pass
            raise

        finally:
            if slot_reserved:
                lock = self._lock()
                with lock:
                    setattr(
                        runner,
                        "_pending_slots",
                        max(0, int(getattr(runner, "_pending_slots", 0)) - 1),
                    )

    def finalize_delete(self, job_id: str) -> None:
        """Remove job state and delete its on-disk directory (best-effort)."""

        j = self.get_job(job_id)
        if not j:
            return

        try:
            shutil.rmtree(j.job_dir, ignore_errors=True)
        except Exception:
            pass

        lock = self._lock()
        jobs = self._jobs()
        procs = self._procs()
        runner = self._runner

        with lock:
            jobs.pop(job_id, None)
            job_order = self._job_order()
            if job_id in job_order:
                job_order.remove(job_id)
            procs.pop(job_id, None)

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        If the job is still queued or running, mark it for deletion and cancel it.
        The directory is removed once the job thread exits to avoid races with
        ongoing log and result writes.
        """

        j = self.get_job(job_id)
        if not j:
            return False

        if j.state in ("queued", "running"):
            j.delete_requested = True
            self.cancel_job(job_id)
            self.write_status(j)
            return True

        self.finalize_delete(job_id)
        return True

    def cancel_job(self, job_id: str) -> bool:
        j = self.get_job(job_id)
        if not j:
            return False

        j.cancel_requested = True

        lock = self._lock()
        procs = self._procs()
        with lock:
            p = procs.get(job_id)

        if p is not None and p.poll() is None:
            kill_process_group(p, soft_seconds=2)

        return True

    def purge_jobs(self, states: List[str], older_than_hours: int, dry_run: bool) -> Dict[str, Any]:
        now = time.time()
        older_than_s = max(0, older_than_hours) * 3600
        to_delete: List[str] = []

        lock = self._lock()
        jobs = self._jobs()
        job_order = self._job_order()

        with lock:
            for job_id in list(job_order):
                j = jobs.get(job_id)
                if not j:
                    continue
                if states and (j.state not in states):
                    continue
                if older_than_s > 0:
                    ts_str = j.finished_utc or j.created_utc
                    t = parse_utc(ts_str) or 0.0
                    if t and (now - t) < older_than_s:
                        continue
                to_delete.append(job_id)

        deleted: List[str] = []
        for job_id in to_delete:
            if dry_run:
                deleted.append(job_id)
                continue
            try:
                _ = self.delete_job(job_id)
                deleted.append(job_id)
            except Exception:
                continue

        return {"ok": True, "deleted": deleted, "count": len(deleted), "dry_run": dry_run}

    def write_status(self, j: object) -> None:
        runner = self._runner
        try:
            text = json.dumps(getattr(j, "status_dict")(), indent=2, sort_keys=True)
            tmp = getattr(j, "status_path").with_name(getattr(j, "status_path").name + ".tmp")
            safe_write_text_no_symlink(tmp, text)
            try:
                os.replace(str(tmp), str(getattr(j, "status_path")))
            except Exception:
                safe_write_text_no_symlink(getattr(j, "status_path"), text)
                try:
                    tmp.unlink()
                except Exception:
                    pass
        except OSError as e:
            try:
                warned = getattr(runner, "_status_write_warned")
                jid = getattr(j, "job_id", "unknown")
                if jid not in warned:
                    warned.add(jid)
                    print(
                        f"WARNING: failed to write status for {jid}: {type(e).__name__}: {e}",
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception:
                pass

    def load_jobs_from_disk(self) -> None:
        """Rebuild job index from /data/jobs on startup."""

        runner = self._runner
        jobs_dir = getattr(runner, "jobs_dir")

        items: List[Path] = []
        for p in jobs_dir.iterdir() if jobs_dir.exists() else []:
            if not p.is_dir():
                continue
            status_path = p / "status.json"
            if not status_path.exists():
                continue
            items.append(p)

        def sort_key(p: Path) -> float:
            try:
                data = json.loads((p / "status.json").read_text(encoding="utf-8"))
                t = parse_utc(str(data.get("created_utc") or "")) or 0.0
                return t
            except Exception:
                try:
                    return p.stat().st_mtime
                except Exception:
                    return 0.0

        items.sort(key=sort_key, reverse=False)

        loaded_jobs: Dict[str, object] = {}
        loaded_order: List[str] = []

        JobCls = getattr(runner, "Job")

        for p in items:
            try:
                data = json.loads((p / "status.json").read_text(encoding="utf-8"))
            except Exception:
                continue

            status_job_id = str(data.get("job_id") or "")
            job_id = str(p.name)
            status_id_mismatch = bool(status_job_id and status_job_id != job_id)
            j = JobCls(job_id=job_id)

            j.created_utc = str(data.get("created_utc") or utc_now())
            j.started_utc = data.get("started_utc")
            j.finished_utc = data.get("finished_utc")
            j.state = str(data.get("state") or "error")
            j.phase = str(data.get("phase") or j.state)
            j.exit_code = data.get("exit_code")
            j.error = data.get("error")

            if status_id_mismatch:
                msg = f"status_job_id_mismatch: {status_job_id}"
                if j.error:
                    j.error = f"{j.error} | {msg}"
                else:
                    j.error = msg

            j.delete_requested = bool(data.get("delete_requested", False))

            lim = data.get("limits") or {}
            j.cpu_percent = clamp_int(
                str(lim.get("cpu_percent")) if lim.get("cpu_percent") is not None else None,
                int(getattr(runner, "default_cpu", 25)),
                1,
                int(getattr(runner, "max_cpu", 50)),
            )
            j.cpu_limit_mode = str(lim.get("cpu_limit_mode") or getattr(runner, "cpu_limit_mode", "single_core"))
            j.cpu_count = int(lim.get("cpu_count") or (os.cpu_count() or 1))
            j.cpu_cpulimit_pct = int(lim.get("cpu_cpulimit_pct") or j.cpu_percent)
            j.mem_mb = clamp_int(
                str(lim.get("mem_mb")) if lim.get("mem_mb") is not None else None,
                int(getattr(runner, "default_mem", 4096)),
                256,
                int(getattr(runner, "max_mem", 4096)),
            )
            j.threads = clamp_int(
                str(lim.get("threads")) if lim.get("threads") is not None else None,
                int(getattr(runner, "max_threads", 1)),
                1,
                int(getattr(runner, "max_threads", 1)),
            )
            j.timeout_seconds = clamp_int(
                str(lim.get("timeout_seconds")) if lim.get("timeout_seconds") is not None else None,
                int(getattr(runner, "timeout_seconds", 3600)),
                1,
                int(getattr(runner, "timeout_seconds", 3600)),
            )

            sb = data.get("submitted_by") or {}
            j.submitted_by_id = sb.get("id")
            j.submitted_by_name = sb.get("name")
            j.submitted_by_display_name = sb.get("display_name")

            j.client_ip = data.get("client_ip")
            j.input_sha256 = data.get("input_sha256")

            j.job_dir = p
            j.work_dir = p / "work"
            j.stdout_path = p / "stdout.txt"
            j.stderr_path = p / "stderr.txt"
            j.status_path = p / "status.json"

            rzs = sorted(p.glob("result_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
            if rzs:
                j.result_zip = rzs[0]
            else:
                j.result_zip = p / "result.zip"

            j.tail_stdout = TailBuffer(int(getattr(runner, "tail_chars", 8000)))
            j.tail_stderr = TailBuffer(int(getattr(runner, "tail_chars", 8000)))
            j.tail_stdout.seed_from_file_tail(j.stdout_path)
            j.tail_stderr.seed_from_file_tail(j.stderr_path)

            if j.state in ("queued", "running"):
                j.state = "error"
                j.phase = "done"
                if j.exit_code is None:
                    j.exit_code = 125
                msg = "runner restarted; job state was not finalised"
                if j.error:
                    j.error = f"{j.error} | {msg}"
                else:
                    j.error = msg

            loaded_jobs[j.job_id] = j
            loaded_order.append(j.job_id)

        loaded_order.reverse()

        lock = self._lock()
        jobs = self._jobs()

        with lock:
            jobs.clear()
            jobs.update(loaded_jobs)
            self._job_order().clear()
            self._job_order().extend(loaded_order)

        with lock:
            jobs_list = list(jobs.values())

        for j in jobs_list:
            self.write_status(j)


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
