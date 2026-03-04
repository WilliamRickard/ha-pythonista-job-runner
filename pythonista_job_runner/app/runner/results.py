# Version: 0.6.12-refactor.1
"""Result packaging and outputs collection."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List

from utils import read_head_tail_text, sha256_file, utc_now

from runner.fs_safe import safe_zip_write


def iter_outputs(_runner: object, j: object) -> Iterable[Path]:
    """Yield output file paths from <work_dir>/outputs deterministically."""
    work_dir = getattr(j, "work_dir")
    out_dir = work_dir / "outputs"
    if not out_dir.exists() or not out_dir.is_dir() or out_dir.is_symlink():
        return
    # Deterministic traversal to keep result zips stable across runs.
    for root, dirs, files in os.walk(str(out_dir)):
        dirs.sort()
        files.sort()
        for fn in files:
            p = Path(root) / fn
            try:
                if not p.is_file() or p.is_symlink():
                    continue
            except OSError:
                continue
            yield p


def make_result_zip(runner: object, j: object) -> None:
    """Create the result zip for a job."""
    addon_version = str(getattr(runner, "addon_version", ""))

    exit_code = getattr(j, "exit_code")
    exit_code_text = (str(exit_code) if exit_code is not None else "").encode("utf-8")
    status_json = json.dumps(getattr(j, "status_dict")(), indent=2, sort_keys=True).encode("utf-8")

    manifest: Dict[str, Any] = {
        "job_id": getattr(j, "job_id"),
        "runner_version": addon_version,
        "generated_utc": utc_now(),
        "outputs": [],
        "outputs_truncated": False,
        "outputs_limit_reason": None,
        "outputs_max_files": int(getattr(runner, "outputs_max_files", 0)),
        "outputs_max_bytes": int(getattr(runner, "outputs_max_bytes", 0)),
    }

    total_bytes = 0
    files: List[Path] = []

    max_files = int(getattr(runner, "outputs_max_files", 0))
    max_bytes = int(getattr(runner, "outputs_max_bytes", 0))

    for p_out in iter_outputs(runner, j):
        try:
            size = int(p_out.stat().st_size)
        except Exception:
            continue

        if max_files > 0 and len(files) >= max_files:
            manifest["outputs_truncated"] = True
            manifest["outputs_limit_reason"] = "max_files"
            break
        if max_bytes > 0 and (total_bytes + size) > max_bytes:
            manifest["outputs_truncated"] = True
            manifest["outputs_limit_reason"] = "max_bytes"
            break

        files.append(p_out)
        rel = p_out.relative_to(getattr(j, "work_dir")).as_posix()
        total_bytes += size
        entry: Dict[str, Any] = {"path": rel, "size": size}
        if bool(getattr(runner, "manifest_sha256", False)):
            try:
                entry["sha256"] = sha256_file(p_out)
            except Exception:
                entry["sha256"] = None
        manifest["outputs"].append(entry)

    manifest["outputs_total_files"] = len(files)
    manifest["outputs_total_bytes"] = total_bytes

    stdout_path = getattr(j, "stdout_path")
    stderr_path = getattr(j, "stderr_path")

    out_parts = read_head_tail_text(stdout_path, int(getattr(runner, "summary_head_chars", 0)), int(getattr(runner, "summary_tail_chars", 0)))
    err_parts = read_head_tail_text(stderr_path, int(getattr(runner, "summary_head_chars", 0)), int(getattr(runner, "summary_tail_chars", 0)))

    summary_lines: List[str] = []
    summary_lines.append("Pythonista Job Runner summary")
    summary_lines.append(f"runner_version: {addon_version}")
    summary_lines.append(f"job_id: {getattr(j, 'job_id')}")
    summary_lines.append(f"created_utc: {getattr(j, 'created_utc')}")
    summary_lines.append(f"started_utc: {getattr(j, 'started_utc')}")
    summary_lines.append(f"finished_utc: {getattr(j, 'finished_utc')}")
    summary_lines.append(f"state: {getattr(j, 'state')}")
    summary_lines.append(f"phase: {getattr(j, 'phase')}")
    summary_lines.append(f"exit_code: {getattr(j, 'exit_code')}")
    summary_lines.append(f"error: {getattr(j, 'error')}")
    summary_lines.append("")
    summary_lines.append("limits:")
    summary_lines.append(f"  cpu_percent: {getattr(j, 'cpu_percent')}")
    summary_lines.append(f"  cpu_limit_mode: {getattr(j, 'cpu_limit_mode')}")
    summary_lines.append(f"  cpu_count: {getattr(j, 'cpu_count')}")
    summary_lines.append(f"  cpu_cpulimit_pct: {getattr(j, 'cpu_cpulimit_pct')}")
    summary_lines.append(f"  mem_mb: {getattr(j, 'mem_mb')}")
    summary_lines.append(f"  threads: {getattr(j, 'threads')}")
    summary_lines.append(f"  timeout_seconds: {getattr(j, 'timeout_seconds')}")
    summary_lines.append("")
    summary_lines.append(f"outputs_total_files: {manifest.get('outputs_total_files')}")
    summary_lines.append(f"outputs_total_bytes: {manifest.get('outputs_total_bytes')}")
    summary_lines.append(f"outputs_truncated: {manifest.get('outputs_truncated')}")
    summary_lines.append(f"outputs_limit_reason: {manifest.get('outputs_limit_reason')}")
    summary_lines.append(f"outputs_max_files: {manifest.get('outputs_max_files')}")
    summary_lines.append(f"outputs_max_bytes: {manifest.get('outputs_max_bytes')}")
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

    job_dir = getattr(j, "job_dir")
    work_dir = getattr(j, "work_dir")
    result_zip = getattr(j, "result_zip")

    with zipfile.ZipFile(result_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        safe_zip_write(zf, stdout_path, "stdout.txt", job_dir)
        safe_zip_write(zf, stderr_path, "stderr.txt", job_dir)

        zf.writestr("status.json", status_json)
        zf.writestr("exit_code.txt", exit_code_text)
        zf.writestr("summary.txt", summary_txt)
        zf.writestr("result_manifest.json", manifest_json)

        for extra_name in ("pip_install_stdout.txt", "pip_install_stderr.txt"):
            p = work_dir / extra_name
            safe_zip_write(zf, p, extra_name, work_dir)

        job_log_lines = [
            f"job_id={getattr(j, 'job_id')}",
            f"runner_version={addon_version}",
            f"created_utc={getattr(j, 'created_utc')}",
            f"started_utc={getattr(j, 'started_utc')}",
            f"finished_utc={getattr(j, 'finished_utc')}",
            f"state={getattr(j, 'state')}",
            f"phase={getattr(j, 'phase')}",
            f"exit_code={getattr(j, 'exit_code')}",
            f"error={getattr(j, 'error')}",
            f"cpu_percent={getattr(j, 'cpu_percent')}",
            f"cpu_limit_mode={getattr(j, 'cpu_limit_mode')}",
            f"cpu_count={getattr(j, 'cpu_count')}",
            f"cpu_cpulimit_pct={getattr(j, 'cpu_cpulimit_pct')}",
            f"mem_mb={getattr(j, 'mem_mb')}",
            f"threads={getattr(j, 'threads')}",
            f"timeout_seconds={getattr(j, 'timeout_seconds')}",
            f"submitted_by_name={getattr(j, 'submitted_by_name')}",
            f"submitted_by_display_name={getattr(j, 'submitted_by_display_name')}",
            f"submitted_by_id={getattr(j, 'submitted_by_id')}",
            f"client_ip={getattr(j, 'client_ip')}",
            f"input_sha256={getattr(j, 'input_sha256')}",
        ]
        zf.writestr("job.log", ("\n".join(job_log_lines) + "\n").encode("utf-8", errors="replace"))

        out_dir = work_dir / "outputs"
        if out_dir.exists() and out_dir.is_dir() and not out_dir.is_symlink():
            for p_out in files:
                rel = p_out.relative_to(work_dir).as_posix()
                safe_zip_write(zf, p_out, rel, out_dir)
