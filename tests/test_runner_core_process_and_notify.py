"""Tests for process management and Home Assistant notification helpers."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from unittest import mock

import pytest

import runner_core


@pytest.mark.skipif(not hasattr(os, "getpgid") or not hasattr(os, "setsid"), reason="Unix process-group semantics required")
def test_kill_process_group_terminates_sleeping_process():
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        preexec_fn=os.setsid,
    )

    try:
        runner_core._kill_process_group(proc, soft_seconds=1)
        time.sleep(0.2)
        assert proc.poll() is not None
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def test_kill_process_group_handles_missing_pgid():
    mock_proc = mock.MagicMock()
    mock_proc.pid = 999999
    mock_proc.poll.return_value = None

    runner_core._kill_process_group(mock_proc, soft_seconds=1)


def test_ha_notification_returns_early_without_token(monkeypatch):
    monkeypatch.setattr(runner_core, "SUPERVISOR_TOKEN", "")
    runner_core._ha_persistent_notification("Title", "Message", "notif_id")


@mock.patch("runner_core.urlopen")
def test_ha_notification_sets_bearer_token(mock_urlopen, monkeypatch):
    monkeypatch.setattr(runner_core, "SUPERVISOR_TOKEN", "test_token")

    mock_response = mock.MagicMock()
    mock_response.read.return_value = b'{"status": "ok"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    runner_core._ha_persistent_notification("Title", "Message", "notif_123")

    req = mock_urlopen.call_args[0][0]
    assert req.headers.get("Authorization") == "Bearer test_token"
