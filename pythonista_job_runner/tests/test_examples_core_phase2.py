# Version: 0.6.13-tests-examples-core.2
"""Fast regression tests for the implemented Phase 2 core examples."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "pythonista_job_runner" / "examples" / "core"


def _copy_job_src(example_id: str, tmp_path: Path) -> Path:
    """Copy one example job source tree into a temporary working directory."""
    source_dir = EXAMPLES_ROOT / example_id / "job_src"
    work_dir = tmp_path / example_id
    shutil.copytree(source_dir, work_dir)
    return work_dir


def _run_example(work_dir: Path, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run `run.py` in a temporary working directory and capture output."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "run.py"],
        cwd=work_dir,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_live_logs_progress_writes_expected_outputs(tmp_path):
    """Example 02 should emit deterministic logs and summary files."""
    work_dir = _copy_job_src("02_live_logs_progress", tmp_path)
    result = _run_example(work_dir, {"PJR_EXAMPLE_SLEEP_SECONDS": "0.001"})

    assert result.returncode == 0
    assert "step 1/8: prepare workspace" in result.stdout
    assert "live-logs example finished" in result.stdout
    assert "warning at step 3" in result.stderr
    summary = json.loads((work_dir / "outputs" / "progress_summary.json").read_text(encoding="utf-8"))
    assert summary["step_count"] == 8
    timeline = (work_dir / "outputs" / "progress_timeline.txt").read_text(encoding="utf-8")
    assert "step 8/8: complete job" in timeline


def test_process_input_files_writes_reports(tmp_path):
    """Example 03 should transform bundled CSV input into multiple outputs."""
    work_dir = _copy_job_src("03_process_input_files", tmp_path)
    result = _run_example(work_dir)

    assert result.returncode == 0
    assert "Loaded 5 input rows" in result.stdout
    processed_csv = (work_dir / "outputs" / "processed.csv").read_text(encoding="utf-8")
    assert "sensor_c,83,high,19" in processed_csv
    stats = json.loads((work_dir / "outputs" / "stats.json").read_text(encoding="utf-8"))
    assert stats["reading_average"] == 64
    assert stats["band_counts"] == {"high": 1, "low": 2, "medium": 2}


def test_cancel_long_running_job_can_complete_when_not_cancelled(tmp_path):
    """Example 04 should still finish cleanly when cancellation is not triggered."""
    work_dir = _copy_job_src("04_cancel_long_running_job", tmp_path)
    result = _run_example(
        work_dir,
        {
            "PJR_CANCEL_TOTAL_HEARTBEATS": "3",
            "PJR_CANCEL_SLEEP_SECONDS": "0.001",
        },
    )

    assert result.returncode == 0
    assert "heartbeat 3/3: job still running" in result.stdout
    completed = json.loads((work_dir / "outputs" / "completed_summary.json").read_text(encoding="utf-8"))
    assert completed["status"] == "completed_without_cancellation"


def test_requirements_optional_fails_cleanly_when_dependency_missing(tmp_path):
    """Example 05 should write a clear failure payload when dependency install is absent."""
    work_dir = _copy_job_src("05_requirements_optional", tmp_path)
    result = _run_example(work_dir, {"PJR_FORCE_MISSING_DEPENDENCY": "1"})

    assert result.returncode != 0
    assert "Dependency `pjr_demo_formatsize` is not available." in result.stdout
    failure = json.loads((work_dir / "outputs" / "requirements_error.json").read_text(encoding="utf-8"))
    assert failure["status"] == "missing_dependency"
    assert failure["requirements_source"] == "local wheel"


def test_requirements_optional_succeeds_with_local_vendored_wheel(tmp_path):
    """Example 05 should succeed when its vendored local wheel has been installed."""
    work_dir = _copy_job_src("05_requirements_optional", tmp_path)
    deps_dir = work_dir / "_deps"
    deps_dir.mkdir()
    install_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-index",
            "-r",
            "requirements.txt",
            "-t",
            str(deps_dir),
        ],
        cwd=work_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install_result.returncode == 0, install_result.stderr
    env = {
        "PYTHONPATH": str(deps_dir),
    }
    result = _run_example(work_dir, env)

    assert result.returncode == 0
    status = json.loads((work_dir / "outputs" / "requirements_status.json").read_text(encoding="utf-8"))
    assert status["status"] == "ok"
    assert status["requirements_source"] == "local wheel"
    summary = (work_dir / "outputs" / "summary.md").read_text(encoding="utf-8")
    assert "camera_archive.zip" in summary
