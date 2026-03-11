# Version: 0.6.13-tests-setup-flow.1
"""End-to-end tests for the guided setup HTTP flow."""

from __future__ import annotations

import http.client
import io
import json
import threading
import zipfile
from pathlib import Path

import socket

import http_api
import runner_core
from runner import package_profiles
from runner import package_store


def _start_server(runner: runner_core.Runner):
    """Start the HTTP server for one test runner."""
    httpd = http_api.RunnerHTTPServer(("127.0.0.1", 0), http_api.Handler)
    httpd.runner = runner
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    return httpd, host, int(port)


def _request(method: str, host: str, port: int, path: str, body: bytes | None, headers: dict[str, str]):
    """Send one request to the test server and return the response."""
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def _wheel_bytes() -> bytes:
    """Return a minimal valid wheel archive for upload tests."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("pjr_demo_formatsize/__init__.py", "__version__ = '0.1.0'\n")
        prefix = "pjr_demo_formatsize-0.1.0.dist-info"
        zf.writestr(f"{prefix}/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        zf.writestr(f"{prefix}/METADATA", "Metadata-Version: 2.1\nName: pjr-demo-formatsize\nVersion: 0.1.0\n")
        zf.writestr(f"{prefix}/RECORD", "pjr_demo_formatsize/__init__.py,,\n")
    return buf.getvalue()


def _profile_zip_bytes() -> bytes:
    """Return a minimal valid package profile archive for upload tests."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("demo_formatsize_profile/manifest.json", json.dumps({"display_name": "Demo formatsize"}))
        zf.writestr("demo_formatsize_profile/requirements.txt", "pjr_demo_formatsize==0.1.0\n")
        zf.writestr("demo_formatsize_profile/README.md", "demo profile\n")
    return buf.getvalue()


def _make_ready_venv(path: Path) -> None:
    """Create the minimal structure needed for a ready Linux venv."""
    (path / "bin").mkdir(parents=True, exist_ok=True)
    (path / "bin" / "python").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (path / "pyvenv.cfg").write_text("home = /usr/bin\n", encoding="utf-8")


def test_setup_http_flow_uploads_builds_and_deletes(temp_data_dir, monkeypatch):
    """The guided setup API should support upload, build, ready, and delete."""
    public_root = temp_data_dir / "config"
    public_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(package_store, "PUBLIC_CONFIG_ROOT", public_root)

    runner = runner_core.Runner(
        {
            "token": "t",
            "bind_host": "127.0.0.1",
            "bind_port": 0,
            "install_requirements": True,
            "dependency_mode": "profile",
            "package_profiles_enabled": True,
            "package_profile_default": "demo_formatsize_profile",
            "package_allow_public_wheelhouse": True,
            "package_offline_prefer_local": True,
            "max_upload_mb": 5,
        }
    )

    def _fake_run(cmd, **kwargs):
        stdout_path = Path(kwargs["stdout_path"])
        stderr_path = Path(kwargs["stderr_path"])
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text("ok\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        if cmd[:3] == ["python3", "-m", "venv"]:
            _make_ready_venv(Path(cmd[-1]))
        elif cmd[-2:] == ["pip", "inspect"] or cmd[-3:] == ["-m", "pip", "inspect"]:
            stdout_path.write_text('{"version":"1"}\n', encoding="utf-8")
        return {
            "cmd": list(cmd),
            "rc": 0,
            "exec_error": None,
            "duration_seconds": 0.01,
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }

    monkeypatch.setattr(package_profiles, "_run_command", _fake_run)

    httpd, host, port = _start_server(runner)
    try:
        status, _hdrs, data = _request("GET", host, port, "/setup/status.json", None, {"X-Runner-Token": "t"})
        assert status == 200
        payload = json.loads(data.decode("utf-8"))
        assert payload["ready_for_example_5"] is False
        assert payload["wheel_present"] is False
        assert payload["profile_present"] is False

        wheel = _wheel_bytes()
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/setup/upload-wheel",
            wheel,
            {
                "X-Runner-Token": "t",
                "X-Upload-Filename": "pjr_demo_formatsize-0.1.0-py3-none-any.whl",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(wheel)),
            },
        )
        assert status == 200
        wheel_payload = json.loads(data.decode("utf-8"))
        assert wheel_payload["status"] == "ok"
        assert wheel_payload["setup_status"]["wheel_present"] is True

        profile_zip = _profile_zip_bytes()
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/setup/upload-profile-zip",
            profile_zip,
            {
                "X-Runner-Token": "t",
                "X-Upload-Filename": "demo_formatsize_profile.zip",
                "Content-Type": "application/zip",
                "Content-Length": str(len(profile_zip)),
            },
        )
        assert status == 200
        profile_payload = json.loads(data.decode("utf-8"))
        assert profile_payload["status"] == "ok"
        assert profile_payload["profile_name"] == "demo_formatsize_profile"
        assert profile_payload["setup_status"]["profile_present"] is True
        assert profile_payload["setup_status"]["ready_state"] == "build_recommended"

        body = json.dumps({"profile": "demo_formatsize_profile"}).encode("utf-8")
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/package_profiles/build",
            body,
            {
                "X-Runner-Token": "t",
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        assert status == 200
        build_payload = json.loads(data.decode("utf-8"))
        assert build_payload["status"] == "ready"
        assert build_payload["setup_status"]["ready_for_example_5"] is True
        assert build_payload["setup_status"]["ready_state"] == "ready"

        delete_body = json.dumps({"profile": "demo_formatsize_profile"}).encode("utf-8")
        status, _hdrs, data = _request(
            "POST",
            host,
            port,
            "/setup/delete-profile",
            delete_body,
            {
                "X-Runner-Token": "t",
                "Content-Type": "application/json",
                "Content-Length": str(len(delete_body)),
            },
        )
        assert status == 200
        delete_payload = json.loads(data.decode("utf-8"))
        assert delete_payload["status"] == "ok"
        assert delete_payload["setup_status"]["profile_present"] is False
        assert delete_payload["setup_status"]["ready_for_example_5"] is False
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_setup_upload_profile_zip_rejects_missing_length(temp_data_dir, monkeypatch):
    """Profile uploads should reject requests that omit Content-Length."""
    public_root = temp_data_dir / "config"
    public_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(package_store, "PUBLIC_CONFIG_ROOT", public_root)
    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})

    httpd, host, port = _start_server(runner)
    try:
        raw_request = (
            f"POST /setup/upload-profile-zip HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "X-Runner-Token: t\r\n"
            "X-Upload-Filename: demo_formatsize_profile.zip\r\n"
            "Content-Type: application/zip\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8") + _profile_zip_bytes()

        sock = socket.create_connection((host, port), timeout=5)
        try:
            sock.sendall(raw_request)
            response = b""
            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                response += chunk
        finally:
            sock.close()

        assert b" 411 " in response.split(b"\r\n", 1)[0]
        assert b'length_required' in response
    finally:
        httpd.shutdown()
        httpd.server_close()
