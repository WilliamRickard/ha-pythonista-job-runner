# Version: 0.6.12-refactor.7
"""Lifecycle operations for creation, cancellation, deletion and purge."""

from __future__ import annotations

import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from utils import TailBuffer, clamp_int, parse_utc, safe_extract_zip_bytes

from runner.hashes import hashlib_sha256_bytes
from runner.process import kill_process_group
from runner.store_index import JobIndex


class JobLifecycle:
    """Mutating lifecycle operations over jobs backed by JobIndex."""

    def __init__(
        self,
        runner: object,
        index: JobIndex,
        write_status: Callable[[object], None],
        kill_process_group_fn: Callable[..., None] = kill_process_group,
    ) -> None:
        self._runner = runner
        self._index = index
        self._write_status = write_status
        self._kill_process_group = kill_process_group_fn

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> object:
        runner = self._runner
        if bool(getattr(runner, "_is_root", False)) and (
            getattr(runner, "_job_uid", None) is None or getattr(runner, "_job_gid", None) is None
        ):
            raise RuntimeError("job_user_missing")

        slot_reserved = False
        job_registered = False
        job_dir: Path | None = None
        try:
            self._index.reserve_pending_slot(int(getattr(runner, "queue_max_jobs", 0)))
            slot_reserved = True
            try:
                getattr(runner, "_ensure_min_free_space")()
            except Exception:
                pass

            limits = self._parse_limits(headers)
            job_id = uuid.uuid4().hex
            job_dir, work_dir = self._create_work_dirs(job_id)
            safe_extract_zip_bytes(zip_bytes, work_dir, getattr(runner, "safe_zip_limits"))
            getattr(runner, "_prepare_work_dir")(work_dir)
            if not (work_dir / "run.py").exists():
                raise RuntimeError("zip_missing_run_py")

            j = self._build_job(job_id, job_dir, work_dir, limits, zip_bytes, headers, client_ip)
            self._index.insert_job_front(job_id, j)
            job_registered = True
            if slot_reserved:
                self._index.release_pending_slot()
                slot_reserved = False

            self._write_status(j)
            threading.Thread(target=getattr(runner, "_run_job"), args=(job_id,), daemon=True).start()
            return j
        except Exception:
            if (not job_registered) and job_dir is not None:
                shutil.rmtree(job_dir, ignore_errors=True)
            raise
        finally:
            if slot_reserved:
                self._index.release_pending_slot()

    def finalize_delete(self, job_id: str) -> None:
        j = self._index.get_job(job_id)
        if not j:
            return
        shutil.rmtree(j.job_dir, ignore_errors=True)
        self._index.discard_job_id(job_id)

    def delete_job(self, job_id: str) -> bool:
        j = self._index.get_job(job_id)
        if not j:
            return False
        if j.state in ("queued", "running"):
            j.delete_requested = True
            self.cancel_job(job_id)
            self._write_status(j)
            return True
        self.finalize_delete(job_id)
        return True

    def cancel_job(self, job_id: str) -> bool:
        j = self._index.get_job(job_id)
        if not j:
            return False
        j.cancel_requested = True
        proc = self._index.get_proc(job_id)
        if proc is not None and proc.poll() is None:
            self._kill_process_group(proc, soft_seconds=2)
        return True

    def purge_jobs(self, states: List[str], older_than_hours: int, dry_run: bool) -> Dict[str, Any]:
        now = time.time()
        older_than_s = max(0, older_than_hours) * 3600
        to_delete: List[str] = []

        for job_id in [j.job_id for j in self._index.list_jobs()]:
            j = self._index.get_job(job_id)
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
                self.delete_job(job_id)
                deleted.append(job_id)
            except Exception:
                continue
        return {"ok": True, "deleted": deleted, "count": len(deleted), "dry_run": dry_run}

    def _parse_limits(self, headers: Any) -> Dict[str, int | str]:
        runner = self._runner
        cpu = clamp_int(headers.get("X-Runner-CPU-PCT"), int(getattr(runner, "default_cpu", 25)), 1, int(getattr(runner, "max_cpu", 50)))
        mem = clamp_int(headers.get("X-Runner-MEM-MB"), int(getattr(runner, "default_mem", 4096)), 256, int(getattr(runner, "max_mem", 4096)))
        thr = clamp_int(headers.get("X-Runner-THREADS"), int(getattr(runner, "max_threads", 1)), 1, int(getattr(runner, "max_threads", 1)))
        timeout = clamp_int(headers.get("X-Runner-TIMEOUT"), int(getattr(runner, "timeout_seconds", 3600)), 1, int(getattr(runner, "timeout_seconds", 3600)))

        cpu_count = os.cpu_count() or 1
        mode = str(getattr(runner, "cpu_limit_mode", "single_core"))
        if mode not in ("single_core", "total_machine"):
            mode = "single_core"
        effective_cpu = cpu if mode == "single_core" else min(cpu * cpu_count, 100 * cpu_count)
        return {"cpu": cpu, "mem": mem, "threads": thr, "timeout": timeout, "cpu_count": cpu_count, "mode": mode, "effective_cpu": effective_cpu}

    def _create_work_dirs(self, job_id: str) -> tuple[Path, Path]:
        jobs_dir = getattr(self._runner, "jobs_dir")
        job_dir = jobs_dir / job_id
        work_dir = job_dir / "work"
        job_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)
        return job_dir, work_dir

    def _build_job(self, job_id: str, job_dir: Path, work_dir: Path, limits: Dict[str, int | str], zip_bytes: bytes, headers: Any, client_ip: str) -> object:
        runner = self._runner
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        JobCls = getattr(runner, "Job")
        j = JobCls(
            job_id=job_id,
            cpu_percent=limits["cpu"],
            cpu_limit_mode=limits["mode"],
            cpu_count=limits["cpu_count"],
            cpu_cpulimit_pct=limits["effective_cpu"],
            mem_mb=limits["mem"],
            threads=limits["threads"],
            timeout_seconds=limits["timeout"],
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
        if client_ip == str(getattr(runner, "ingress_proxy_ip", "")):
            j.submitted_by_id = headers.get("X-Remote-User-Id")
            j.submitted_by_name = headers.get("X-Remote-User-Name")
            j.submitted_by_display_name = headers.get("X-Remote-User-Display-Name")
            j.ingress_path = headers.get("X-Ingress-Path")
        return j
