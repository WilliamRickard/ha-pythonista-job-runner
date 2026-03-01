from __future__ import annotations

import json
import os
import re
import shutil
import hashlib
import os
import re
import shutil
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import resource  # type: ignore
except Exception:
    resource = None  # type: ignore[assignment]

try:
    import pwd  # type: ignore
    import grp  # type: ignore
except Exception:
    pwd = None  # type: ignore[assignment]
    grp = None  # type: ignore[assignment]

from utils import (
    SafeZipLimits,
    TailBuffer,
    clamp_int,
    file_tail_text,
    parse_utc,
    read_head_tail_text,
    safe_extract_zip_bytes,
    sha256_file,
    utc_now,
)

ADDON_VERSION = "0.6.0"

DATA_DIR = Path("/data")
OPTIONS_PATH = DATA_DIR / "options.json"
JOBS_DIR = DATA_DIR / "jobs"

INGRESS_PROXY_IP = "172.30.32.2"
SUPERVISOR_CORE_API = "http://supervisor/core/api"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


def read_options() -> Dict[str, Any]:
    if not OPTIONS_PATH.exists():
        return {}
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_user_ids(username: str) -> tuple[Optional[int], Optional[int]]:
    """Return (uid, gid) for username, or (None, None) if unavailable."""
    if not username:
        return (None, None)
    if pwd is None:
        return (None, None)
    try:
        pw = pwd.getpwnam(username)  # type: ignore[attr-defined]
        return (int(pw.pw_uid), int(pw.pw_gid))
    except Exception:
        return (None, None)


@dataclass
class Job:
    job_id: str
    created_utc: str = field(default_factory=utc_now)
    started_utc: Optional[str] = None
    finished_utc: Optional[str] = None
    state: str = "queued"  # queued|running|done|error
    phase: str = "queued"  # queued|running|done|error
    exit_code: Optional[int] = None
    error: Optional[str] = None

    cpu_percent: int = 25
    cpu_limit_mode: str = "single_core"
    cpu_count: int = 1
    cpu_cpulimit_pct: int = 25
    mem_mb: int = 4096
    timeout_seconds: int = 3600
    threads: int = 1

    submitted_by_name: Optional[str] = None
    submitted_by_display_name: Optional[str] = None
    submitted_by_id: Optional[str] = None
    ingress_path: Optional[str] = None
    client_ip: Optional[str] = None

    input_sha256: Optional[str] = None

    cancel_requested: bool = False

    job_dir: Path = field(default_factory=lambda: JOBS_DIR / "unset")
    work_dir: Path = field(default_factory=lambda: JOBS_DIR / "unset" / "work")

    stdout_path: Path = field(default_factory=lambda: JOBS_DIR / "unset" / "stdout.txt")
    stderr_path: Path = field(default_factory=lambda: JOBS_DIR / "unset" / "stderr.txt")
    status_path: Path = field(default_factory=lambda: JOBS_DIR / "unset" / "status.json")
    result_zip: Path = field(default_factory=lambda: JOBS_DIR / "unset" / "result.zip")

    tail_stdout: TailBuffer = field(default_factory=lambda: TailBuffer(8000))
    tail_stderr: TailBuffer = field(default_factory=lambda: TailBuffer(8000))

    def duration_seconds(self) -> Optional[int]:
        if not self.started_utc:
            return None
        t0 = parse_utc(self.started_utc) or 0.0
        t1 = parse_utc(self.finished_utc) if self.finished_utc else time.time()
        if not t1:
            t1 = time.time()
        d = int(max(0.0, float(t1) - float(t0)))
        return d

    def status_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_utc": self.created_utc,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "duration_seconds": self.duration_seconds(),
            "state": self.state,
            "phase": self.phase,
            "exit_code": self.exit_code,
            "error": self.error,
            "runner_version": ADDON_VERSION,
            "client_ip": self.client_ip,
            "submitted_by": {
                "id": self.submitted_by_id,
                "name": self.submitted_by_name,
                "display_name": self.submitted_by_display_name,
            },
            "limits": {
                "cpu_percent": self.cpu_percent,
                "cpu_limit_mode": self.cpu_limit_mode,
                "cpu_count": self.cpu_count,
                "cpu_cpulimit_pct": self.cpu_cpulimit_pct,
                "mem_mb": self.mem_mb,
                "threads": self.threads,
                "timeout_seconds": self.timeout_seconds,
            },
            "result_filename": self.result_zip.name,
            "input_sha256": self.input_sha256,
        }


def _ha_persistent_notification(title: str, message: str, notification_id: Optional[str]) -> None:
    if not SUPERVISOR_TOKEN:
        return
    url = f"{SUPERVISOR_CORE_API}/services/persistent_notification/create"
    payload: Dict[str, Any] = {"title": title, "message": message}
    if notification_id:
        payload["notification_id"] = notification_id
    data = json.dumps(payload).encode("utf-8")
    from urllib.request import Request, urlopen

    req = Request(
        url=url,
        data=data,
        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            _ = resp.read()
    except Exception:
        return


class Runner:
    def __init__(self, opts: Dict[str, Any]) -> None:
        self._opts = opts

        self.token = str(opts.get("token") or "")
        self.ingress_strict = bool(opts.get("ingress_strict", False))

        self.api_allow_cidrs = [str(c).strip() for c in (opts.get("api_allow_cidrs") or []) if isinstance(c, str) and str(c).strip()]
import re
        self.bind_host = str(opts.get("bind_host") or "0.0.0.0").strip() or "0.0.0.0"
        try:
            self.bind_port = int(opts.get("bind_port") or 8787)
        except Exception:
            self.bind_port = 8787
        if not (1 <= self.bind_port <= 65535):
            self.bind_port = 8787

        self.job_user = str(opts.get("job_user") or "jobrunner").strip() or "jobrunner"
        self._job_uid, self._job_gid = _resolve_user_ids(self.job_user)
        if self._job_uid is None or self._job_gid is None:
            print("WARNING: job_user not found; jobs will run as root", flush=True)

        self.timeout_seconds = int(opts.get("timeout_seconds") or 3600)
        self.max_upload_mb = int(opts.get("max_upload_mb") or 50)

        self.default_cpu = int(opts.get("default_cpu_percent") or 25)
        self.max_cpu = int(opts.get("max_cpu_percent") or 50)
        self.default_mem = int(opts.get("default_mem_mb") or 4096)
        self.max_mem = int(opts.get("max_mem_mb") or 4096)
        self.max_threads = int(opts.get("max_threads") or 1)

        self.cpu_limit_mode = str(opts.get("cpu_limit_mode") or "single_core").strip() or "single_core"

        self.max_concurrent_jobs = int(opts.get("max_concurrent_jobs") or 1)
        self.queue_max_jobs = int(opts.get("queue_max_jobs") or 10)

        self.tail_chars = int(opts.get("tail_chars") or 8000)
        self.retention_hours = int(opts.get("job_retention_hours") or 24)

        self.summary_head_chars = int(opts.get("summary_head_chars") or 4000)
        self.summary_tail_chars = int(opts.get("summary_tail_chars") or 4000)
        self.manifest_sha256 = bool(opts.get("manifest_sha256", False))

        self.notify_on_completion = bool(opts.get("notify_on_completion", True))
        self.notification_mode = str(opts.get("notification_mode") or "latest").strip() or "latest"
        self.notification_id_prefix = str(opts.get("notification_id_prefix") or "pythonista_job_runner").strip() or "pythonista_job_runner"
        self.notification_excerpt_chars = int(opts.get("notification_excerpt_chars") or 1200)

        self.safe_zip_limits = SafeZipLimits(
            max_members=int(opts.get("zip_max_members") or 2000),
            max_total_uncompressed=int(opts.get("zip_max_total_uncompressed") or (200 * 1024 * 1024)),
            max_single_uncompressed=int(opts.get("zip_max_single_uncompressed") or (50 * 1024 * 1024)),
        )

        self._lock = threading.Lock()
        self._jobs: Dict[str, Job] = {}
        self._job_order: List[str] = []
        self._procs: Dict[str, subprocess.Popen] = {}
        self._sema = threading.Semaphore(max(1, self.max_concurrent_jobs))

        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        self._load_jobs_from_disk()
        threading.Thread(target=self._reaper, daemon=True).start()

    def _build_job_env(self, threads: int) -> Dict[str, str]:
        """Build a minimal environment for user code (do not leak supervisor secrets)."""
        env: Dict[str, str] = {}
        for k in ("PATH", "LANG", "LC_ALL"):
            v = os.environ.get(k)
            if v:
                env[k] = v
        env["HOME"] = "/tmp"
        env["PYTHONUNBUFFERED"] = "1"

        # Thread caps for common numerical stacks
        t = str(int(threads) if int(threads) > 0 else 1)
        for k in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "NUMEXPR_MAX_THREADS",
            "VECLIB_MAXIMUM_THREADS",
            "BLIS_NUM_THREADS",
        ):
            env[k] = t

        # Optional, explicit allow-list from add-on options
        for k in self.allow_env:
            if k == "SUPERVISOR_TOKEN":
                continue
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        return env

    def _prepare_work_dir(self, work_dir: Path) -> None:
        """Best-effort: make work_dir writable by the job user."""
        uid, gid = self._job_uid, self._job_gid
        if uid is None or gid is None:
            return
        try:
            os.chown(str(work_dir), uid, gid)
            os.chmod(str(work_dir), 0o770)
        except Exception:
            pass
        try:
            for p in work_dir.rglob("*"):
                try:
                    if p.is_symlink():
                        continue
                    os.chown(str(p), uid, gid)
                    if p.is_dir():
                        os.chmod(str(p), 0o770)
                    else:
                        os.chmod(str(p), 0o660)
                except Exception:
                    continue
        except Exception:
            pass

    def stats_dict(self) -> Dict[str, Any]:
        with self._lock:
            states = [j.state for j in self._jobs.values()]
        jobs_total = len(states)
        jobs_running = sum(1 for s in states if s == "running")
        jobs_error = sum(1 for s in states if s == "error")
        jobs_done = sum(1 for s in states if s == "done")
        jobs_queued = sum(1 for s in states if s == "queued")

        try:
            du = shutil.disk_usage(str(JOBS_DIR))
            disk_free = int(du.free)
            disk_total = int(du.total)
        except Exception:
            disk_free = 0
            disk_total = 0

        jobs_bytes = 0
        try:
            for p in JOBS_DIR.rglob("*"):
                if p.is_file():
                    jobs_bytes += int(p.stat().st_size)
        except Exception:
            pass

        return {
            "runner_version": ADDON_VERSION,
            "jobs_total": jobs_total,
            "jobs_running": jobs_running,
            "jobs_done": jobs_done,
            "jobs_error": jobs_error,
            "jobs_queued": jobs_queued,
            "job_retention_hours": self.retention_hours,
            "jobs_dir_bytes": jobs_bytes,
            "disk_free_bytes": disk_free,
            "disk_total_bytes": disk_total,
        }

    def list_jobs(self) -> List[Job]:
        with self._lock:
            return [self._jobs[jid] for jid in self._job_order if jid in self._jobs]

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> Job:
        with self._lock:
            active = sum(1 for j in self._jobs.values() if j.state in ("queued", "running"))
        if active >= self.queue_max_jobs:
            raise RuntimeError("queue_full")

        cpu = clamp_int(headers.get("X-Runner-CPU-PCT"), self.default_cpu, 1, self.max_cpu)
        mem = clamp_int(headers.get("X-Runner-MEM-MB"), self.default_mem, 256, self.max_mem)
        thr = clamp_int(headers.get("X-Runner-THREADS"), self.max_threads, 1, self.max_threads)
        timeout = clamp_int(headers.get("X-Runner-TIMEOUT"), self.timeout_seconds, 1, self.timeout_seconds)

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        work_dir = job_dir / "work"
        job_dir.mkdir(parents=True, exist_ok=True)
        work_dir.mkdir(parents=True, exist_ok=True)

        safe_extract_zip_bytes(zip_bytes, work_dir, self.safe_zip_limits)
        self._prepare_work_dir(work_dir)

        run_py = work_dir / "run.py"
        if not run_py.exists():
            raise RuntimeError("zip_missing_run_py")

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        cpu_count = os.cpu_count() or 1
        mode = self.cpu_limit_mode
        if mode not in ("single_core", "total_machine"):
            mode = "single_core"
        eff = cpu
        if mode == "total_machine":
            eff = min(cpu * cpu_count, 100 * cpu_count)

        j = Job(
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
            tail_stdout=TailBuffer(self.tail_chars),
            tail_stderr=TailBuffer(self.tail_chars),
            client_ip=client_ip,
            input_sha256=hashlib_sha256_bytes(zip_bytes),
        )

        # Ingress user metadata
        if client_ip == INGRESS_PROXY_IP:
            j.submitted_by_id = headers.get("X-Remote-User-Id")
            j.submitted_by_name = headers.get("X-Remote-User-Name")
            j.submitted_by_display_name = headers.get("X-Remote-User-Display-Name")
            j.ingress_path = headers.get("X-Ingress-Path")

        with self._lock:
            self._jobs[job_id] = j
            self._job_order.insert(0, job_id)

        self._write_status(j)
        threading.Thread(target=self._run_job, args=(job_id,), daemon=True).start()
        return j

    def delete(self, job_id: str) -> bool:
        j = self.get(job_id)
        if not j:
            return False
        self.cancel(job_id)
        shutil.rmtree(j.job_dir, ignore_errors=True)
        with self._lock:
            self._jobs.pop(job_id, None)
            self._job_order = [x for x in self._job_order if x != job_id]
            self._procs.pop(job_id, None)
        return True

    def cancel(self, job_id: str) -> bool:
        j = self.get(job_id)
        if not j:
            return False
        j.cancel_requested = True

        with self._lock:
            p = self._procs.get(job_id)

        if p is not None and p.poll() is None:
            _kill_process_group(p, soft_seconds=2)
        return True

    def purge(self, states: List[str], older_than_hours: int, dry_run: bool) -> Dict[str, Any]:
        now = time.time()
        older_than_s = max(0, older_than_hours) * 3600
        to_delete: List[str] = []

        with self._lock:
            for job_id in list(self._job_order):
                j = self._jobs.get(job_id)
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
                _ = self.delete(job_id)
                deleted.append(job_id)
            except Exception:
                continue

        return {"ok": True, "deleted": deleted, "count": len(deleted), "dry_run": dry_run}

    def _write_status(self, j: Job) -> None:
        try:
            j.status_path.write_text(json.dumps(j.status_dict(), indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

    def _run_job(self, job_id: str) -> None:
        j = self.get(job_id)
        if not j:
            return

        j.state = "queued"
        j.phase = "queued"
        self._write_status(j)

        self._sema.acquire()
        try:
            if j.cancel_requested:
                j.state = "error"
                j.phase = "done"
                j.exit_code = 125
                j.error = "cancelled before start"
                j.started_utc = utc_now()
                j.finished_utc = utc_now()
                self._write_status(j)
                self._make_result_zip(j)
                self._notify_done(j)
                return

            j.state = "running"
            j.phase = "running"
            j.started_utc = utc_now()
            self._write_status(j)

            env = self._build_job_env(j.threads)

            job_uid = self._job_uid
            job_gid = self._job_gid

            def _preexec() -> None:
                try:
                    os.setsid()
                except Exception:
                    pass
                try:
                    os.nice(10)
                except Exception:
                    pass
                if resource is not None:
                    try:
                        mem_bytes = int(j.mem_mb) * 1024 * 1024
                        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
                    except Exception:
                        pass

                # Drop privileges for the user job (best-effort)
                try:
                    if job_gid is not None:
                        try:
                            os.setgroups([])
                        except Exception:
                            pass
                        os.setgid(int(job_gid))
                    if job_uid is not None:
                        os.setuid(int(job_uid))
                except Exception as e:
                    import sys
                    print(f"WARNING: Failed to drop privileges: {e}", file=sys.stderr)

            cmd = ["python3", "-u", str(j.work_dir / "run.py")]
            if shutil.which("cpulimit"):
                cmd = ["cpulimit", "-i", "-l", str(j.cpu_cpulimit_pct), "--"] + cmd

            rc = 1
            try:
                with open(j.stdout_path, "wb") as f_out, open(j.stderr_path, "wb") as f_err:
                    p = subprocess.Popen(
                        cmd,
                        cwd=str(j.work_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=env,
                        preexec_fn=_preexec,
                    )
                    with self._lock:
                        self._procs[j.job_id] = p

                    assert p.stdout is not None
                    assert p.stderr is not None

                    def pump(src, dst, tail: TailBuffer) -> None:
                        while True:
                            b = src.readline()
                            if not b:
                                break
                            dst.write(b)
                            dst.flush()
                            tail.append_bytes(b)

                    t1 = threading.Thread(target=pump, args=(p.stdout, f_out, j.tail_stdout), daemon=True)
                    t2 = threading.Thread(target=pump, args=(p.stderr, f_err, j.tail_stderr), daemon=True)
                    t1.start()
                    t2.start()

                    t0 = time.time()
                    while True:
                        if j.cancel_requested:
                            rc = 125
                            j.error = "cancelled"
                            _kill_process_group(p, soft_seconds=2)
                            break

                        if time.time() - t0 > j.timeout_seconds:
                            rc = 124
                            j.error = f"timeout after {j.timeout_seconds}s"
                            _kill_process_group(p, soft_seconds=2)
                            break

                        polled = p.poll()
                        if polled is not None:
                            rc = int(polled)
                            break

                        time.sleep(0.5)

                    t1.join(timeout=5)
                    t2.join(timeout=5)

            finally:
                with self._lock:
                    self._procs.pop(j.job_id, None)

            j.exit_code = rc
            j.finished_utc = utc_now()
            j.state = "done" if (rc == 0 and not j.error) else "error"
            if j.state == "error" and not j.error:
                j.error = f"job exited rc={rc}"
            j.phase = "done"
            self._write_status(j)

            self._make_result_zip(j)
            self._notify_done(j)

        except Exception as e:
            j.state = "error"
            j.phase = "error"
            j.finished_utc = utc_now()
            j.error = f"runner_error: {type(e).__name__}: {e}"
            self._write_status(j)
            try:
                self._make_result_zip(j)
            except Exception:
                pass
            self._notify_done(j)
        finally:
            try:
                self._sema.release()
            except Exception:
                pass

    def _notification_id(self, j: Job) -> Optional[str]:
        if not self.notify_on_completion:
            return None
        if self.notification_mode == "per_job":
            return f"{self.notification_id_prefix}_{j.job_id}"
        # default: overwrite latest
        return f"{self.notification_id_prefix}_latest"

    def _notify_done(self, j: Job) -> None:
        if not self.notify_on_completion:
            return
        title = "Pythonista Job Runner"
        who = j.submitted_by_display_name or j.submitted_by_name or "unknown user"
        if j.submitted_by_id:
            who = f"{who} ({j.submitted_by_id})"

        base = j.ingress_path or ""
        job_link = ""
        if base:
            job_link = f"\n\n[Open Web UI]({base}/?job={j.job_id})"

        excerpt = ""
        if self.notification_excerpt_chars > 0:
            if j.state == "error":
                ex = file_tail_text(j.stderr_path, self.notification_excerpt_chars)
                if not ex:
                    ex = file_tail_text(j.stdout_path, self.notification_excerpt_chars)
            else:
                ex = file_tail_text(j.stdout_path, self.notification_excerpt_chars)
            if ex:
                excerpt = "\n\n```text\n" + ex[-self.notification_excerpt_chars :] + "\n```"

        msg = (
            f"Job {j.job_id} finished.\n"
            f"State: {j.state}\n"
            f"Exit code: {j.exit_code}\n"
            f"Error: {j.error}\n"
            f"Duration (s): {j.duration_seconds()}\n"
            f"Submitted by: {who}"
            f"{job_link}"
            f"{excerpt}"
        )
        _ha_persistent_notification(title, msg, self._notification_id(j))

    def _iter_outputs(self, j: Job) -> Iterable[Path]:
        out_dir = j.work_dir / "outputs"
        if not out_dir.exists() or not out_dir.is_dir():
            return []
        return [p for p in out_dir.rglob("*") if p.is_file()]

    def _make_result_zip(self, j: Job) -> None:
        exit_code_text = (str(j.exit_code) if j.exit_code is not None else "").encode("utf-8")
        status_json = json.dumps(j.status_dict(), indent=2, sort_keys=True).encode("utf-8")

        manifest: Dict[str, Any] = {"job_id": j.job_id, "runner_version": ADDON_VERSION, "generated_utc": utc_now(), "outputs": []}

        total_bytes = 0
        files = list(self._iter_outputs(j))
        for p in files:
            rel = p.relative_to(j.work_dir).as_posix()
            size = int(p.stat().st_size)
            total_bytes += size
            entry: Dict[str, Any] = {"path": rel, "size": size}
            if self.manifest_sha256:
                try:
                    entry["sha256"] = sha256_file(p)
                except Exception:
                    entry["sha256"] = None
            manifest["outputs"].append(entry)

        manifest["outputs_total_files"] = len(files)
        manifest["outputs_total_bytes"] = total_bytes

        out_parts = read_head_tail_text(j.stdout_path, self.summary_head_chars, self.summary_tail_chars)
        err_parts = read_head_tail_text(j.stderr_path, self.summary_head_chars, self.summary_tail_chars)

        summary_lines = []
        summary_lines.append("Pythonista Job Runner summary")
        summary_lines.append(f"runner_version: {ADDON_VERSION}")
        summary_lines.append(f"job_id: {j.job_id}")
        summary_lines.append(f"created_utc: {j.created_utc}")
        summary_lines.append(f"started_utc: {j.started_utc}")
        summary_lines.append(f"finished_utc: {j.finished_utc}")
        summary_lines.append(f"state: {j.state}")
        summary_lines.append(f"phase: {j.phase}")
        summary_lines.append(f"exit_code: {j.exit_code}")
        summary_lines.append(f"error: {j.error}")
        summary_lines.append("")
        summary_lines.append("limits:")
        summary_lines.append(f"  cpu_percent: {j.cpu_percent}")
        summary_lines.append(f"  cpu_limit_mode: {j.cpu_limit_mode}")
        summary_lines.append(f"  cpu_count: {j.cpu_count}")
        summary_lines.append(f"  cpu_cpulimit_pct: {j.cpu_cpulimit_pct}")
        summary_lines.append(f"  mem_mb: {j.mem_mb}")
        summary_lines.append(f"  threads: {j.threads}")
        summary_lines.append(f"  timeout_seconds: {j.timeout_seconds}")
        summary_lines.append("")
        summary_lines.append(f"outputs_total_files: {manifest.get('outputs_total_files')}")
        summary_lines.append(f"outputs_total_bytes: {manifest.get('outputs_total_bytes')}")
        summary_lines.append("")
        summary_lines.append("stdout_head:")
        summary_lines.append(out_parts["head"])
        summary_lines.append("")
        summary_lines.append("stdout_tail:")
        summary_lines.append(out_parts["tail"])
        summary_lines.append("")
        summary_lines.append("stderr_head:")
        summary_lines.append(err_parts["head"])
        summary_lines.append("")
        summary_lines.append("stderr_tail:")
        summary_lines.append(err_parts["tail"])
        summary_lines.append("")

        summary_txt = "\n".join(summary_lines).encode("utf-8", errors="replace")
        manifest_json = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

        with zipfile.ZipFile(j.result_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            if j.stdout_path.exists():
                zf.write(j.stdout_path, "stdout.txt")
            if j.stderr_path.exists():
                zf.write(j.stderr_path, "stderr.txt")

            zf.writestr("status.json", status_json)
            zf.writestr("exit_code.txt", exit_code_text)
            zf.writestr("summary.txt", summary_txt)
            zf.writestr("result_manifest.json", manifest_json)

            job_log_lines = [
                f"job_id={j.job_id}",
                f"runner_version={ADDON_VERSION}",
                f"created_utc={j.created_utc}",
                f"started_utc={j.started_utc}",
                f"finished_utc={j.finished_utc}",
                f"state={j.state}",
                f"phase={j.phase}",
                f"exit_code={j.exit_code}",
                f"error={j.error}",
                f"cpu_percent={j.cpu_percent}",
                f"cpu_limit_mode={j.cpu_limit_mode}",
                f"cpu_count={j.cpu_count}",
                f"cpu_cpulimit_pct={j.cpu_cpulimit_pct}",
                f"mem_mb={j.mem_mb}",
                f"threads={j.threads}",
                f"timeout_seconds={j.timeout_seconds}",
                f"submitted_by_name={j.submitted_by_name}",
                f"submitted_by_display_name={j.submitted_by_display_name}",
                f"submitted_by_id={j.submitted_by_id}",
                f"client_ip={j.client_ip}",
                f"input_sha256={j.input_sha256}",
            ]
            zf.writestr("job.log", ("\n".join(job_log_lines) + "\n").encode("utf-8", errors="replace"))

            out_dir = j.work_dir / "outputs"
            if out_dir.exists() and out_dir.is_dir():
                for p in out_dir.rglob("*"):
                    if p.is_file():
                        rel = p.relative_to(j.work_dir).as_posix()
                        zf.write(p, rel)

    def _reaper(self) -> None:
        while True:
            try:
                cutoff = int(time.time()) - (int(self.retention_hours) * 3600)
                stale: List[str] = []
                with self._lock:
                    for jid, j in self._jobs.items():
                        if j.finished_utc:
                            finished = parse_utc(j.finished_utc) or time.time()
                            if int(finished) < cutoff:
                                stale.append(jid)
                for jid in stale:
                    j = self.get(jid)
                    if j:
                        shutil.rmtree(j.job_dir, ignore_errors=True)
                    with self._lock:
                        self._jobs.pop(jid, None)
                        self._job_order = [x for x in self._job_order if x != jid]
                        self._procs.pop(jid, None)
            except Exception:
                pass
            time.sleep(600)

    def _load_jobs_from_disk(self) -> None:
        """Rebuild job index from /data/jobs on startup."""
        items: List[Path] = []
        for p in JOBS_DIR.iterdir() if JOBS_DIR.exists() else []:
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

        items.sort(key=sort_key, reverse=True)

        with self._lock:
            self._jobs.clear()
            self._job_order.clear()

        for p in items:
            try:
                data = json.loads((p / "status.json").read_text(encoding="utf-8"))
            except Exception:
                continue

            job_id = str(data.get("job_id") or p.name)
            j = Job(job_id=job_id)

            j.created_utc = str(data.get("created_utc") or utc_now())
            j.started_utc = data.get("started_utc")
            j.finished_utc = data.get("finished_utc")
            j.state = str(data.get("state") or "error")
            j.phase = str(data.get("phase") or j.state)
            j.exit_code = data.get("exit_code")
            j.error = data.get("error")

            lim = data.get("limits") or {}
            j.cpu_percent = int(lim.get("cpu_percent") or self.default_cpu)
            j.cpu_limit_mode = str(lim.get("cpu_limit_mode") or self.cpu_limit_mode)
            j.cpu_count = int(lim.get("cpu_count") or (os.cpu_count() or 1))
            j.cpu_cpulimit_pct = int(lim.get("cpu_cpulimit_pct") or j.cpu_percent)
            j.mem_mb = int(lim.get("mem_mb") or self.default_mem)
            j.threads = int(lim.get("threads") or self.max_threads)
            j.timeout_seconds = int(lim.get("timeout_seconds") or self.timeout_seconds)

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

            # best-effort: pick newest result zip
            rzs = sorted(p.glob("result_*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)
            if rzs:
                j.result_zip = rzs[0]
            else:
                j.result_zip = p / "result.zip"

            j.tail_stdout = TailBuffer(self.tail_chars)
            j.tail_stderr = TailBuffer(self.tail_chars)
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

            with self._lock:
                self._jobs[j.job_id] = j
                self._job_order.insert(0, j.job_id)

        # rewrite status for normalisation
        with self._lock:
            jobs = list(self._jobs.values())
        for j in jobs:
            self._write_status(j)


def hashlib_sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _kill_process_group(p: subprocess.Popen, soft_seconds: int) -> None:
    try:
        pgid = os.getpgid(p.pid)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < float(soft_seconds):
        if p.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass

