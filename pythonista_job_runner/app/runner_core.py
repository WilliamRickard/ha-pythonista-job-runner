from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import resource  # type: ignore
except Exception:
    resource = None  # type: ignore[assignment]

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
    """
    Load the addon options file from OPTIONS_PATH and return its contents as a mapping.
    
    If the options file does not exist, contains invalid JSON, or the top-level JSON value is not an object, an empty dictionary is returned.
    
    Returns:
        dict: Parsed options from OPTIONS_PATH, or an empty dict if the file is missing, invalid JSON, or not a JSON object.
    """
    if not OPTIONS_PATH.exists():
        return {}
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


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
        """
        Compute the elapsed time of the job in seconds.
        
        Returns:
            int: Number of whole seconds between `started_utc` and `finished_utc`, or between `started_utc` and now if the job has not finished.
            None: If the job has not started (`started_utc` is not set).
        """
        if not self.started_utc:
            return None
        t0 = parse_utc(self.started_utc) or 0.0
        t1 = parse_utc(self.finished_utc) if self.finished_utc else time.time()
        if not t1:
            t1 = time.time()
        d = int(max(0.0, float(t1) - float(t0)))
        return d

    def status_dict(self) -> Dict[str, Any]:
        """
        Builds a serialisable dictionary representing the job's current status and metadata.
        
        Returns:
            status (dict): A mapping with the job's identifying timestamps and state, plus:
                - job_id, created_utc, started_utc, finished_utc
                - duration_seconds: elapsed seconds between start and finish (or now if running)
                - state, phase, exit_code, error
                - runner_version: runner release identifier
                - client_ip
                - submitted_by (dict): keys `id`, `name`, `display_name`
                - limits (dict): keys `cpu_percent`, `cpu_limit_mode`, `cpu_count`, `cpu_cpulimit_pct`, `mem_mb`, `threads`, `timeout_seconds`
                - result_filename: name of the produced result ZIP
                - input_sha256
        """
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
    """
    Send a Home Assistant persistent notification via the Supervisor API.
    
    Sends a persistent notification with the given title and message to the Supervisor persistent_notification service when a supervisor token is configured. If no supervisor token is available or the HTTP request fails, the function does nothing and returns silently.
    
    Parameters:
        title (str): Notification title.
        message (str): Notification body; may contain HTML for rendering.
        notification_id (Optional[str]): Optional identifier to reuse or replace an existing notification.
    """
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
        """
        Initialise the Runner with configuration options.
        
        Parameters:
            opts (Dict[str, Any]): Configuration mapping. Recognised keys:
                - token: Supervisor API token for notifications.
                - ingress_strict: If true, enforce ingress path validation.
                - timeout_seconds: Default job timeout in seconds.
                - max_upload_mb: Maximum upload size in megabytes for incoming ZIPs.
                - default_cpu_percent / max_cpu_percent: Default and maximum CPU percent allocation.
                - default_mem_mb / max_mem_mb: Default and maximum memory (MB) per job.
                - max_threads: Maximum allowed thread count for jobs.
                - cpu_limit_mode: CPU limiting mode, e.g. "single_core".
                - max_concurrent_jobs: Number of jobs allowed to run concurrently.
                - queue_max_jobs: Maximum queued jobs permitted.
                - tail_chars: Number of characters retained in in-memory tails for stdout/stderr.
                - job_retention_hours: Hours to keep finished job directories before reaping.
                - summary_head_chars / summary_tail_chars: Characters to include from job output in summaries.
                - manifest_sha256: Include SHA-256 digests for output files in result manifest when true.
                - notify_on_completion: Enable sending persistent notifications when jobs finish.
                - notification_mode: "per_job" or "latest" notification behaviour.
                - notification_id_prefix: Prefix used when constructing notification IDs.
                - notification_excerpt_chars: Number of characters of output included in notifications.
                - zip_max_members / zip_max_total_uncompressed / zip_max_single_uncompressed: Limits applied when extracting uploaded ZIPs.
        
        Initialisation side effects:
            - Creates the jobs directory if missing.
            - Loads any existing jobs from disk.
            - Starts the background reaper thread.
        """
        self._opts = opts

        self.token = str(opts.get("token") or "")
        self.ingress_strict = bool(opts.get("ingress_strict", False))

        # Normalize api_allow_cidrs to a list of non-empty strings
        raw_api_allow_cidrs = opts.get("api_allow_cidrs")
        api_allow_cidrs: List[str] = []
        if isinstance(raw_api_allow_cidrs, str):
            # Support comma-separated list in a single string
            api_allow_cidrs = [cidr.strip() for cidr in raw_api_allow_cidrs.split(",") if cidr.strip()]
        elif isinstance(raw_api_allow_cidrs, (list, tuple, set)):
            api_allow_cidrs = [str(cidr).strip() for cidr in raw_api_allow_cidrs if str(cidr).strip()]
        elif raw_api_allow_cidrs is None:
            api_allow_cidrs = []
        else:
            # Unexpected type; fall back to empty list to avoid errors
            api_allow_cidrs = []
        self.api_allow_cidrs = api_allow_cidrs
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

    def stats_dict(self) -> Dict[str, Any]:
        """
        Collect runtime and storage statistics for the runner and its jobs.
        
        Returns:
            stats (Dict[str, Any]): Mapping with the following keys:
                - `runner_version`: Runner addon version string.
                - `jobs_total`: Total number of tracked jobs.
                - `jobs_running`: Number of jobs currently in the `running` state.
                - `jobs_done`: Number of jobs in the `done` state.
                - `jobs_error`: Number of jobs in the `error` state.
                - `jobs_queued`: Number of jobs in the `queued` state.
                - `job_retention_hours`: Configured retention window in hours.
                - `jobs_dir_bytes`: Total size in bytes of files under the jobs directory (best-effort; 0 on error).
                - `disk_free_bytes`: Free bytes available on the filesystem containing the jobs directory (0 on error).
                - `disk_total_bytes`: Total bytes of the filesystem containing the jobs directory (0 on error).
        """
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
        """
        Return the stored jobs ordered most-recent-first.
        
        Returns:
            List[Job]: A list of Job objects with the most recently created/added job first.
        """
        with self._lock:
            return [self._jobs[jid] for jid in self._job_order if jid in self._jobs]

    def get(self, job_id: str) -> Optional[Job]:
        """
        Retrieve a job by its identifier.
        
        Returns:
            Job or None: `Job` if a job with the given id exists, `None` otherwise.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> Job:
        """
        Create and enqueue a new job from an uploaded ZIP archive.
        
        Parameters:
            zip_bytes (bytes): ZIP payload containing the job workspace; its SHA-256 is recorded.
            headers (Any): HTTP headers used to derive resource limits and, for ingress requests, submitter metadata.
            client_ip (str): Source IP of the submission; used to detect ingress proxy submissions.
        
        Returns:
            Job: The newly created Job object, persisted to disk and scheduled to run.
        
        Raises:
            RuntimeError: "queue_full" if the runner's queue capacity is exceeded.
            RuntimeError: "zip_missing_run_py" if the uploaded ZIP does not contain a top-level run.py.
        """
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

        run_py = work_dir / "run.py"
        if not run_py.exists():
            raise RuntimeError("zip_missing_run_py")

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

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
        """
        Delete a job and its on-disk data, cancelling it first if it is running.
        
        Parameters:
        	job_id (str): Identifier of the job to remove.
        
        Returns:
        	bool: `True` if the job was found and deleted, `False` if no job with the given id exists.
        """
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
        """
        Request cancellation of the job identified by `job_id` and, if it is running, attempt to terminate its process group.
        
        Parameters:
            job_id (str): Identifier of the job to cancel.
        
        Returns:
            bool: `True` if a job with `job_id` was found and cancellation was requested (termination attempted if running), `False` if no such job exists.
        """
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
        """
        Delete jobs that match the specified states and are older than the given age, optionally performing a dry run.
        
        Parameters:
            states (List[str]): Job state names to match (e.g. "done", "error"). An empty list matches all states.
            older_than_hours (int): Minimum age in hours for a job to be eligible for deletion; zero disables age filtering.
            dry_run (bool): If True, do not remove job data but return the list that would be deleted.
        
        Returns:
            result (Dict[str, Any]): Summary dictionary containing:
                - "ok": True if operation completed.
                - "deleted": list of job IDs deleted (or that would be deleted on dry run).
                - "count": number of entries in "deleted".
                - "dry_run": the input dry_run flag.
        """
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
        """
        Persist the job's current status to the job's status file on disk.
        
        Parameters:
            j (Job): Job whose status will be written to its `status_path`. IO or serialization errors are ignored.
        """
        try:
            j.status_path.write_text(json.dumps(j.status_dict(), indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

    def _run_job(self, job_id: str) -> None:
        """
        Execute the full lifecycle of the job identified by `job_id`: start the worker, enforce resource limits and timeouts, stream stdout/stderr to disk and in-memory tails, handle cancellation, record final status, produce the result ZIP and send completion notification.
        
        Parameters:
            job_id (str): Identifier of the job to run; if the job does not exist the method returns immediately.
        """
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

            env = os.environ.copy()
            t = str(j.threads)
            for k in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_MAX_THREADS",
                "VECLIB_MAXIMUM_THREADS",
                "BLIS_NUM_THREADS",
            ):
                env[k] = t

            def _preexec() -> None:
                """
                Prepare the child process environment before execution.
                
                When invoked in the child (pre-exec), this sets a new session id, lowers process priority, and — if the platform resource module is available — applies an address-space (virtual memory) limit based on the job's `mem_mb` value.
                """
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
                        """
                        Copy lines from a readable stream to a writable stream and record them in a TailBuffer.
                        
                        Reads from `src` until end-of-file, writing each line to `dst`, flushing after each write, and appending the raw bytes to `tail`.
                        
                        Parameters:
                            src: A file-like object supporting `readline()` that yields bytes or text lines.
                            dst: A writable file-like object to receive the copied lines; `write()` and `flush()` are used.
                            tail (TailBuffer): Buffer that stores the most recent bytes written for quick access.
                        """
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
        """
        Compute the persistent notification identifier to use for a finished job.
        
        Parameters:
            j (Job): The job for which to generate the notification identifier.
        
        Returns:
            Optional[str]: `None` if notifications are disabled; otherwise a string.
            For `"per_job"` mode returns `"<prefix>_<job_id>"`, otherwise returns `"<prefix>_latest"`.
        """
        if not self.notify_on_completion:
            return None
        if self.notification_mode == "per_job":
            return f"{self.notification_id_prefix}_{j.job_id}"
        # default: overwrite latest
        return f"{self.notification_id_prefix}_latest"

    def _notify_done(self, j: Job) -> None:
        """
        Send a Home Assistant persistent notification summarising a finished job if notifications are enabled.
        
        The notification includes the job ID, final state, exit code, error message (if any), duration, and submitter information. If the job has an ingress path a link to the web UI for that job is included. If an excerpt length is configured, a tail excerpt from the job's stdout (or stderr for error states) is appended and truncated to the configured size.
        
        Parameters:
            j (Job): The job whose completion should be notified.
        """
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
        """
        Yield all regular files contained in a job's outputs directory, searched recursively.
        
        Parameters:
            j (Job): The job whose work directory will be searched for an 'outputs' subdirectory.
        
        Returns:
            files (Iterable[Path]): An iterable of file paths found under `j.work_dir / "outputs"`. Returns an empty iterable if the directory does not exist or contains no files.
        """
        out_dir = j.work_dir / "outputs"
        if not out_dir.exists() or not out_dir.is_dir():
            return []
        return [p for p in out_dir.rglob("*") if p.is_file()]

    def _make_result_zip(self, j: Job) -> None:
        """
        Create the job result ZIP file for the given job.
        
        The ZIP at j.result_zip will contain the job's status.json, exit_code.txt, summary.txt, result_manifest.json, job.log, stdout.txt and stderr.txt (if present), and any files under the job's work/outputs directory preserved with their relative paths. The manifest records job metadata, a listing of output files with sizes (and SHA-256 digests if the runner's manifest SHA-256 option is enabled), and totals for files and bytes. The summary text includes a brief job overview, configured limits and truncated head/tail excerpts of stdout and stderr.
        
        Parameters:
            j (Job): The job whose artifacts and metadata will be packaged into the result ZIP at j.result_zip.
        """
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
        """
        Periodically removes completed jobs that are older than the configured retention window.
        
        Calculates a cutoff time from self.retention_hours, finds jobs with a finished timestamp older than
        that cutoff, deletes their job directory from disk, and removes their entries from the runner's
        in-memory indexes (job list, job order and process map). Runs indefinitely, sleeping for 600
        seconds between iterations and ignoring any errors encountered during cleanup.
        """
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
        """
        Reconstruct the in-memory job index from the on-disk job directories in /data/jobs.
        
        Scans each subdirectory that contains a status.json, loads and normalises its data into a Job object, seeds stdout/stderr tail buffers from existing log files, and populates the runner's internal job map and ordering under the instance lock. Any job in a non-final state ("queued" or "running") is marked as an error with a default exit code of 125 and a restart message. After loading, each job's status.json is rewritten to ensure a consistent, normalised on-disk representation.
        
        No return value.
        """
        items: List[Path] = []
        for p in JOBS_DIR.iterdir() if JOBS_DIR.exists() else []:
            if not p.is_dir():
                continue
            status_path = p / "status.json"
            if not status_path.exists():
                continue
            items.append(p)

        def sort_key(p: Path) -> float:
            """
            Determine a numeric sort key for a job directory based on its creation time.
            
            Parameters:
                p (Path): Path to a job directory expected to contain a `status.json`.
            
            Returns:
                float: Unix timestamp in seconds derived from `created_utc` in `status.json` if present and parseable; otherwise the file-system modification time of the path; if neither is available, `0.0`.
            """
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
    """
    Compute the SHA-256 hexadecimal digest of the given bytes.
    
    Parameters:
        b (bytes): Input data to hash.
    
    Returns:
        hex_digest (str): Lowercase hexadecimal SHA-256 digest of `b`.
    """
    import hashlib
    return hashlib.sha256(b).hexdigest()


def _kill_process_group(p: subprocess.Popen, soft_seconds: int) -> None:
    """
    Terminate a process group gracefully, escalating to a forceful kill after a grace period.
    
    Attempts to obtain the process group for the provided subprocess and sends SIGTERM to that group.
    Waits up to `soft_seconds` for the process to exit, polling periodically; if the process remains
    running after the grace period, sends SIGKILL to the group. If the process group cannot be
    determined, attempts to terminate the single process. All errors during termination are ignored.
    
    Parameters:
        p (subprocess.Popen): The child process whose process group should be terminated.
        soft_seconds (int): Number of seconds to wait after sending SIGTERM before sending SIGKILL.
    """
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

