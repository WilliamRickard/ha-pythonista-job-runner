# Version: 0.3.0-tests-custom-integration-runtime-guards.1
"""Targeted runtime and guardrail tests for Step 6 custom integration fixes."""

from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import sys


def _load_client_module():
    module_path = Path("custom_components/pythonista_job_runner/client.py")
    spec = importlib.util.spec_from_file_location("_step6_client_module", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps({"ok": True}).encode("utf-8")


def test_verify_ssl_true_uses_default_context(monkeypatch) -> None:
    client_mod = _load_client_module()
    captured: dict[str, object] = {}
    default_ctx = object()

    monkeypatch.setattr(
        client_mod.ssl,
        "create_default_context",
        lambda: default_ctx,
    )
    monkeypatch.setattr(client_mod, "urlopen", lambda _req, timeout, context: captured.update({"timeout": timeout, "context": context}) or _DummyResponse())

    client = client_mod.RunnerClient(base_url="https://runner.local", token="t", verify_ssl=True)
    assert client.health() == {"ok": True}
    assert captured["timeout"] == 10
    assert captured["context"] is default_ctx


def test_verify_ssl_false_uses_unverified_context(monkeypatch) -> None:
    client_mod = _load_client_module()
    captured: dict[str, object] = {}
    unverified_ctx = object()

    monkeypatch.setattr(client_mod.ssl, "_create_unverified_context", lambda: unverified_ctx)  # noqa: SLF001
    monkeypatch.setattr(client_mod, "urlopen", lambda _req, timeout, context: captured.update({"timeout": timeout, "context": context}) or _DummyResponse())

    client = client_mod.RunnerClient(base_url="https://runner.local", token="t", verify_ssl=False)
    assert client.health() == {"ok": True}
    assert captured["timeout"] == 10
    assert captured["context"] is unverified_ctx


def test_backup_listener_unsubs_are_stored_and_called_on_unload() -> None:
    text = Path("custom_components/pythonista_job_runner/__init__.py").read_text(encoding="utf-8")
    assert '"backup_event_unsubs": [unsub_backup_started, unsub_backup_ended]' in text
    assert 'for unsub in entry_data.get("backup_event_unsubs", []):' in text
    assert "unsub()" in text


def test_service_registration_is_guarded_per_service() -> None:
    text = Path("custom_components/pythonista_job_runner/services.py").read_text(encoding="utf-8")
    assert "if hass.services.has_service(DOMAIN, SERVICE_PURGE_JOBS):\n        return" not in text
    for service_name in [
        "SERVICE_PURGE_JOBS",
        "SERVICE_PURGE_DONE_JOBS",
        "SERVICE_PURGE_FAILED_JOBS",
        "SERVICE_REFRESH",
        "SERVICE_CANCEL_JOB",
        "SERVICE_BUILD_PACKAGE_PROFILE",
        "SERVICE_PRUNE_PACKAGE_CACHE",
        "SERVICE_PURGE_PACKAGE_CACHE",
    ]:
        assert f"if not hass.services.has_service(DOMAIN, {service_name}):" in text


def test_client_exposes_package_management_methods() -> None:
    text = Path("custom_components/pythonista_job_runner/client.py").read_text(encoding="utf-8")
    for method in ["package_summary", "package_profiles", "package_cache", "build_package_profile", "prune_package_cache", "purge_package_cache"]:
        assert f"def {method}" in text


def test_sensor_platform_exposes_package_diagnostics_entities() -> None:
    text = Path("custom_components/pythonista_job_runner/sensor.py").read_text(encoding="utf-8")
    for key in ["package_cache_size", "package_venv_count", "package_last_prune_status", "package_default_profile"]:
        assert key in text
