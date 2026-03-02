"""Pytest fixtures and shared helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


APP_DIR = (Path(__file__).resolve().parent.parent / "app").resolve()

# Ensure the add-on's app modules are importable in all tests.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Patch runner_core globals to use a temporary /data equivalent."""
    import runner_core

    jobs_dir = tmp_path / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(runner_core, "DATA_DIR", tmp_path)
    monkeypatch.setattr(runner_core, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(runner_core, "OPTIONS_PATH", tmp_path / "options.json")

    return tmp_path


def make_zip(files: dict[str, str | bytes]) -> bytes:
    """Build a zip archive in memory from a mapping of filename to content."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            if isinstance(content, bytes):
                zf.writestr(name, content)
            else:
                zf.writestr(name, content)
    return buf.getvalue()


@pytest.fixture
def minimal_job_zip() -> bytes:
    """A minimal job zip containing run.py."""
    return make_zip({"run.py": "print('hello')\n"})
