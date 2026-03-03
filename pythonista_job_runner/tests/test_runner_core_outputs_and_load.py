"""Regression tests for output packaging limits and job reload behaviour."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import runner_core


def _read_manifest(zpath: Path) -> dict:
    with zipfile.ZipFile(zpath, "r") as zf:
        data = zf.read("result_manifest.json").decode("utf-8")
    return json.loads(data)


def test_make_result_zip_respects_outputs_max_files(temp_data_dir):
    runner = runner_core.Runner(
        {
            "token": "t",
            "bind_host": "127.0.0.1",
            "bind_port": 0,
            "outputs_max_files": 2,
            "outputs_max_bytes": 0,
        }
    )

    job_id = "job1"
    job_dir = runner_core.JOBS_DIR / job_id
    work_dir = job_dir / "work"
    out_dir = work_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create three outputs; only two should be included.
    (out_dir / "a.txt").write_text("a", encoding="utf-8")
    (out_dir / "b.txt").write_text("b", encoding="utf-8")
    (out_dir / "c.txt").write_text("c", encoding="utf-8")

    stdout_path = job_dir / "stdout.txt"
    stderr_path = job_dir / "stderr.txt"
    stdout_path.write_text("", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")

    j = runner_core.Job(
        job_id=job_id,
        job_dir=job_dir,
        work_dir=work_dir,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        status_path=job_dir / "status.json",
        result_zip=job_dir / "result_test.zip",
    )

    runner._make_result_zip(j)

    man = _read_manifest(j.result_zip)
    assert man["outputs_total_files"] == 2
    assert man["outputs_truncated"] is True
    assert man["outputs_limit_reason"] == "max_files"
    paths = [e["path"] for e in man["outputs"]]
    assert paths == ["outputs/a.txt", "outputs/b.txt"]

    with zipfile.ZipFile(j.result_zip, "r") as zf:
        names = set(zf.namelist())
    assert "outputs/a.txt" in names
    assert "outputs/b.txt" in names
    assert "outputs/c.txt" not in names


def test_load_jobs_from_disk_uses_directory_name_as_job_id(temp_data_dir):
    # Create a job directory whose status.json claims a different job_id.
    job_dir = runner_core.JOBS_DIR / "dir_job"
    job_dir.mkdir(parents=True, exist_ok=True)
    status_path = job_dir / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "job_id": "different_id",
                "created_utc": runner_core.utc_now(),
                "state": "done",
                "phase": "done",
            }
        ),
        encoding="utf-8",
    )

    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    assert runner.get("dir_job") is not None
    assert runner.get("different_id") is None
