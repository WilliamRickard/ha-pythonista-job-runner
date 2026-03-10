# Version: 0.6.13-live-logs.2
"""Job execution helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from typing import Any
from pathlib import Path
from typing import Dict

from utils import TailBuffer, utc_now

from runner.fs_safe import safe_write_text_no_symlink
from runner.process import kill_process_group
from runner.store import JobStore

try:
    import resource
except ImportError:
    resource = None  # type: ignore[assignment]


def build_job_env(runner: object, threads: int) -> Dict[str, str]:
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
    for k in getattr(runner, "allow_env", []):
        if k == "SUPERVISOR_TOKEN":
            continue
        v = os.environ.get(k)
        if v is not None:
            env[k] = v
    return env


def prepare_work_dir(runner: object, work_dir: Path) -> None:
    """Best-effort: make work_dir writable by the job user."""
    uid, gid = getattr(runner, "_job_uid", None), getattr(runner, "_job_gid", None)
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


def _read_pipe_chunk(src: Any, chunk_size: int = 8192) -> bytes:
    """Read one available chunk from a subprocess pipe.

    `subprocess.Popen(..., stdout=PIPE)` exposes a buffered reader. Calling
    `read(8192)` on that object can wait for the full buffer or end-of-file,
    which makes the Web UI look like logs only arrive at the end of the job.
    Reading from the underlying file descriptor returns as soon as any bytes are
    available, which keeps stdout and stderr visibly live.
    """
    if chunk_size <= 0:
        chunk_size = 8192
    try:
        fileno = src.fileno()
    except Exception:
        fileno = None

    if fileno is not None:
        try:
            return os.read(fileno, chunk_size)
        except Exception:
            pass

    return src.read(chunk_size)


def run_job(runner: object, job_id: str) -> None:
    j = getattr(runner, "get")(job_id)
    if not j:
        return

    j.state = "queued"
    j.phase = "queued"
    getattr(runner, "_write_status")(j)

    sema = getattr(runner, "_sema")
    sema.acquire()
    try:
        if j.cancel_requested:
            j.state = "error"
            j.phase = "done"
            j.exit_code = 125
            j.error = "cancelled before start"
            j.started_utc = utc_now()
            j.finished_utc = utc_now()
            getattr(runner, "_write_status")(j)
            getattr(runner, "_make_result_zip")(j)
            getattr(runner, "_notify_done")(j)
            return

        j.state = "running"
        j.phase = "running"
        j.started_utc = utc_now()
        getattr(runner, "_write_status")(j)

        env = getattr(runner, "_build_job_env")(j.threads).copy()
        active_package_environment_key = None

        pip_err = getattr(runner, "_maybe_install_requirements")(j, env)
        if pip_err:
            j.state = "error"
            j.phase = "done"
            j.exit_code = 126
            j.error = pip_err
            j.finished_utc = utc_now()
            try:
                safe_write_text_no_symlink(j.stderr_path, "pip install failed\n" + pip_err + "\n")
            except Exception:
                pass
            getattr(runner, "_write_status")(j)
            getattr(runner, "_make_result_zip")(j)
            getattr(runner, "_notify_done")(j)
            return

        active_package_environment_key = str((getattr(j, "package", {}) or {}).get("environment_key") or "").strip() or None
        if active_package_environment_key:
            try:
                getattr(runner, "register_active_package_environment")(active_package_environment_key)
            except Exception:
                active_package_environment_key = None

        job_uid = getattr(runner, "_job_uid", None)
        job_gid = getattr(runner, "_job_gid", None)

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

            # Drop privileges for the user job. If running as root, fail closed on errors.
            if bool(getattr(runner, "_is_root", False)):
                if job_uid is None or job_gid is None:
                    raise RuntimeError("job_user_missing")
                try:
                    os.setgroups([])
                except Exception:
                    pass
                os.setgid(int(job_gid))
                os.setuid(int(job_uid))

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
                JobStore.for_runner(runner).set_proc(j.job_id, p)

                assert p.stdout is not None
                assert p.stderr is not None

                def pump(src: Any, dst: Any, tail: TailBuffer) -> None:
                    """Copy one process stream into the job artefacts and tail buffer."""
                    while True:
                        b = _read_pipe_chunk(src, 8192)
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
                        kill_process_group(p, soft_seconds=2)
                        break

                    if time.time() - t0 > j.timeout_seconds:
                        rc = 124
                        j.error = f"timeout after {j.timeout_seconds}s"
                        kill_process_group(p, soft_seconds=2)
                        break

                    polled = p.poll()
                    if polled is not None:
                        rc = int(polled)
                        break

                    time.sleep(0.5)

                t1.join(timeout=5)
                t2.join(timeout=5)

        finally:
            JobStore.for_runner(runner).pop_proc(j.job_id)

        j.exit_code = rc
        j.finished_utc = utc_now()
        j.state = "done" if (rc == 0 and not j.error) else "error"
        if j.state == "error" and not j.error:
            j.error = f"job exited rc={rc}"
        j.phase = "done"
        getattr(runner, "_write_status")(j)
        try:
            getattr(runner, "record_audit_event")(
                "job_complete",
                {"client_ip": j.client_ip, "via_ingress": bool(j.ingress_path), "user_id": j.submitted_by_id, "user_name": j.submitted_by_name, "display_name": j.submitted_by_display_name, "ingress_path": j.ingress_path},
                job_id=j.job_id,
                details={"state": j.state, "exit_code": j.exit_code},
                persist_status=True,
            )
        except Exception as e:
            print(f"WARNING: failed to record job_complete audit event for job {j.job_id}: {e}", flush=True)

        getattr(runner, "_make_result_zip")(j)
        getattr(runner, "_notify_done")(j)

    except Exception as e:
        j.state = "error"
        j.phase = "error"
        j.finished_utc = utc_now()
        j.error = f"runner_error: {type(e).__name__}: {e}"
        getattr(runner, "_write_status")(j)
        try:
            getattr(runner, "_make_result_zip")(j)
        except Exception:
            pass
        getattr(runner, "_notify_done")(j)
    finally:
        try:
            getattr(runner, "release_active_package_environment")(locals().get("active_package_environment_key"))
        except Exception:
            pass
        try:
            sema.release()
        except Exception:
            pass

        if getattr(j, "delete_requested", False):
            getattr(runner, "_finalize_delete")(j.job_id)
