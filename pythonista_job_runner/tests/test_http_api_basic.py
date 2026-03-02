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
