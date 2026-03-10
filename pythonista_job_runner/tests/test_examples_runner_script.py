# Version: 0.6.13-tests-examples-runner.3
"""Regression tests for the standalone Pythonista examples runner script."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import zipfile


class _FakeClient:
    """Simple fake runner client for result download retry tests."""

    def __init__(self, outcomes):
        """Store the scripted outcomes for successive download attempts."""
        self._outcomes = list(outcomes)
        self.calls = 0

    def download_result_zip(self, job_id, dest_zip_path):
        """Either raise the next scripted error or write a zip file."""
        self.calls += 1
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("stdout.txt", "ok\n")
        dest_zip_path.write_bytes(buffer.getvalue())
        return dest_zip_path


def _load_runner_module():
    """Load the standalone runner script as an importable module."""
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "pythonista_job_runner" / "examples" / "tools" / "pythonista_run_example_job.py"
    spec = importlib.util.spec_from_file_location("examples_runner_script", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_zip_bytes(files: dict[str, bytes]) -> bytes:
    """Return zip bytes containing the supplied archive members."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_resolve_selected_job_zip_accepts_direct_job_zip(tmp_path):
    """A direct job zip with run.py at root should be copied into the run folder."""
    module = _load_runner_module()
    job_zip = tmp_path / "job.zip"
    job_zip.write_bytes(_build_zip_bytes({"run.py": b"print('ok')\n"}))
    run_dir = tmp_path / "run_dir"
    run_dir.mkdir()

    resolved = module._resolve_selected_job_zip(job_zip, run_dir)

    assert resolved.zip_path != job_zip
    assert resolved.zip_path.parent == run_dir
    assert resolved.zip_path.exists()
    assert resolved.was_embedded is False


def test_resolve_selected_job_zip_extracts_embedded_job_zip(tmp_path, monkeypatch):
    """A selected bundle zip should expose an embedded runnable job zip."""
    module = _load_runner_module()
    embedded_job = _build_zip_bytes({"run.py": b"print('ok')\n"})
    repo_zip = _build_zip_bytes(
        {"pythonista_job_runner/examples/core/01_hello_world/job.zip": embedded_job}
    )
    bundle_zip = tmp_path / "bundle.zip"
    bundle_zip.write_bytes(_build_zip_bytes({"repo.zip": repo_zip}))
    run_dir = tmp_path / "run_dir"
    run_dir.mkdir()
    monkeypatch.setattr(module, "_choose_embedded_job_zip", lambda discovered: discovered[0])

    resolved = module._resolve_selected_job_zip(bundle_zip, run_dir)

    assert resolved.was_embedded is True
    assert resolved.zip_path.exists()
    assert module._zip_file_has_root_run_py(resolved.zip_path) is True


def test_resolve_selected_job_zip_errors_when_no_runnable_job_zip_exists(tmp_path):
    """A selected zip without a runnable job zip should fail early with a clear error."""
    module = _load_runner_module()
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(_build_zip_bytes({"notes.txt": b"no run file here"}))

    try:
        module._resolve_selected_job_zip(bad_zip, tmp_path / "run_dir")
    except module.RunnerClientError as exc:
        assert str(exc) == "selected_zip_missing_root_run_py_and_contains_no_embedded_job_zip"
    else:
        raise AssertionError("Expected RunnerClientError")


def test_download_result_zip_with_retries_handles_fast_job_race(tmp_path, monkeypatch):
    """Retryable result download failures should be retried until the zip is ready."""
    module = _load_runner_module()
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    client = _FakeClient(
        [
            module.RunnerClientError("http_error:404:not_ready"),
            module.RunnerClientError("http_error:404:not_ready"),
            "success",
        ]
    )

    result_zip_path, attempts_path = module._download_result_zip_with_retries(client, "job123", tmp_path)

    assert result_zip_path.exists()
    attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    assert [entry["result"] for entry in attempts] == ["error", "error", "saved"]
    assert client.calls == 3


def test_download_result_zip_with_retries_raises_for_non_retryable_error(tmp_path, monkeypatch):
    """Non-retryable result download failures should surface immediately."""
    module = _load_runner_module()
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    client = _FakeClient([module.RunnerClientError("http_error:401:unauthorised")])

    try:
        module._download_result_zip_with_retries(client, "job123", tmp_path)
    except module.RunnerClientError as exc:
        assert str(exc) == "http_error:401:unauthorised"
    else:
        raise AssertionError("Expected RunnerClientError")


class _FakeTailClient:
    """Simple fake client for tail polling compatibility tests."""

    def __init__(self, tails, final_status=None):
        """Store scripted tail responses and optional final status payload."""
        self._tails = list(tails)
        self.final_status = final_status or {"state": "done", "exit_code": 0}
        self.job_calls = 0

    def get_tail(self, job_id, *, stdout_from=None, stderr_from=None, max_bytes=None):
        """Return the next scripted tail payload."""
        return self._tails.pop(0)

    def get_job(self, job_id):
        """Return the final job status payload."""
        self.job_calls += 1
        return dict(self.final_status)


def test_extract_tail_payload_fields_supports_current_api_contract():
    """The runner should understand the current nested tail payload structure."""
    module = _load_runner_module()
    stdout_text, stderr_text, stdout_offset, stderr_offset, state = module._extract_tail_payload_fields(
        {
            "status": {"state": "running"},
            "tail": {"stdout": "hello\n", "stderr": "warn\n"},
            "offsets": {"stdout_next": 12, "stderr_next": 4},
        },
        stdout_offset=0,
        stderr_offset=0,
    )

    assert stdout_text == "hello\n"
    assert stderr_text == "warn\n"
    assert stdout_offset == 12
    assert stderr_offset == 4
    assert state == "running"


def test_stream_job_until_terminal_supports_current_tail_schema(monkeypatch):
    """Current tail payloads should stream logs and return terminal status."""
    module = _load_runner_module()
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    printed = []
    monkeypatch.setattr(module, "_print_text_chunk", lambda prefix, text: printed.append((prefix, text)))
    client = _FakeTailClient(
        [
            {
                "status": {"state": "running"},
                "tail": {"stdout": "step 1\n", "stderr": ""},
                "offsets": {"stdout_next": 7, "stderr_next": 0},
            },
            {
                "status": {"state": "done", "exit_code": 0},
                "tail": {"stdout": "done\n", "stderr": ""},
                "offsets": {"stdout_next": 12, "stderr_next": 0},
            },
        ]
    )
    submitted = module.SubmittedJob("job123", "/tail/job123.json", "/result/job123.zip", "/jobs.json")

    status = module._stream_job_until_terminal(client, submitted)

    assert printed == [("", "step 1\n"), ("", "done\n")]
    assert status["state"] == "done"
    assert status["exit_code"] == 0
    assert client.job_calls == 0
