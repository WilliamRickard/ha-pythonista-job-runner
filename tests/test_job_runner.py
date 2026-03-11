"""Unit tests for the add-on entry point (job_runner.py)."""

from __future__ import annotations

from unittest import mock

import pytest


def test_main_calls_serve() -> None:
    """main() should call serve() exactly once."""
    import job_runner

    with mock.patch.object(job_runner, "serve") as mock_serve:
        job_runner.main()

    mock_serve.assert_called_once_with()


def test_main_propagates_errors() -> None:
    """main() should not swallow exceptions from serve()."""
    import job_runner

    with mock.patch.object(job_runner, "serve", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            job_runner.main()
