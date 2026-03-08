# Version: 0.6.12-refactor.1
"""Dependency installation support (optional pip requirements.txt per job)."""

from __future__ import annotations

import os
import subprocess
from typing import Dict, Optional

from utils import file_tail_text

from runner.fs_safe import safe_write_text_no_symlink
from runner.process import kill_process_group
from runner.redact import redact_pip_text


def maybe_install_requirements(runner: object, j: object, env: Dict[str, str]) -> Optional[str]:
    """Optionally install requirements.txt into a per-job directory and set PYTHONPATH.

    Security: pip may execute build hooks. The install step is run as the unprivileged
    job user when the runner is running as root.

    Returns:
        None on success or if requirements.txt is absent.
        A short error string on failure.
    """
    # Access runner fields via attribute lookup to avoid importing runner_core.
    if not bool(getattr(runner, "install_requirements", False)):
        return None

    is_root = bool(getattr(runner, "_is_root", False))
    job_uid = getattr(runner, "_job_uid", None)
    job_gid = getattr(runner, "_job_gid", None)
    if is_root and (job_uid is None or job_gid is None):
        return "pip_install_disabled_no_job_user"

    work_dir = getattr(j, "work_dir")
    req = work_dir / "requirements.txt"
    if not req.exists() or not req.is_file():
        return None

    deps_dir = work_dir / "_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(str(deps_dir), int(job_uid), int(job_gid))
        os.chmod(str(deps_dir), 0o770)
    except Exception:
        pass

    cmd = [
        "python3",
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--no-cache-dir",
        "-r",
        str(req),
        "-t",
        str(deps_dir),
    ]

    pip_index_url = str(getattr(runner, "pip_index_url", "") or "").strip()
    pip_extra_index_url = str(getattr(runner, "pip_extra_index_url", "") or "").strip()
    pip_trusted_hosts = list(getattr(runner, "pip_trusted_hosts", []) or [])

    if pip_index_url:
        cmd += ["--index-url", pip_index_url]
    if pip_extra_index_url:
        cmd += ["--extra-index-url", pip_extra_index_url]
    for h in pip_trusted_hosts:
        cmd += ["--trusted-host", str(h)]

    redaction_urls = [pip_index_url, pip_extra_index_url]

    def _pip_preexec() -> None:
        try:
            os.setsid()
        except Exception:
            pass

        # If running as root, drop privileges for pip (pip may execute build hooks).
        if not bool(getattr(runner, "_is_root", False)):
            return
        try:
            os.setgroups([])
        except Exception:
            pass
        os.setgid(int(job_gid))
        os.setuid(int(job_uid))

    pip_stdout_tmp = work_dir / "pip_install_stdout.tmp"
    pip_stderr_tmp = work_dir / "pip_install_stderr.tmp"
    timeout_s = max(10, int(getattr(runner, "pip_timeout_seconds", 120)))

    rc: Optional[int] = None
    try:
        with open(pip_stdout_tmp, "wb") as f_out, open(pip_stderr_tmp, "wb") as f_err:
            p = subprocess.Popen(
                cmd,
                cwd=str(work_dir),
                env=env,
                stdout=f_out,
                stderr=f_err,
                preexec_fn=_pip_preexec,
            )
            try:
                rc = int(p.wait(timeout=timeout_s))
            except subprocess.TimeoutExpired:
                kill_process_group(p, soft_seconds=2)
                rc = None
    except Exception as e:
        msg = redact_pip_text(f"{type(e).__name__}: {e}", redaction_urls)
        return f"pip_install_failed: {msg}"

    def _pip_debug_tail(max_chars: int) -> tuple[str, str]:
        out_t = file_tail_text(pip_stdout_tmp, max_chars)
        err_t = file_tail_text(pip_stderr_tmp, max_chars)
        return (redact_pip_text(out_t or "", redaction_urls), redact_pip_text(err_t or "", redaction_urls))

    if rc is None:
        out_2k, err_2k = _pip_debug_tail(2000)
        try:
            out_20k, err_20k = _pip_debug_tail(20000)
            safe_write_text_no_symlink(work_dir / "pip_install_stdout.txt", out_20k)
            safe_write_text_no_symlink(work_dir / "pip_install_stderr.txt", err_20k)
        except Exception:
            pass
        tail = (err_2k or out_2k).strip()
        if len(tail) > 2000:
            tail = tail[-2000:]
        return f"pip_install_timeout: {tail}"

    if int(rc) != 0:
        out_2k, err_2k = _pip_debug_tail(2000)
        try:
            out_20k, err_20k = _pip_debug_tail(20000)
            safe_write_text_no_symlink(work_dir / "pip_install_stdout.txt", out_20k)
            safe_write_text_no_symlink(work_dir / "pip_install_stderr.txt", err_20k)
        except Exception:
            pass
        tail = (err_2k or out_2k).strip()
        if len(tail) > 2000:
            tail = tail[-2000:]
        return f"pip_install_rc_{int(rc)}: {tail}"

    # Success: remove temporary log files and prepend to PYTHONPATH so run.py can import installed dependencies.
    try:
        pip_stdout_tmp.unlink()
    except Exception:
        pass
    try:
        pip_stderr_tmp.unlink()
    except Exception:
        pass

    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(deps_dir) + (os.pathsep + existing if existing else "")
    return None
