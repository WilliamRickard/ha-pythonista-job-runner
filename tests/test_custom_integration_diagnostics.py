# Version: 0.3.0-tests-custom-integration-diagnostics.1
"""Static checks for diagnostics implementation and translations."""

from __future__ import annotations

import json
from pathlib import Path


def test_diagnostics_module_has_redaction() -> None:
    text = Path("custom_components/pythonista_job_runner/diagnostics.py").read_text(encoding="utf-8")
    assert "***REDACTED***" in text
    assert "async_get_config_entry_diagnostics" in text


def test_spanish_translation_exists_and_has_issues() -> None:
    data = json.loads(Path("custom_components/pythonista_job_runner/translations/es.json").read_text(encoding="utf-8"))
    assert "issues" in data
    assert "endpoint_unreachable" in data["issues"]


def test_diagnostics_include_package_payloads() -> None:
    text = Path("custom_components/pythonista_job_runner/diagnostics.py").read_text(encoding="utf-8")
    assert "package_summary" in text
    assert "package_cache" in text
    assert "package_profiles" in text
