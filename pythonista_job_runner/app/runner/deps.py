# Version: 0.6.13-profile.2
"""Dependency installation support with persistent cache, wheelhouse reuse, and diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from utils import file_tail_text

from runner import package_envs
from runner import package_hashes
from runner import package_profiles
from runner import package_prune
from runner import package_store
from runner.fs_safe import safe_write_text_no_symlink
from runner.process import kill_process_group
from runner.redact import redact_pip_text


def _package_report_dir(runner: object, j: object) -> Path:
    """Return the per-job private package diagnostics directory."""
    job_id = str(getattr(j, "job_id", "unknown") or "unknown")
    paths = getattr(runner, "package_store_paths", None)
    if paths is not None:
        base_dir = Path(getattr(paths, "jobs_package_reports_dir"))
        report_dir = base_dir / job_id
    else:
        report_dir = Path(getattr(j, "work_dir")) / "_package_reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON to disk without following symlinks where possible."""
    safe_write_text_no_symlink(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _tail_redacted_text(path: Path, max_chars: int, redaction_urls: list[str]) -> str:
    """Return a redacted tail snippet from a text file."""
    return redact_pip_text(file_tail_text(path, max_chars) or "", redaction_urls)


def _read_redacted_text(path: Path, redaction_urls: list[str]) -> str:
    """Return the full redacted text from a path, best-effort."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return redact_pip_text(text, redaction_urls)


def _run_pip_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: Dict[str, str],
    preexec_fn: Any,
    stdout_path: Path,
    stderr_path: Path,
    timeout_s: int,
) -> tuple[Optional[int], Optional[str]]:
    """Run one pip command and capture stdout and stderr to files."""
    rc: Optional[int] = None
    try:
        with open(stdout_path, "wb") as f_out, open(stderr_path, "wb") as f_err:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=f_out,
                stderr=f_err,
                preexec_fn=preexec_fn,
            )
            try:
                rc = int(proc.wait(timeout=timeout_s))
            except subprocess.TimeoutExpired:
                kill_process_group(proc, soft_seconds=2)
                return (None, "timeout")
    except Exception as exc:
        return (None, f"exception:{type(exc).__name__}: {exc}")
    return (rc, None)


def _pip_preexec_factory(runner: object, job_uid: object, job_gid: object) -> Any:
    """Build the pre-exec hook used for pip subprocesses."""

    def _pip_preexec() -> None:
        try:
            os.setsid()
        except Exception:
            pass
        if not bool(getattr(runner, "_is_root", False)):
            return
        try:
            os.setgroups([])
        except Exception:
            pass
        os.setgid(int(job_gid))
        os.setuid(int(job_uid))

    return _pip_preexec


def _pip_base_install_command(
    req: Path,
    install_report_path: Path,
    *,
    python_executable: str = "python3",
    target_dir: Path | None = None,
) -> list[str]:
    """Return the base pip install command for one job or reusable venv."""
    cmd = [
        str(python_executable),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--report",
        str(install_report_path),
        "-r",
        str(req),
    ]
    if target_dir is not None:
        cmd += ["-t", str(target_dir)]
    return cmd


def _pip_inspect_command(*, python_executable: str = "python3", target_path: Path | None = None) -> list[str]:
    """Return the pip inspect command for the chosen package target."""
    cmd = [str(python_executable), "-m", "pip", "inspect"]
    if target_path is not None:
        cmd += ["--path", str(target_path)]
    return cmd


def _pip_index_options(runner: object) -> tuple[list[str], list[str]]:
    """Return pip index-related options and redaction candidates."""
    pip_index_url = str(getattr(runner, "pip_index_url", "") or "").strip()
    pip_extra_index_url = str(getattr(runner, "pip_extra_index_url", "") or "").strip()
    pip_trusted_hosts = list(getattr(runner, "pip_trusted_hosts", []) or [])

    opts: list[str] = []
    if pip_index_url:
        opts += ["--index-url", pip_index_url]
    if pip_extra_index_url:
        opts += ["--extra-index-url", pip_extra_index_url]
    for host in pip_trusted_hosts:
        opts += ["--trusted-host", str(host)]
    return (opts, [pip_index_url, pip_extra_index_url])


def _add_find_links(cmd: list[str], find_links_dirs: list[str]) -> list[str]:
    """Append pip --find-links options for each directory."""
    out = list(cmd)
    for link_dir in find_links_dirs:
        out += ["--find-links", str(link_dir)]
    return out


def _build_env_for_pip(runner: object, env: Dict[str, str], package_meta: Dict[str, Any]) -> Dict[str, str]:
    """Return the pip environment with persistent cache settings applied."""
    env_for_pip = dict(env)
    if bool(getattr(runner, "package_cache_enabled", True)):
        cache_dir = getattr(getattr(runner, "package_store_paths", None), "pip_cache_dir", None)
        if cache_dir is not None:
            env_for_pip["PIP_CACHE_DIR"] = str(cache_dir)
            package_meta["cache_dir"] = str(cache_dir)
    return env_for_pip


def _run_with_capture(
    cmd: list[str],
    *,
    cwd: Path,
    env_for_pip: Dict[str, str],
    preexec_fn: Any,
    stdout_path: Path,
    stderr_path: Path,
    timeout_s: int,
    redaction_urls: list[str],
) -> dict[str, Any]:
    """Run one pip command and return normalised capture details."""
    started = time.monotonic()
    rc, exec_error = _run_pip_command(
        cmd,
        cwd=cwd,
        env=env_for_pip,
        preexec_fn=preexec_fn,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_s=timeout_s,
    )
    duration = round(time.monotonic() - started, 3)
    stdout_text = _read_redacted_text(stdout_path, redaction_urls)
    stderr_text = _read_redacted_text(stderr_path, redaction_urls)
    return {
        "cmd": list(cmd),
        "rc": rc,
        "exec_error": exec_error,
        "duration": duration,
        "stdout_text": stdout_text,
        "stderr_text": stderr_text,
    }


def _result_to_status(result: dict[str, Any]) -> str:
    """Collapse a command result into a compact status string."""
    if result["exec_error"] == "timeout":
        return "timeout"
    if result["exec_error"] is not None:
        return "error"
    if result["rc"] == 0:
        return "ok"
    if result["rc"] is None:
        return "error"
    return f"rc_{int(result['rc'])}"


def _pip_failure_message(result: dict[str, Any], redaction_urls: list[str], stderr_path: Path, stdout_path: Path) -> str:
    """Build a compact user-facing error tail for a failed pip command."""
    exec_error = result["exec_error"]
    if exec_error == "timeout":
        tail = (_tail_redacted_text(stderr_path, 2000, redaction_urls) or _tail_redacted_text(stdout_path, 2000, redaction_urls)).strip()
        if len(tail) > 2000:
            tail = tail[-2000:]
        return f"pip_install_timeout: {tail}"
    if exec_error is not None:
        msg = redact_pip_text(str(exec_error), redaction_urls)
        return f"pip_install_failed: {msg}"
    rc = result["rc"]
    tail = (_tail_redacted_text(stderr_path, 2000, redaction_urls) or _tail_redacted_text(stdout_path, 2000, redaction_urls)).strip()
    if len(tail) > 2000:
        tail = tail[-2000:]
    return f"pip_install_rc_{int(rc)}: {tail}"


def _detect_cache_hit(stdout_text: str, stderr_text: str) -> bool:
    """Return whether pip output indicates cache reuse."""
    combined = (stdout_text + "\n" + stderr_text).lower()
    return "using cached" in combined


def _detect_wheelhouse_hit(stdout_text: str, stderr_text: str, find_links_dirs: list[str]) -> bool:
    """Return whether output suggests a local wheelhouse or vendor directory was used."""
    combined = stdout_text + "\n" + stderr_text
    if "Looking in links:" in combined:
        return True
    for link_dir in find_links_dirs:
        if str(link_dir) in combined:
            return True
    return False


def _enforce_lock_hashes(
    req: Path,
    *,
    package_meta: Dict[str, Any],
    diagnostics_path: Path,
) -> Optional[str]:
    """Validate hash-enforced lock files before invoking pip."""
    if req.name != "requirements.lock":
        package_meta["hash_enforcement"] = "disabled_no_lockfile"
        return None
    validation = package_hashes.validate_requirements_lock_hashes(req)
    package_meta["hash_enforcement"] = "required"
    package_meta["hash_validation"] = validation
    if validation.get("status") == "ok":
        return None
    package_meta["status"] = "error"
    package_meta["reason"] = "hash_validation_failed"
    _write_json(diagnostics_path, package_meta)
    first_issue = (validation.get("issues") or [{}])[0]
    line_no = first_issue.get("line")
    issue_text = str(first_issue.get("text") or "").strip()
    return f"hash_validation_failed: line {line_no}: {issue_text}".rstrip()


def _refresh_wheelhouse_summary(runner: object) -> dict[str, Any]:
    """Return current wheelhouse summary when package store paths are available."""
    paths = getattr(runner, "package_store_paths", None)
    required = (
        "wheelhouse_downloaded_dir",
        "wheelhouse_built_dir",
        "wheelhouse_imported_dir",
        "package_index_path",
        "storage_stats_path",
    )
    if paths is None or any(not hasattr(paths, name) for name in required):
        return {"downloaded_files": 0, "built_files": 0, "imported_files": 0, "total_files": 0, "total_bytes": 0}
    return package_store.refresh_package_index(paths)


def _prepare_wheelhouse(
    runner: object,
    *,
    req: Path,
    cwd: Path,
    env_for_pip: Dict[str, str],
    preexec_fn: Any,
    timeout_s: int,
    redaction_urls: list[str],
    find_links_dirs: list[str],
    report_dir: Path,
    package_meta: Dict[str, Any],
) -> None:
    """Best-effort populate the persistent wheelhouse after a successful install."""
    paths = getattr(runner, "package_store_paths", None)
    required = ("wheelhouse_downloaded_dir", "wheelhouse_built_dir")
    if paths is None or any(not hasattr(paths, name) for name in required):
        package_meta["prepare_download_status"] = "skipped_no_store"
        package_meta["prepare_wheel_status"] = "skipped_no_store"
        return

    index_opts, _ = _pip_index_options(runner)

    download_cmd = [
        "python3",
        "-m",
        "pip",
        "download",
        "--disable-pip-version-check",
        "--dest",
        str(paths.wheelhouse_downloaded_dir),
        "-r",
        str(req),
    ]
    download_cmd = _add_find_links(download_cmd, find_links_dirs)
    download_cmd += index_opts
    if bool(getattr(runner, "package_require_hashes", False)):
        download_cmd.append("--require-hashes")

    package_meta["prepare_download_command"] = redact_pip_text(" ".join(download_cmd), redaction_urls)
    download_result = _run_with_capture(
        download_cmd,
        cwd=cwd,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        stdout_path=report_dir / "pip_download_stdout.txt",
        stderr_path=report_dir / "pip_download_stderr.txt",
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
    )
    package_meta["prepare_download_status"] = _result_to_status(download_result)

    wheel_cmd = [
        "python3",
        "-m",
        "pip",
        "wheel",
        "--disable-pip-version-check",
        "--wheel-dir",
        str(paths.wheelhouse_built_dir),
        "-r",
        str(req),
    ]
    wheel_cmd = _add_find_links(wheel_cmd, find_links_dirs)
    wheel_cmd += index_opts
    if bool(getattr(runner, "package_require_hashes", False)):
        wheel_cmd.append("--require-hashes")

    package_meta["prepare_wheel_command"] = redact_pip_text(" ".join(wheel_cmd), redaction_urls)
    wheel_result = _run_with_capture(
        wheel_cmd,
        cwd=cwd,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        stdout_path=report_dir / "pip_wheel_stdout.txt",
        stderr_path=report_dir / "pip_wheel_stderr.txt",
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
    )
    package_meta["prepare_wheel_status"] = _result_to_status(wheel_result)
    wheelhouse_summary = _refresh_wheelhouse_summary(runner)
    package_meta["wheelhouse_downloaded_files"] = wheelhouse_summary.get("downloaded_files", 0)
    package_meta["wheelhouse_built_files"] = wheelhouse_summary.get("built_files", 0)
    package_meta["wheelhouse_imported_files"] = wheelhouse_summary.get("imported_files", 0)
    package_meta["wheelhouse_total_files"] = wheelhouse_summary.get("total_files", 0)



def _copy_install_failure_logs(work_dir: Path, install_result: dict[str, Any]) -> None:
    """Copy redacted install logs into the job work directory for easier debugging."""
    safe_write_text_no_symlink(work_dir / "pip_install_stdout.txt", install_result["stdout_text"])
    safe_write_text_no_symlink(work_dir / "pip_install_stderr.txt", install_result["stderr_text"])


def _run_install_flow(
    runner: object,
    *,
    req: Path,
    work_dir: Path,
    env_for_pip: Dict[str, str],
    preexec_fn: Any,
    timeout_s: int,
    redaction_urls: list[str],
    find_links_dirs: list[str],
    report_dir: Path,
    package_meta: Dict[str, Any],
    install_base: list[str],
    inspect_cmd: list[str],
    prepare_wheelhouse_on_success: bool,
) -> Optional[str]:
    """Run the pip install and inspect flow for one dependency target."""
    install_report_path = report_dir / "pip_install_report.json"
    inspect_report_path = report_dir / "pip_inspect_report.json"
    install_stdout_path = report_dir / "pip_install_stdout.txt"
    install_stderr_path = report_dir / "pip_install_stderr.txt"
    local_install_stdout_path = report_dir / "pip_install_local_stdout.txt"
    local_install_stderr_path = report_dir / "pip_install_local_stderr.txt"
    inspect_stdout_path = report_dir / "pip_inspect_stdout.txt"
    inspect_stderr_path = report_dir / "pip_inspect_stderr.txt"

    install_with_links = _add_find_links(install_base, find_links_dirs)
    if bool(getattr(runner, "package_require_hashes", False)):
        install_with_links.append("--require-hashes")

    index_opts, redaction_urls_from_indexes = _pip_index_options(runner)
    if redaction_urls_from_indexes:
        redaction_urls = list(dict.fromkeys(list(redaction_urls) + redaction_urls_from_indexes))

    install_result: dict[str, Any] | None = None
    used_stdout_path = install_stdout_path
    used_stderr_path = install_stderr_path

    if bool(getattr(runner, "package_offline_prefer_local", True)) and find_links_dirs:
        local_cmd = list(install_with_links) + ["--no-index"]
        package_meta["local_only_attempted"] = True
        package_meta["local_install_command"] = redact_pip_text(" ".join(local_cmd), redaction_urls)
        local_result = _run_with_capture(
            local_cmd,
            cwd=work_dir,
            env_for_pip=env_for_pip,
            preexec_fn=preexec_fn,
            stdout_path=local_install_stdout_path,
            stderr_path=local_install_stderr_path,
            timeout_s=timeout_s,
            redaction_urls=redaction_urls,
        )
        package_meta["local_only_status"] = _result_to_status(local_result)
        if local_result["rc"] == 0 and local_result["exec_error"] is None:
            install_result = local_result
            used_stdout_path = local_install_stdout_path
            used_stderr_path = local_install_stderr_path
            package_meta["install_command"] = package_meta["local_install_command"]
            package_meta["install_source"] = "local_wheelhouse"
            package_meta["wheelhouse_hit"] = True

    if install_result is None:
        remote_cmd = list(install_with_links) + index_opts
        package_meta["install_command"] = redact_pip_text(" ".join(remote_cmd), redaction_urls)
        install_result = _run_with_capture(
            remote_cmd,
            cwd=work_dir,
            env_for_pip=env_for_pip,
            preexec_fn=preexec_fn,
            stdout_path=install_stdout_path,
            stderr_path=install_stderr_path,
            timeout_s=timeout_s,
            redaction_urls=redaction_urls,
        )
        if package_meta.get("local_only_attempted"):
            package_meta["install_source"] = "local_then_remote"
        elif find_links_dirs:
            package_meta["install_source"] = "remote_with_find_links"
        else:
            package_meta["install_source"] = "remote_index"

    package_meta["install_report"] = str(install_report_path)
    package_meta["inspect_report"] = str(inspect_report_path)
    package_meta["install_duration_seconds"] = install_result["duration"]
    package_meta["cache_hit"] = _detect_cache_hit(install_result["stdout_text"], install_result["stderr_text"])
    if not package_meta.get("wheelhouse_hit"):
        package_meta["wheelhouse_hit"] = _detect_wheelhouse_hit(
            install_result["stdout_text"],
            install_result["stderr_text"],
            find_links_dirs,
        )

    if install_result["exec_error"] == "timeout":
        package_meta["status"] = "error"
        package_meta["reason"] = "pip_install_timeout"
        _copy_install_failure_logs(work_dir, install_result)
        return _pip_failure_message(install_result, redaction_urls, used_stderr_path, used_stdout_path)

    if install_result["exec_error"] is not None:
        package_meta["status"] = "error"
        package_meta["reason"] = "pip_install_failed"
        return _pip_failure_message(install_result, redaction_urls, used_stderr_path, used_stdout_path)

    if install_result["rc"] is None:
        package_meta["status"] = "error"
        package_meta["reason"] = "pip_install_failed"
        return "pip_install_failed: unknown"

    if int(install_result["rc"]) != 0:
        package_meta["status"] = "error"
        package_meta["reason"] = f"pip_install_rc_{int(install_result['rc'])}"
        _copy_install_failure_logs(work_dir, install_result)
        return _pip_failure_message(install_result, redaction_urls, used_stderr_path, used_stdout_path)

    if prepare_wheelhouse_on_success and package_meta.get("install_source") != "local_wheelhouse":
        _prepare_wheelhouse(
            runner,
            req=req,
            cwd=work_dir,
            env_for_pip=env_for_pip,
            preexec_fn=preexec_fn,
            timeout_s=timeout_s,
            redaction_urls=redaction_urls,
            find_links_dirs=find_links_dirs,
            report_dir=report_dir,
            package_meta=package_meta,
        )
    else:
        package_meta["prepare_download_status"] = "skipped_local_wheelhouse"
        package_meta["prepare_wheel_status"] = "skipped_local_wheelhouse"

    package_meta["inspect_command"] = redact_pip_text(" ".join(inspect_cmd), redaction_urls)
    inspect_result = _run_with_capture(
        inspect_cmd,
        cwd=work_dir,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        stdout_path=inspect_report_path,
        stderr_path=inspect_stderr_path,
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
    )
    package_meta["inspect_duration_seconds"] = inspect_result["duration"]

    inspect_stderr_text = inspect_result["stderr_text"]
    inspect_stdout_text = inspect_result["stdout_text"]
    if inspect_result["exec_error"] == "timeout":
        package_meta["inspect_status"] = "timeout"
        safe_write_text_no_symlink(inspect_stdout_path, inspect_stdout_text)
    elif inspect_result["exec_error"] is not None:
        package_meta["inspect_status"] = "error"
        safe_write_text_no_symlink(inspect_stdout_path, inspect_stdout_text)
    elif inspect_result["rc"] == 0:
        package_meta["inspect_status"] = "ok"
        try:
            inspect_stdout_path.unlink()
        except Exception:
            pass
    else:
        package_meta["inspect_status"] = f"rc_{int(inspect_result['rc'])}"
        safe_write_text_no_symlink(inspect_stdout_path, inspect_stdout_text)
    safe_write_text_no_symlink(inspect_stderr_path, inspect_stderr_text)

    package_meta["status"] = "ok"
    package_meta["reason"] = None
    return None


def _maybe_use_reusable_venv(
    runner: object,
    *,
    j: object,
    env: Dict[str, str],
    req: Path,
    work_dir: Path,
    report_dir: Path,
    package_meta: Dict[str, Any],
    env_for_pip: Dict[str, str],
    preexec_fn: Any,
    timeout_s: int,
    redaction_urls: list[str],
    find_links_dirs: list[str],
) -> tuple[bool, Optional[str]]:
    """Reuse or build a keyed venv when that mode is enabled."""
    if not bool(getattr(runner, "venv_reuse_enabled", False)):
        return (False, None)
    if str(getattr(runner, "dependency_mode", "per_job") or "per_job") != "per_job":
        return (False, None)

    paths = getattr(runner, "package_store_paths", None)
    if paths is None or not hasattr(paths, "venvs_root") or not hasattr(paths, "venv_index_path"):
        return (False, None)

    environment_key = package_envs.build_environment_key(runner, req)
    venv_path = package_envs.venv_dir(paths, environment_key)
    venv_python = package_envs.venv_python_path(venv_path)
    venv_site_packages = package_envs.venv_site_packages_path(venv_path)

    package_meta["environment_key"] = environment_key
    package_meta["venv_enabled"] = True
    package_meta["venv_reuse_enabled"] = True
    package_meta["venv_path"] = str(venv_path)
    package_meta["venv_python"] = str(venv_python)
    package_meta["venv_site_packages"] = str(venv_site_packages)
    package_meta["venv_max_count"] = int(getattr(runner, "venv_max_count", 0) or 0)
    package_meta["venv_reused"] = False
    package_meta["venv_action"] = "not_used"
    package_meta["venv_prune_status"] = "not_run"

    if package_envs.is_ready_venv(venv_path):
        package_envs.attach_venv_to_env(env, venv_path)
        record = package_envs.touch_last_used(paths, environment_key) or {}
        prune_keep_keys = [environment_key]
        active_keys_getter = getattr(runner, "active_package_environment_keys", None)
        if callable(active_keys_getter):
            try:
                prune_keep_keys.extend(active_keys_getter())
            except Exception:
                pass
        prune_result = package_envs.prune_venvs(paths, max_count=int(getattr(runner, "venv_max_count", 0) or 0), keep_keys=prune_keep_keys)
        package_meta["status"] = "ok"
        package_meta["reason"] = None
        package_meta["install_source"] = "reused_venv"
        package_meta["install_duration_seconds"] = 0
        package_meta["inspect_duration_seconds"] = 0
        package_meta["inspect_status"] = "reused_existing"
        package_meta["venv_reused"] = True
        package_meta["venv_action"] = "reused"
        package_meta["venv_record"] = record
        package_meta["venv_prune_status"] = str(prune_result.get("status") or "unknown")
        package_meta["venv_pruned_count"] = int(prune_result.get("removed", 0) or 0)
        package_meta["venv_count_after_prune"] = int(prune_result.get("kept", 0) or 0)
        return (True, None)

    staging_path = package_envs.staging_venv_dir(paths, environment_key)
    package_envs.prepare_staging_dir(staging_path)
    venv_create_stdout_path = report_dir / "venv_create_stdout.txt"
    venv_create_stderr_path = report_dir / "venv_create_stderr.txt"
    create_cmd = ["python3", "-m", "venv", str(staging_path)]
    package_meta["venv_create_command"] = " ".join(create_cmd)
    create_result = _run_with_capture(
        create_cmd,
        cwd=work_dir,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        stdout_path=venv_create_stdout_path,
        stderr_path=venv_create_stderr_path,
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
    )
    package_meta["venv_create_duration_seconds"] = create_result["duration"]
    package_meta["venv_create_status"] = _result_to_status(create_result)
    if create_result["exec_error"] is not None or create_result["rc"] not in (0, None) or not package_envs.is_ready_venv(staging_path):
        package_meta["venv_action"] = "fallback_per_job"
        package_meta["venv_status"] = "create_failed"
        package_meta["venv_reused"] = False
        package_meta["venv_create_error"] = _pip_failure_message(create_result, redaction_urls, venv_create_stderr_path, venv_create_stdout_path)
        package_envs.remove_tree(staging_path)
        return (False, None)

    staging_python = package_envs.venv_python_path(staging_path)
    install_base = _pip_base_install_command(req, report_dir / "pip_install_report.json", python_executable=str(staging_python), target_dir=None)
    inspect_cmd = _pip_inspect_command(python_executable=str(staging_python), target_path=None)
    err = _run_install_flow(
        runner,
        req=req,
        work_dir=work_dir,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
        find_links_dirs=find_links_dirs,
        report_dir=report_dir,
        package_meta=package_meta,
        install_base=install_base,
        inspect_cmd=inspect_cmd,
        prepare_wheelhouse_on_success=True,
    )
    if err is not None:
        package_meta["venv_action"] = "create_failed"
        package_meta["venv_status"] = "install_failed"
        package_envs.remove_tree(staging_path)
        return (True, err)

    if package_envs.is_ready_venv(venv_path):
        package_envs.remove_tree(staging_path)
    else:
        if venv_path.exists():
            package_envs.remove_tree(venv_path)
        staging_path.rename(venv_path)

    package_envs.attach_venv_to_env(env, venv_path)
    record = package_envs.upsert_venv_record(
        paths,
        environment_key=environment_key,
        venv_path=venv_path,
        requirements_path=req,
        install_source=str(package_meta.get("install_source") or "unknown"),
    )
    prune_keep_keys = [environment_key]
    active_keys_getter = getattr(runner, "active_package_environment_keys", None)
    if callable(active_keys_getter):
        try:
            prune_keep_keys.extend(active_keys_getter())
        except Exception:
            pass
    prune_result = package_envs.prune_venvs(paths, max_count=int(getattr(runner, "venv_max_count", 0) or 0), keep_keys=prune_keep_keys)
    package_meta["venv_action"] = "created"
    package_meta["venv_status"] = "ready"
    package_meta["venv_reused"] = False
    package_meta["venv_record"] = record
    package_meta["venv_prune_status"] = str(prune_result.get("status") or "unknown")
    package_meta["venv_pruned_count"] = int(prune_result.get("removed", 0) or 0)
    package_meta["venv_count_after_prune"] = int(prune_result.get("kept", 0) or 0)
    return (True, None)


def maybe_install_requirements(runner: object, j: object, env: Dict[str, str]) -> Optional[str]:
    """Optionally install requirements and attach either a venv or per-job package target."""
    package_meta: Dict[str, Any] = {
        "enabled": bool(getattr(runner, "install_requirements", False)),
        "mode": str(getattr(runner, "dependency_mode", "per_job") or "per_job"),
        "cache_enabled": bool(getattr(runner, "package_cache_enabled", True)),
        "cache_dir": "",
        "requirements_present": False,
        "profile_name": None,
        "profile_display_name": None,
        "profile_status": "not_used",
        "profile_attached": False,
        "profile_requirements_path": None,
        "profile_effective_requirements_path": None,
        "profile_diagnostics_bundle_path": None,
        "status": "skipped",
        "reason": None,
        "cache_hit": False,
        "wheelhouse_hit": False,
        "install_source": "",
        "install_duration_seconds": None,
        "inspect_duration_seconds": None,
        "install_report": None,
        "inspect_report": None,
        "report_dir": None,
        "install_command": None,
        "inspect_command": None,
        "inspect_status": "not_run",
        "find_links_dirs": [],
        "wheelhouse_available": False,
        "wheelhouse_downloaded_files": 0,
        "wheelhouse_built_files": 0,
        "wheelhouse_imported_files": 0,
        "wheelhouse_total_files": 0,
        "public_wheel_sync_status": "not_run",
        "public_wheel_imported_count": 0,
        "public_wheel_updated_count": 0,
        "public_wheel_unchanged_count": 0,
        "public_wheel_skipped_invalid_count": 0,
        "hash_enforcement": "not_checked",
        "hash_validation": None,
        "package_cache_prune_status": "not_run",
        "package_cache_pruned_count": 0,
        "package_cache_pruned_bytes": 0,
        "package_cache_private_bytes": None,
        "local_only_attempted": False,
        "local_only_status": "not_run",
        "local_install_command": None,
        "prepare_download_status": "not_run",
        "prepare_download_command": None,
        "prepare_wheel_status": "not_run",
        "prepare_wheel_command": None,
        "environment_key": None,
        "venv_enabled": False,
        "venv_reuse_enabled": bool(getattr(runner, "venv_reuse_enabled", False)),
        "venv_reused": False,
        "venv_action": "not_used",
        "venv_status": "not_run",
        "venv_path": None,
        "venv_python": None,
        "venv_site_packages": None,
        "venv_record": None,
        "venv_create_command": None,
        "venv_create_duration_seconds": None,
        "venv_create_status": "not_run",
        "venv_create_error": None,
        "venv_prune_status": "not_run",
        "venv_pruned_count": 0,
        "venv_count_after_prune": None,
        "venv_max_count": int(getattr(runner, "venv_max_count", 0) or 0),
    }
    setattr(j, "package", package_meta)

    if not bool(getattr(runner, "install_requirements", False)):
        package_meta["reason"] = "install_requirements_disabled"
        return None

    is_root = bool(getattr(runner, "_is_root", False))
    job_uid = getattr(runner, "_job_uid", None)
    job_gid = getattr(runner, "_job_gid", None)
    if is_root and (job_uid is None or job_gid is None):
        package_meta["status"] = "error"
        package_meta["reason"] = "pip_install_disabled_no_job_user"
        return "pip_install_disabled_no_job_user"

    work_dir = Path(getattr(j, "work_dir"))
    req = work_dir / "requirements.txt"

    report_dir = _package_report_dir(runner, j)
    package_meta["report_dir"] = str(report_dir)
    diagnostics_path = report_dir / "package_diagnostics.json"

    paths = getattr(runner, "package_store_paths", None)
    has_wheelhouse_paths = paths is not None and all(
        hasattr(paths, name)
        for name in (
            "wheelhouse_imported_dir",
            "wheelhouse_downloaded_dir",
            "wheelhouse_built_dir",
            "public_wheel_uploads_dir",
            "package_index_path",
            "storage_stats_path",
            "venvs_root",
            "venv_index_path",
        )
    )
    if has_wheelhouse_paths:
        if bool(getattr(runner, "package_allow_public_wheelhouse", True)):
            sync_result = package_store.sync_public_wheel_uploads(
                paths,
                max_import_bytes=package_store.public_wheel_import_max_bytes(getattr(runner, "package_cache_max_mb", 0)),
            )
            package_meta["public_wheel_sync_status"] = str(sync_result.get("status") or "unknown")
            package_meta["public_wheel_imported_count"] = int(sync_result.get("copied", 0) or 0)
            package_meta["public_wheel_updated_count"] = int(sync_result.get("updated", 0) or 0)
            package_meta["public_wheel_unchanged_count"] = int(sync_result.get("unchanged", 0) or 0)
            package_meta["public_wheel_skipped_invalid_count"] = int(sync_result.get("skipped_invalid", 0) or 0)
        wheelhouse_summary = _refresh_wheelhouse_summary(runner)
        package_meta["wheelhouse_downloaded_files"] = wheelhouse_summary.get("downloaded_files", 0)
        package_meta["wheelhouse_built_files"] = wheelhouse_summary.get("built_files", 0)
        package_meta["wheelhouse_imported_files"] = wheelhouse_summary.get("imported_files", 0)
        package_meta["wheelhouse_total_files"] = wheelhouse_summary.get("total_files", 0)

    find_links_dirs = package_store.find_links_dirs(paths, work_dir=work_dir) if has_wheelhouse_paths else []
    package_meta["find_links_dirs"] = list(find_links_dirs)
    package_meta["wheelhouse_available"] = bool(find_links_dirs)

    mode = str(getattr(runner, "dependency_mode", "per_job") or "per_job")
    if mode == "profile":
        package_meta["requirements_present"] = False
        err = package_profiles.attach_profile_for_job(runner, env, package_meta)
        _write_json(diagnostics_path, package_meta)
        return err

    package_meta["requirements_present"] = bool(req.exists() and req.is_file())
    if not req.exists() or not req.is_file():
        package_meta["reason"] = "requirements_txt_missing"
        _write_json(diagnostics_path, package_meta)
        return None

    if bool(getattr(runner, "package_require_hashes", False)):
        hash_err = _enforce_lock_hashes(req, package_meta=package_meta, diagnostics_path=diagnostics_path)
        if hash_err is not None:
            return hash_err

    env_for_pip = _build_env_for_pip(runner, env, package_meta)
    _index_opts, redaction_urls = _pip_index_options(runner)
    preexec_fn = _pip_preexec_factory(runner, job_uid, job_gid)
    timeout_s = max(10, int(getattr(runner, "pip_timeout_seconds", 120)))

    handled_by_venv, venv_err = _maybe_use_reusable_venv(
        runner,
        j=j,
        env=env,
        req=req,
        work_dir=work_dir,
        report_dir=report_dir,
        package_meta=package_meta,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
        find_links_dirs=find_links_dirs,
    )
    if handled_by_venv:
        cache_prune = package_prune.prune_package_store(runner, reason="post_install", keep_keys=[str(package_meta.get("environment_key") or "")])
        package_meta["package_cache_prune_status"] = str(cache_prune.get("status") or "unknown")
        package_meta["package_cache_pruned_count"] = int(cache_prune.get("removed", 0) or 0)
        package_meta["package_cache_pruned_bytes"] = int(cache_prune.get("removed_bytes", 0) or 0)
        storage = cache_prune.get("storage") if isinstance(cache_prune.get("storage"), dict) else {}
        package_meta["package_cache_private_bytes"] = storage.get("private_bytes")
        _write_json(diagnostics_path, package_meta)
        return venv_err

    deps_dir = work_dir / "_deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chown(str(deps_dir), int(job_uid), int(job_gid))
        os.chmod(str(deps_dir), 0o770)
    except Exception:
        pass

    install_base = _pip_base_install_command(req, report_dir / "pip_install_report.json", python_executable="python3", target_dir=deps_dir)
    inspect_cmd = _pip_inspect_command(python_executable="python3", target_path=deps_dir)
    err = _run_install_flow(
        runner,
        req=req,
        work_dir=work_dir,
        env_for_pip=env_for_pip,
        preexec_fn=preexec_fn,
        timeout_s=timeout_s,
        redaction_urls=redaction_urls,
        find_links_dirs=find_links_dirs,
        report_dir=report_dir,
        package_meta=package_meta,
        install_base=install_base,
        inspect_cmd=inspect_cmd,
        prepare_wheelhouse_on_success=True,
    )
    cache_prune = package_prune.prune_package_store(runner, reason="post_install", keep_keys=[str(package_meta.get("environment_key") or "")])
    package_meta["package_cache_prune_status"] = str(cache_prune.get("status") or "unknown")
    package_meta["package_cache_pruned_count"] = int(cache_prune.get("removed", 0) or 0)
    package_meta["package_cache_pruned_bytes"] = int(cache_prune.get("removed_bytes", 0) or 0)
    storage = cache_prune.get("storage") if isinstance(cache_prune.get("storage"), dict) else {}
    package_meta["package_cache_private_bytes"] = storage.get("private_bytes")
    _write_json(diagnostics_path, package_meta)
    if err is not None:
        return err

    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(deps_dir) + (os.pathsep + existing if existing else "")
    return None
