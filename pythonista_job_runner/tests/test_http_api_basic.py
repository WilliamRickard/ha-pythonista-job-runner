"""Basic HTTP API behaviour tests.

These tests focus on auth and request/response codes. They avoid running real
jobs by stubbing Runner.new_job.
"""

from __future__ import annotations

import http.client
import json
import threading
from types import SimpleNamespace

import pytest

import http_api
import runner_core


def _start_server(runner: runner_core.Runner):
    httpd = http_api.RunnerHTTPServer(("127.0.0.1", 0), http_api.Handler)
    httpd.runner = runner

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    host, port = httpd.server_address
    return httpd, host, int(port)


def _request(method: str, host: str, port: int, path: str, body: bytes | None, headers: dict[str, str]):
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, resp.getheaders(), data
    finally:
        conn.close()


def test_health_is_public(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request("GET", host, port, "/health", None, {})
        assert status == 200
        payload = json.loads(data.decode("utf-8"))
        assert payload["status"] == "ok"
        assert payload["version"] == runner_core.ADDON_VERSION
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_jobs_requires_token(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, _data = _request("GET", host, port, "/jobs.json", None, {})
        assert status == 401

        status, _hdrs, data = _request("GET", host, port, "/jobs.json", None, {"X-Runner-Token": "t"})
        assert status == 200
        payload = json.loads(data.decode("utf-8"))
        assert payload == {"jobs": []}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_rejects_unauthorised(temp_data_dir, minimal_job_zip):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, _data = _request("POST", host, port, "/run", minimal_job_zip, {})
        assert status == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_accepts_valid_zip_without_executing_job(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    def _fake_new_job(zip_bytes, headers, client_ip):
        _ = (zip_bytes, headers, client_ip)
        return SimpleNamespace(job_id="job123")

    monkeypatch.setattr(runner, "new_job", _fake_new_job)

    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            minimal_job_zip,
            {"X-Runner-Token": "t", "Content-Length": str(len(minimal_job_zip))},
        )
        assert status == 202
        payload = json.loads(data.decode("utf-8"))
        assert payload["job_id"] == "job123"
        assert payload["tail_url"].endswith("/tail/job123.json")
        assert payload["result_url"].endswith("/result/job123.zip")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_rejects_oversize_upload(temp_data_dir, monkeypatch):
    # Set a small max_upload_mb and send a slightly larger payload.
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0, "max_upload_mb": 1})

    # Avoid doing anything real even if the handler reached new_job.
    monkeypatch.setattr(runner, "new_job", lambda *_args, **_kwargs: SimpleNamespace(job_id="x"))

    httpd, host, port = _start_server(runner)
    try:
        body = b"x" * (1024 * 1024 + 1)
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            body,
            {"X-Runner-Token": "t", "Content-Length": str(len(body))},
        )
        assert status == 413
        payload = json.loads(data.decode("utf-8"))
        assert payload.get("error") == "upload_too_large"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_stdout_rejects_multi_segment_job_id(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    # Seed a real job "b" with a stdout file, then request /stdout/a/b.txt which should be rejected.
    job_id = "b"
    job_dir = runner_core.JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = job_dir / "stdout.txt"
    stdout_path.write_text("ok\n", encoding="utf-8")

    j = runner_core.Job(job_id=job_id, job_dir=job_dir, stdout_path=stdout_path)
    with runner._lock:
        runner._jobs[job_id] = j
        runner._job_order.insert(0, job_id)

    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request("GET", host, port, "/stdout/a/b.txt", None, {"X-Runner-Token": "t"})
        assert status == 404
        payload = json.loads(data.decode("utf-8"))
        assert payload.get("error") == "unknown_job"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_stdout_supports_delta_query(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    job_id = "b"
    job_dir = runner_core.JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = job_dir / "stdout.txt"
    stdout_path.write_text("abcdef\n", encoding="utf-8")

    j = runner_core.Job(job_id=job_id, job_dir=job_dir, stdout_path=stdout_path)
    with runner._lock:
        runner._jobs[job_id] = j
        runner._job_order.insert(0, job_id)

    httpd, host, port = _start_server(runner)
    try:
        status, hdrs, data = _request("GET", host, port, "/stdout/b.txt?from=0&max_bytes=3", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert data == b"abc"
        hdr_map = {k.lower(): v for (k, v) in hdrs}
        assert hdr_map.get("x-from-offset") == "0"
        assert hdr_map.get("x-next-offset") == "3"
        assert hdr_map.get("x-file-size") == str(stdout_path.stat().st_size)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_info_is_public_but_stats_requires_auth(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request("GET", host, port, "/info.json", None, {})
        assert status == 200
        payload = json.loads(data.decode("utf-8"))
        assert payload["service"] == "pythonista_job_runner"

        status, _hdrs, data = _request("GET", host, port, "/stats.json", None, {})
        assert status == 401
        assert json.loads(data.decode("utf-8")) == {"error": "unauthorised"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_rejects_unsupported_content_type(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    monkeypatch.setattr(runner, "new_job", lambda *_args, **_kwargs: SimpleNamespace(job_id="x"))

    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            minimal_job_zip,
            {
                "X-Runner-Token": "t",
                "Content-Length": str(len(minimal_job_zip)),
                "Content-Type": "application/json",
            },
        )
        assert status == 415
        assert json.loads(data.decode("utf-8")) == {"error": "unsupported_content_type"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_rejects_invalid_content_length(temp_data_dir, minimal_job_zip):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            minimal_job_zip,
            {"X-Runner-Token": "t", "Content-Length": "not-an-int"},
        )
        assert status == 400
        assert json.loads(data.decode("utf-8")) == {"error": "bad_content_length"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_rejects_invalid_zip_error(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    runner._is_root = False
    bad_zip = b"not-a-zip"

    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            bad_zip,
            {
                "X-Runner-Token": "t",
                "Content-Length": str(len(bad_zip)),
                "Content-Type": "application/zip",
            },
        )
        assert status == 400
        assert json.loads(data.decode("utf-8")) == {"error": "invalid_zip"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_purge_rejects_unsupported_content_type(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    body = b"{}"
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/purge",
            body,
            {"X-Runner-Token": "t", "Content-Length": str(len(body)), "Content-Type": "text/plain"},
        )
        assert status == 415
        assert json.loads(data.decode("utf-8")) == {"error": "unsupported_content_type"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_purge_rejects_invalid_json(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    body = b"{"
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/purge",
            body,
            {"X-Runner-Token": "t", "Content-Length": str(len(body)), "Content-Type": "application/json"},
        )
        assert status == 400
        assert json.loads(data.decode("utf-8")) == {"error": "invalid_json"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_purge_rejects_non_object_json(temp_data_dir):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd, host, port = _start_server(runner)
    body = b"[]"
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/purge",
            body,
            {"X-Runner-Token": "t", "Content-Length": str(len(body)), "Content-Type": "application/json"},
        )
        assert status == 400
        assert json.loads(data.decode("utf-8")) == {"error": "invalid_json"}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_run_runtime_error_code_is_sanitized(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    def _bad(*_args, **_kwargs):
        raise RuntimeError("Bad runtime text with spaces")

    monkeypatch.setattr(runner, "new_job", _bad)
    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/run",
            minimal_job_zip,
            {"X-Runner-Token": "t", "Content-Length": str(len(minimal_job_zip))},
        )
        assert status == 400
        assert json.loads(data.decode("utf-8")) == {"error": "job_creation_failed"}
    finally:
        httpd.shutdown()
        httpd.server_close()
