"""Tests for support bundle and redaction behaviour."""

from __future__ import annotations

import json
from pathlib import Path

import runner_core
import support_bundle
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



def test_tail_jsonl_uses_streaming_reader_not_read_text(temp_data_dir, monkeypatch) -> None:
    runner = runner_core.Runner({"token": "abc"})
    rows = []
    for i in range(120):
        rows.append(json.dumps({"action": f"event_{i}", "token": "secret"}))
    runner.audit_log_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    def _forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("_tail_jsonl should not call Path.read_text")

    monkeypatch.setattr(Path, "read_text", _forbidden_read_text)

    payload = build_support_bundle(runner)
    assert len(payload["audit_recent"]) == 50
    assert payload["audit_recent"][0]["action"] == "event_70"
    assert payload["audit_recent"][-1]["action"] == "event_119"
    assert all(row.get("token") == "***REDACTED***" for row in payload["audit_recent"])


def test_support_bundle_queue_uses_single_snapshot(temp_data_dir):
    class _OneShotRunner:
        addon_version = "x"
        audit_log_path = Path("/tmp/nonexistent-audit.jsonl")

        def __init__(self):
            self._opts = {"token": "t"}
            self._calls = 0

        def list_jobs(self):
            self._calls += 1
            if self._calls > 1:
                raise AssertionError("list_jobs called more than once")
            return [
                runner_core.Job(job_id="j1", state="running"),
                runner_core.Job(job_id="j2", state="queued"),
                runner_core.Job(job_id="j3", state="error"),
            ]

        def stats_dict(self):
            return {"jobs_total": 3}

    payload = support_bundle.build_support_bundle(_OneShotRunner())
    assert payload["queue"] == {
        "jobs_total": 3,
        "jobs_running": 1,
        "jobs_queued": 1,
        "jobs_error": 1,
    }

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
        # Verify sensitive fields are redacted
        assert body.get("options", {}).get("token") == "***REDACTED***"
    finally:
        conn.close()
        httpd.shutdown()
        httpd.server_close()
