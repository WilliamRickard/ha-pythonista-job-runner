# Version: 0.6.13-tests-package-results.1
"""Tests for result zip package report inclusion."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

from runner import results as results_mod


def test_make_result_zip_includes_package_reports(tmp_path):
    job_dir = tmp_path / "job"
    work_dir = job_dir / "work"
    report_dir = tmp_path / "package_reports" / "job-1"
    out_dir = work_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.txt"
    stderr_path = job_dir / "stderr.txt"
    result_zip = job_dir / "result.zip"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text("ok\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    (out_dir / "hello.txt").write_text("hello\n", encoding="utf-8")
    (report_dir / "pip_install_report.json").write_text('{"install": true}\n', encoding="utf-8")
    (report_dir / "package_diagnostics.json").write_text('{"status": "ok"}\n', encoding="utf-8")

    job = SimpleNamespace(
        job_id="job-1",
        created_utc="2026-03-10T00:00:00Z",
        started_utc="2026-03-10T00:00:01Z",
        finished_utc="2026-03-10T00:00:02Z",
        state="done",
        phase="done",
        exit_code=0,
        error=None,
        cpu_percent=25,
        cpu_limit_mode="single_core",
        cpu_count=1,
        cpu_cpulimit_pct=25,
        mem_mb=1024,
        threads=1,
        timeout_seconds=60,
        submitted_by_name=None,
        submitted_by_display_name=None,
        submitted_by_id=None,
        client_ip=None,
        input_sha256=None,
        job_dir=job_dir,
        work_dir=work_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        result_zip=result_zip,
        package={
            "enabled": True,
            "mode": "per_job",
            "status": "ok",
            "cache_enabled": True,
            "cache_hit": False,
            "report_dir": str(report_dir),
        },
        status_dict=lambda: {"job_id": "job-1", "package": {"status": "ok"}},
    )
    runner = SimpleNamespace(
        addon_version="0.6.13",
        outputs_max_files=100,
        outputs_max_bytes=1000000,
        manifest_sha256=False,
        summary_head_chars=1000,
        summary_tail_chars=1000,
    )

    results_mod.make_result_zip(runner, job)

    with zipfile.ZipFile(result_zip, "r") as zf:
        names = set(zf.namelist())
        assert "package/pip_install_report.json" in names
        assert "package/package_diagnostics.json" in names
        manifest = json.loads(zf.read("result_manifest.json").decode("utf-8"))
        assert manifest["package"]["status"] == "ok"
