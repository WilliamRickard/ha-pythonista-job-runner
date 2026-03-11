# Version: 0.6.12-refactor.7
"""Status persistence and startup loading for job storage."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from utils import TailBuffer, clamp_int, parse_utc, utc_now

from runner.fs_safe import safe_write_text_no_symlink
from runner.store_index import JobIndex


class JobPersistence:
    """Read/write status and rebuild in-memory state from disk."""

    def __init__(self, runner: object, index: JobIndex) -> None:
        self._runner = runner
        self._index = index

    def write_status(self, j: object) -> None:
        try:
            text = json.dumps(getattr(j, "status_dict")(), indent=2, sort_keys=True)
            status_path = getattr(j, "status_path")
            tmp = status_path.with_name(status_path.name + ".tmp")
            safe_write_text_no_symlink(tmp, text)
            try:
                os.replace(str(tmp), str(status_path))
            except Exception:
                safe_write_text_no_symlink(status_path, text)
                try:
                    tmp.unlink()
                except Exception:
                    pass
        except OSError as e:
            try:
                warned = getattr(self._runner, "_status_write_warned")
                jid = getattr(j, "job_id", "unknown")
                if jid not in warned:
                    warned.add(jid)
                    print(f"WARNING: failed to write status for {jid}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            except Exception:
                pass

    def load_jobs_from_disk(self) -> None:
        jobs_dir = getattr(self._runner, "jobs_dir")
        items = self._discover_job_dirs(jobs_dir)
        loaded_jobs, loaded_order = self._deserialize_jobs(items)
        loaded_order.reverse()
        self._index.replace(loaded_jobs, loaded_order)
        for job in self._index.jobs_values_snapshot():
            self.write_status(job)

    def _discover_job_dirs(self, jobs_dir: Path) -> List[Path]:
        items: List[Path] = []
        for p in jobs_dir.iterdir() if jobs_dir.exists() else []:
            if p.is_dir() and (p / "status.json").exists():
                items.append(p)

        def sort_key(path: Path) -> float:
            try:
                data = json.loads((path / "status.json").read_text(encoding="utf-8"))
                return parse_utc(str(data.get("created_utc") or "")) or 0.0
            except Exception:
                try:
                    return path.stat().st_mtime
                except Exception:
                    return 0.0

        items.sort(key=sort_key)
        return items

    def _deserialize_jobs(self, items: List[Path]) -> tuple[Dict[str, object], List[str]]:
        loaded_jobs: Dict[str, object] = {}
        loaded_order: List[str] = []
        JobCls = getattr(self._runner, "Job")

        for p in items:
            try:
                data = json.loads((p / "status.json").read_text(encoding="utf-8"))
            except Exception:
                continue
            job = self._job_from_status(JobCls, p, data)
            loaded_jobs[job.job_id] = job
            loaded_order.append(job.job_id)
        return loaded_jobs, loaded_order

    def _job_from_status(self, JobCls: Any, job_dir: Path, data: Dict[str, Any]) -> object:
        status_job_id = str(data.get("job_id") or "")
        job_id = str(job_dir.name)
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
            j.error = f"{j.error} | {msg}" if j.error else msg

        j.delete_requested = bool(data.get("delete_requested", False))
        self._apply_limits(j, data.get("limits") or {})

        sb = data.get("submitted_by") or {}
        j.submitted_by_id = sb.get("id")
        j.submitted_by_name = sb.get("name")
        j.submitted_by_display_name = sb.get("display_name")
        j.client_ip = data.get("client_ip")
        j.input_sha256 = data.get("input_sha256")

        j.job_dir = job_dir
        j.work_dir = job_dir / "work"
        j.stdout_path = job_dir / "stdout.txt"
        j.stderr_path = job_dir / "stderr.txt"
        j.status_path = job_dir / "status.json"

        rzs = sorted(job_dir.glob("result_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
        j.result_zip = rzs[0] if rzs else (job_dir / "result.zip")

        j.tail_stdout = TailBuffer(int(getattr(self._runner, "tail_chars", 8000)))
        j.tail_stderr = TailBuffer(int(getattr(self._runner, "tail_chars", 8000)))
        j.tail_stdout.seed_from_file_tail(j.stdout_path)
        j.tail_stderr.seed_from_file_tail(j.stderr_path)

        if j.state in ("queued", "running"):
            j.state = "error"
            j.phase = "done"
            if j.exit_code is None:
                j.exit_code = 125
            msg = "runner restarted; job state was not finalised"
            j.error = f"{j.error} | {msg}" if j.error else msg

        return j

    def _apply_limits(self, j: object, limits: Dict[str, Any]) -> None:
        j.cpu_percent = clamp_int(
            str(limits.get("cpu_percent")) if limits.get("cpu_percent") is not None else None,
            int(getattr(self._runner, "default_cpu", 25)),
            1,
            int(getattr(self._runner, "max_cpu", 50)),
        )
        j.cpu_limit_mode = str(limits.get("cpu_limit_mode") or getattr(self._runner, "cpu_limit_mode", "single_core"))
        j.cpu_count = int(limits.get("cpu_count") or (os.cpu_count() or 1))
        j.cpu_cpulimit_pct = int(limits.get("cpu_cpulimit_pct") or j.cpu_percent)
        j.mem_mb = clamp_int(
            str(limits.get("mem_mb")) if limits.get("mem_mb") is not None else None,
            int(getattr(self._runner, "default_mem", 4096)),
            256,
            int(getattr(self._runner, "max_mem", 4096)),
        )
        j.threads = clamp_int(
            str(limits.get("threads")) if limits.get("threads") is not None else None,
            int(getattr(self._runner, "max_threads", 1)),
            1,
            int(getattr(self._runner, "max_threads", 1)),
        )
        j.timeout_seconds = clamp_int(
            str(limits.get("timeout_seconds")) if limits.get("timeout_seconds") is not None else None,
            int(getattr(self._runner, "timeout_seconds", 3600)),
            1,
            int(getattr(self._runner, "timeout_seconds", 3600)),
        )
