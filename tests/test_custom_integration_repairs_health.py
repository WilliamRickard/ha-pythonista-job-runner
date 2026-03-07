"""Static checks for repairs and system health implementation hooks."""

from __future__ import annotations

from pathlib import Path


def test_system_health_registers_info_callback() -> None:
    text = Path("custom_components/pythonista_job_runner/system_health.py").read_text(encoding="utf-8")
    assert "async_register_info(system_health_info)" in text


def test_repairs_create_issue_calls_present() -> None:
    text = Path("custom_components/pythonista_job_runner/repairs.py").read_text(encoding="utf-8")
    assert "async_create_issue" in text
    assert "ISSUE_UNREACHABLE" in text
    assert "ISSUE_AUTH" in text


def test_coordinator_emits_event_constants() -> None:
    text = Path("custom_components/pythonista_job_runner/coordinator.py").read_text(encoding="utf-8")
    assert "EVENT_JOB_UPDATED" in text
    assert "EVENT_JOB_FINISHED" in text


def test_services_include_operational_hooks() -> None:
    text = Path("custom_components/pythonista_job_runner/services.py").read_text(encoding="utf-8")
    assert "SERVICE_REFRESH" in text
    assert "SERVICE_CANCEL_JOB" in text
    assert "SERVICE_PURGE_DONE_JOBS" in text
    assert "SERVICE_PURGE_FAILED_JOBS" in text
