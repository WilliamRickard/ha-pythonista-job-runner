"""Integration tests for the reusable Pythonista client toolkit."""

from __future__ import annotations

import io
import threading
import time
import zipfile
from pathlib import Path

import pytest

import http_api
import runner_core
from pythonista_client import RunnerClient, RunnerClientError


def _start_server(runner: runner_core.Runner):
    httpd = http_api.RunnerHTTPServer(("127.0.0.1", 0), http_api.Handler)
    httpd.runner = runner

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    host, port = httpd.server_address
    return httpd, host, int(port)


def _zip_bytes(run_py: str = "print('ok')\n") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("run.py", run_py)
    return buf.getvalue()


def _runner_with_fake_worker() -> runner_core.Runner:
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    runner._is_root = False

    def _fake_worker(job_id: str) -> None:
        j = runner.get(job_id)
        if j is None:
            return
        j.state = "running"
        j.phase = "running"
        runner._write_status(j)

        time.sleep(0.05)
        if j.cancel_requested:
            j.state = "error"
            j.phase = "done"
            j.exit_code = 130
            j.error = "cancelled"
        else:
            j.state = "done"
            j.phase = "done"
            j.exit_code = 0
            with zipfile.ZipFile(j.result_zip, "w") as zf:
                zf.writestr("result.txt", "ok")

        runner._write_status(j)
        if j.delete_requested:
            runner._finalize_delete(job_id)

    runner._run_job = _fake_worker  # type: ignore[method-assign]
    return runner


def test_runner_client_run_zip_and_collect(temp_data_dir, tmp_path: Path):
    runner = _runner_with_fake_worker()
    httpd, host, port = _start_server(runner)
    try:
        base_url = f"http://{host}:{port}"
        client = RunnerClient(base_url, "t", poll_interval_seconds=0.01)

        job_zip = tmp_path / "job.zip"
        job_zip.write_bytes(_zip_bytes())

        result = client.run_zip_and_collect(
            job_zip,
            timeout_seconds=3,
            result_zip_path=tmp_path / "result.zip",
            extract_to=tmp_path / "result_files",
        )

        assert result.status["state"] == "done"
        assert result.result_zip_path.exists()
        assert (tmp_path / "result_files" / "result.txt").read_text(encoding="utf-8") == "ok"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_runner_client_surfaces_auth_error(temp_data_dir):
    runner = _runner_with_fake_worker()
    httpd, host, port = _start_server(runner)
    try:
        client = RunnerClient(f"http://{host}:{port}", "bad-token", poll_interval_seconds=0.01)
        with pytest.raises(RunnerClientError, match="http_error:401:unauthorised"):
            client.get_job("nope")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_runner_client_handles_cancelled_job_failure_path(temp_data_dir, tmp_path: Path):
    runner = _runner_with_fake_worker()
    httpd, host, port = _start_server(runner)
    try:
        client = RunnerClient(f"http://{host}:{port}", "t", poll_interval_seconds=0.01)
        submitted = client.submit_zip_bytes(_zip_bytes())
        assert client.cancel_job(submitted.job_id) is True

        status = client.wait_for_completion(submitted.job_id, timeout_seconds=3)
        assert status["state"] == "error"

        with pytest.raises(RunnerClientError, match="http_error:404:result_not_ready"):
            client.download_result_zip(submitted.job_id, tmp_path / "result.zip")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_runner_client_wait_for_completion_times_out() -> None:
    class _NeverDoneClient(RunnerClient):
        def get_job(self, job_id: str) -> dict[str, str]:
            _ = job_id
            return {"state": "running"}

    client = _NeverDoneClient("http://example", "t", poll_interval_seconds=0.0)
    with pytest.raises(RunnerClientError, match="timed_out_waiting_for_job"):
        client.wait_for_completion("job-1", timeout_seconds=0.0)


def test_runner_client_invalid_json_response_raises() -> None:
    class _BadJsonClient(RunnerClient):
        def _request_bytes(self, *args, **kwargs) -> bytes:  # type: ignore[override]
            _ = (args, kwargs)
            return b"not-json"

    client = _BadJsonClient("http://example", "t")
    with pytest.raises(RunnerClientError, match="invalid_json_response"):
        client.get_job("job-1")
