"""Regression coverage for native HA functionality pass."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_and_platform_files_present() -> None:
    base = Path("custom_components/pythonista_job_runner")
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "0.3.0"
    for rel in ["number.py", "select.py", "text.py", "button.py", "update.py", "event.py", "notify.py", "intents.py"]:
        assert (base / rel).exists(), rel


def test_config_and_options_strings_include_new_fields() -> None:
    data = json.loads(Path("custom_components/pythonista_job_runner/translations/en.json").read_text(encoding="utf-8"))
    assert "reconfigure" in data["config"]["step"]
    for key in ["scan_interval", "notify_policy", "notify_target", "notify_throttle_seconds"]:
        assert key in data["options"]["step"]["init"]["data"]


def test_coordinator_and_backup_endpoints_added() -> None:
    coordinator = Path("custom_components/pythonista_job_runner/coordinator.py").read_text(encoding="utf-8")
    assert "EVENT_JOB_STARTED" in coordinator
    assert "EVENT_JOB_COMPLETED" in coordinator
    assert "EVENT_JOB_FAILED" in coordinator
    api = Path("pythonista_job_runner/app/http_api_server.py").read_text(encoding="utf-8")
    assert 'path == "/backup/pause"' in api
    assert 'path == "/backup/resume"' in api
    assert 'path == "/backup/status.json"' in api


def test_assist_sentences_and_notify_manager_present() -> None:
    intent_sentences = Path("custom_components/pythonista_job_runner/intents/en/pythonista_job_runner.yaml").read_text(encoding="utf-8")
    for intent_name in [
        "PythonistaRunnerJobsRunningIntent",
        "PythonistaRunnerQueueDepthIntent",
        "PythonistaRunnerRefreshIntent",
        "PythonistaRunnerPurgeDoneIntent",
    ]:
        assert intent_name in intent_sentences
    notifications = Path("custom_components/pythonista_job_runner/notifications.py").read_text(encoding="utf-8")
    assert "throttle_seconds" in notifications
    assert "persistent_notification" in notifications
