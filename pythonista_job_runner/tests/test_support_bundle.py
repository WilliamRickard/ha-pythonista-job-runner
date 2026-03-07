"""Tests for support bundle and redaction behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import runner_core
from support_bundle import build_support_bundle, redacted_options_summary


def test_redacted_options_summary_hides_secrets() -> None:
    src = {
        "token": "abc",
        "pip_index_url": "https://u:p@example.com/simple",
        "nested": {"api_key": "xyz", "safe": 1},
    }
    out = redacted_options_summary(src)
    assert out["token"] == "***REDACTED***"
    assert out["pip_index_url"] == "***REDACTED***"
    assert out["nested"]["api_key"] == "***REDACTED***"
    assert out["nested"]["safe"] == 1


def test_build_support_bundle_includes_expected_sections(temp_data_dir) -> None:
    runner = runner_core.Runner({"token": "abc", "telemetry_mqtt_enabled": True, "telemetry_topic_prefix": "runner/test"})
    runner.audit_log_path.write_text(json.dumps({"action": "job_submit", "token": "abc"}) + "\n", encoding="utf-8")
    payload = build_support_bundle(runner)
    assert "included" in payload
    assert "excluded" in payload
    assert payload["options"]["token"] == "***REDACTED***"
    assert payload["audit_recent"][0]["token"] == "***REDACTED***"


def test_support_bundle_endpoint(temp_data_dir):
    import http.client
    import threading
    import http_api

    runner = runner_core.Runner({"token": "t", "bind_host": "127.0.0.1", "bind_port": 0})
    httpd = http_api.RunnerHTTPServer(("127.0.0.1", 0), http_api.Handler)
    httpd.runner = runner
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    host, port = httpd.server_address
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request("GET", "/support_bundle.json", headers={"X-Runner-Token": "t"})
        resp = conn.getresponse()
        body = json.loads(resp.read().decode("utf-8"))
        assert resp.status == 200
        assert body["service"] == "pythonista_job_runner"
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
