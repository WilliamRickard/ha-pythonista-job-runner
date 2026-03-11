"""Integration and stress tests covering HTTP lifecycle endpoints."""

from __future__ import annotations

import http.client
import io
import json
import threading
import time
import zipfile

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
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, {k.lower(): v for (k, v) in resp.getheaders()}, data
    finally:
        conn.close()


def _await_state(host: str, port: int, token: str, job_id: str, wanted: set[str], timeout_s: float = 5.0) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, _hdrs, data = _request("GET", host, port, f"/job/{job_id}.json", None, {"X-Runner-Token": token})
        if status == 200:
            payload = json.loads(data.decode("utf-8"))
            if payload.get("state") in wanted:
                return payload
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for job {job_id} in states {wanted}")


def _make_runner_with_fake_worker(temp_data_dir, monkeypatch):
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    runner._is_root = False

    def _fake_worker(job_id: str) -> None:
        j = runner.get(job_id)
        if j is None:
            return
        j.state = "running"
        j.phase = "running"
        j.started_utc = runner_core.utc_now()
        runner._write_status(j)

        for idx in range(10):
            if j.cancel_requested:
                j.state = "error"
                j.phase = "done"
                j.exit_code = 130
                j.error = "cancelled"
                break
            j.stdout_path.parent.mkdir(parents=True, exist_ok=True)
            with j.stdout_path.open("a", encoding="utf-8") as f:
                f.write(f"out-{idx}\n")
            j.tail_stdout.append_bytes(f"out-{idx}\n".encode("utf-8"))
            with j.stderr_path.open("a", encoding="utf-8") as f:
                f.write(f"err-{idx}\n")
            j.tail_stderr.append_bytes(f"err-{idx}\n".encode("utf-8"))
            time.sleep(0.01)
        else:
            j.state = "done"
            j.phase = "done"
            j.exit_code = 0
            j.error = None

        j.finished_utc = runner_core.utc_now()

        if j.state == "done":
            with zipfile.ZipFile(j.result_zip, "w") as zf:
                zf.writestr("result.txt", "ok")

        runner._write_status(j)
        if j.delete_requested:
            runner._finalize_delete(job_id)

    monkeypatch.setattr(runner, "_run_job", _fake_worker)
    return runner


def test_http_lifecycle_submit_poll_logs_result_and_delete(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = _make_runner_with_fake_worker(temp_data_dir, monkeypatch)
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
        job_id = payload["job_id"]

        final = _await_state(host, port, "t", job_id, {"done"})
        assert final["exit_code"] == 0

        status, _hdrs, data = _request("GET", host, port, f"/tail/{job_id}.json?stdout_from=0&stderr_from=0&max_bytes=32", None, {"X-Runner-Token": "t"})
        assert status == 200
        tail_payload = json.loads(data.decode("utf-8"))
        assert "out-" in tail_payload["tail"]["stdout"]
        assert "err-" in tail_payload["tail"]["stderr"]

        status, hdrs, data = _request("GET", host, port, f"/stdout/{job_id}.txt?from=0&max_bytes=12", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert hdrs["x-from-offset"] == "0"
        assert int(hdrs["x-next-offset"]) >= 1
        assert b"out-" in data

        status, _hdrs, data = _request("GET", host, port, f"/result/{job_id}.zip", None, {"X-Runner-Token": "t"})
        assert status == 200
        zf = zipfile.ZipFile(io.BytesIO(data), "r")
        assert zf.read("result.txt") == b"ok"

        status, _hdrs, data = _request("DELETE", host, port, f"/job/{job_id}", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert json.loads(data.decode("utf-8")) == {"ok": True}

        status, _hdrs, data = _request("GET", host, port, f"/job/{job_id}.json", None, {"X-Runner-Token": "t"})
        assert status == 404
        assert json.loads(data.decode("utf-8"))["error"] == "unknown_job"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_lifecycle_cancel_and_failure_paths(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = _make_runner_with_fake_worker(temp_data_dir, monkeypatch)
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
        job_id = json.loads(data.decode("utf-8"))["job_id"]
        assert status == 202

        status, _hdrs, data = _request("POST", host, port, f"/cancel/{job_id}", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert json.loads(data.decode("utf-8")) == {"ok": True}

        final = _await_state(host, port, "t", job_id, {"error"})
        assert final["exit_code"] == 130
        assert final["error"] == "cancelled"

        status, _hdrs, data = _request("GET", host, port, f"/result/{job_id}.zip", None, {"X-Runner-Token": "t"})
        assert status == 404
        assert json.loads(data.decode("utf-8")) == {"error": "result_not_ready"}

        status, _hdrs, data = _request("POST", host, port, "/cancel/missing-job", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert json.loads(data.decode("utf-8")) == {"ok": False}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_stress_lifecycle_churn_and_concurrent_reads(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = _make_runner_with_fake_worker(temp_data_dir, monkeypatch)
    httpd, host, port = _start_server(runner)
    try:
        stop = threading.Event()
        read_errors: list[str] = []

        def _reader() -> None:
            while not stop.is_set():
                try:
                    status, _hdrs, data = _request("GET", host, port, "/jobs.json", None, {"X-Runner-Token": "t"})
                    if status != 200:
                        read_errors.append(f"jobs_status={status}")
                    else:
                        json.loads(data.decode("utf-8"))
                except Exception as exc:  # explicit failure capture for stress assertions
                    read_errors.append(type(exc).__name__)

        readers = [threading.Thread(target=_reader, daemon=True) for _ in range(4)]
        for t in readers:
            t.start()

        job_ids: list[str] = []
        for _ in range(20):
            status, _hdrs, data = _request(
                "POST",
                host,
                port,
                "/run",
                minimal_job_zip,
                {"X-Runner-Token": "t", "Content-Length": str(len(minimal_job_zip))},
            )
            assert status == 202
            job_id = json.loads(data.decode("utf-8"))["job_id"]
            job_ids.append(job_id)
            _request("POST", host, port, f"/cancel/{job_id}", None, {"X-Runner-Token": "t"})
            _await_state(host, port, "t", job_id, {"done", "error"}, timeout_s=8.0)
            status, _hdrs, _data = _request("DELETE", host, port, f"/job/{job_id}", None, {"X-Runner-Token": "t"})
            assert status == 200

        stop.set()
        for t in readers:
            t.join(timeout=2)

        assert not read_errors

        status, _hdrs, data = _request("GET", host, port, "/jobs.json", None, {"X-Runner-Token": "t"})
        assert status == 200
        assert json.loads(data.decode("utf-8")) == {"jobs": []}
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_audit_trail_captures_ingress_identity_and_actions(temp_data_dir, minimal_job_zip, monkeypatch):
    runner = _make_runner_with_fake_worker(temp_data_dir, monkeypatch)
    runner.ingress_proxy_ip = "127.0.0.1"
    httpd, host, port = _start_server(runner)
    headers = {
        "X-Runner-Token": "t",
        "Content-Length": str(len(minimal_job_zip)),
        "X-Remote-User-Id": "user-1",
        "X-Remote-User-Name": "alice",
        "X-Remote-User-Display-Name": "Alice A",
        "X-Ingress-Path": "/api/hassio_ingress/xyz",
    }
    try:
        status, _hdrs, data = _request("POST", host, port, "/run", minimal_job_zip, headers)
        assert status == 202
        job_id = json.loads(data.decode("utf-8"))["job_id"]

        _await_state(host, port, "t", job_id, {"done", "error"})

        status, _hdrs, _ = _request("POST", host, port, f"/cancel/{job_id}", None, {"X-Runner-Token": "t", "X-Remote-User-Display-Name": "Alice A"})
        assert status == 200

        status, _hdrs, _ = _request("GET", host, port, f"/result/{job_id}.zip", None, {"X-Runner-Token": "t", "X-Remote-User-Display-Name": "Alice A"})
        assert status in (200, 404)

        status, _hdrs, payload = _request("GET", host, port, f"/job/{job_id}.json", None, {"X-Runner-Token": "t"})
        assert status == 200
        job_payload = json.loads(payload.decode("utf-8"))
        status_data = job_payload.get("status", job_payload)
        events = status_data.get("audit_events", [])
        assert any(e.get("action") == "job_submit" for e in events)
        assert any(e.get("actor", {}).get("display_name") == "Alice A" for e in events)

        audit_log = temp_data_dir / "audit_events.jsonl"
        assert audit_log.exists()
        lines = [ln for ln in audit_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
        assert any("job_submit" in ln for ln in lines)
        assert not any("X-Runner-Token" in ln for ln in lines)
    finally:
        httpd.shutdown()
        httpd.server_close()
