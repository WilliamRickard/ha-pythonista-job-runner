"""Validation tests for custom integration baseline structure."""

from __future__ import annotations

import json
from pathlib import Path


def test_manifest_has_config_flow() -> None:
    manifest = json.loads(Path("custom_components/pythonista_job_runner/manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "pythonista_job_runner"
    assert manifest["config_flow"] is True


def test_required_files_exist() -> None:
    base = Path("custom_components/pythonista_job_runner")
    for rel in ["__init__.py", "config_flow.py", "const.py", "coordinator.py", "sensor.py", "system_health.py", "repairs.py"]:
        assert (base / rel).exists(), rel


def test_translations_include_issue_strings() -> None:
    data = json.loads(Path("custom_components/pythonista_job_runner/translations/en.json").read_text(encoding="utf-8"))
    assert "issues" in data
    assert "endpoint_unreachable" in data["issues"]
    assert "auth_failed" in data["issues"]
