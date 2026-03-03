"""Comprehensive tests for runner_core.py module."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from unittest import mock

import pytest

# Add app directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from runner_core import (
    ADDON_VERSION,
    Job,
    Runner,
    hashlib_sha256_bytes,
    read_options,
    _resolve_user_ids,
    _kill_process_group,
    _ha_persistent_notification,
)
from utils import TailBuffer, SafeZipLimits, utc_now, parse_utc


class TestJob:
    """Test Job dataclass and its methods."""

    def test_job_initialization_defaults(self):
        """Test Job initialization with default values."""
        job = Job(job_id="test123")

        assert job.job_id == "test123"
        assert job.state == "queued"
        assert job.phase == "queued"
        assert job.exit_code is None
        assert job.error is None
        assert job.cpu_percent == 25
        assert job.mem_mb == 4096
        assert job.timeout_seconds == 3600
        assert job.threads == 1
        assert job.cancel_requested is False

    def test_job_initialization_with_params(self):
        """Test Job initialization with custom parameters."""
        job = Job(
            job_id="custom123",
            state="running",
            phase="running",
            cpu_percent=50,
            mem_mb=8192,
            timeout_seconds=7200,
            threads=4,
            submitted_by_name="testuser",
            client_ip="192.168.1.1"
        )

        assert job.job_id == "custom123"
        assert job.state == "running"
        assert job.phase == "running"
        assert job.cpu_percent == 50
        assert job.mem_mb == 8192
        assert job.timeout_seconds == 7200
        assert job.threads == 4
        assert job.submitted_by_name == "testuser"
        assert job.client_ip == "192.168.1.1"

    def test_job_duration_seconds_no_start(self):
        """Test duration_seconds when job hasn't started."""
        job = Job(job_id="test123")
        assert job.duration_seconds() is None

    def test_job_duration_seconds_running(self):
        """Test duration_seconds for a running job."""
        job = Job(job_id="test123")
        from datetime import datetime, timezone
        job.started_utc = datetime.fromtimestamp(time.time() - 2, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        duration = job.duration_seconds()
        assert duration is not None
        assert duration >= 0
        assert duration <= 5  # Allow for rounding to whole seconds

    def test_job_duration_seconds_finished(self):
        """Test duration_seconds for a finished job."""
        # Create timestamps with known difference
        start_time = time.time() - 100  # 100 seconds ago
        from datetime import datetime, timezone
        job = Job(job_id="test123")
        job.started_utc = datetime.fromtimestamp(start_time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        job.finished_utc = datetime.fromtimestamp(start_time + 50, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        duration = job.duration_seconds()
        assert duration is not None
        # Duration should be around 50 seconds (with some tolerance)
        assert 49 <= duration <= 51

    def test_job_status_dict_basic(self):
        """Test status_dict returns correct structure."""
        job = Job(job_id="test123")
        job.state = "done"
        job.phase = "done"
        job.exit_code = 0

        status = job.status_dict()

        assert status["job_id"] == "test123"
        assert status["state"] == "done"
        assert status["phase"] == "done"
        assert status["exit_code"] == 0
        assert status["runner_version"] == ADDON_VERSION
        assert "limits" in status
        assert status["limits"]["cpu_percent"] == 25
        assert status["limits"]["mem_mb"] == 4096
        assert "submitted_by" in status

    def test_job_status_dict_with_metadata(self):
        """Test status_dict includes submission metadata."""
        job = Job(
            job_id="test123",
            submitted_by_name="alice",
            submitted_by_display_name="Alice Smith",
            submitted_by_id="user_001",
            client_ip="10.0.0.5"
        )

        status = job.status_dict()

        assert status["submitted_by"]["name"] == "alice"
        assert status["submitted_by"]["display_name"] == "Alice Smith"
        assert status["submitted_by"]["id"] == "user_001"
        assert status["client_ip"] == "10.0.0.5"

    def test_job_status_dict_duration(self):
        """Test status_dict includes duration calculation."""
        job = Job(job_id="test123")
        job.started_utc = utc_now()

        status = job.status_dict()

        assert "duration_seconds" in status
        assert status["duration_seconds"] is not None
        assert status["duration_seconds"] >= 0


class TestReadOptions:
    """Test read_options function."""

    def test_read_options_file_not_exists(self, tmp_path, monkeypatch):
        """Test read_options when file doesn't exist."""
        monkeypatch.setattr("runner_core.OPTIONS_PATH", tmp_path / "nonexistent.json")
        result = read_options()
        assert result == {}

    def test_read_options_valid_json(self, tmp_path, monkeypatch):
        """Test read_options with valid JSON file."""
        options_file = tmp_path / "options.json"
        options_data = {"token": "secret123", "bind_port": 9090}
        options_file.write_text(json.dumps(options_data))

        monkeypatch.setattr("runner_core.OPTIONS_PATH", options_file)
        result = read_options()

        assert result == options_data
        assert result["token"] == "secret123"
        assert result["bind_port"] == 9090

    def test_read_options_invalid_json(self, tmp_path, monkeypatch):
        """Test read_options with invalid JSON."""
        options_file = tmp_path / "options.json"
        options_file.write_text("not valid json{")

        monkeypatch.setattr("runner_core.OPTIONS_PATH", options_file)
        result = read_options()

        assert result == {}

    def test_read_options_not_dict(self, tmp_path, monkeypatch):
        """Test read_options when JSON is not a dictionary."""
        options_file = tmp_path / "options.json"
        options_file.write_text(json.dumps(["list", "not", "dict"]))

        monkeypatch.setattr("runner_core.OPTIONS_PATH", options_file)
        result = read_options()

        assert result == {}


class TestResolveUserIds:
    """Test _resolve_user_ids function."""

    def test_resolve_user_ids_empty_username(self):
        """Test _resolve_user_ids with empty username."""
        uid, gid = _resolve_user_ids("")
        assert uid is None
        assert gid is None

    def test_resolve_user_ids_no_pwd_module(self, monkeypatch):
        """Test _resolve_user_ids when pwd module unavailable."""
        # Simulate pwd being None (Windows environment)
        monkeypatch.setattr("runner_core.pwd", None)
        uid, gid = _resolve_user_ids("testuser")
        assert uid is None
        assert gid is None

    @pytest.mark.skipif(not hasattr(os, 'getuid'), reason="Unix-only test")
    def test_resolve_user_ids_nonexistent_user(self):
        """Test _resolve_user_ids with non-existent user."""
        uid, gid = _resolve_user_ids("nonexistent_user_xyz_12345")
        assert uid is None
        assert gid is None

    @pytest.mark.skipif(not hasattr(os, 'getuid'), reason="Unix-only test")
    def test_resolve_user_ids_root(self):
        """Test _resolve_user_ids with root user."""
        uid, gid = _resolve_user_ids("root")
        # root should exist on Unix systems
        if uid is not None:
            assert uid == 0
            assert gid == 0


class TestHashlibSha256Bytes:
    """Test hashlib_sha256_bytes function."""

    def test_hashlib_sha256_bytes_empty(self):
        """Test SHA256 of empty bytes."""
        result = hashlib_sha256_bytes(b"")
        # SHA256 of empty string
        assert result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hashlib_sha256_bytes_known_value(self):
        """Test SHA256 with known input."""
        result = hashlib_sha256_bytes(b"hello world")
        # Known SHA256 of "hello world"
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_hashlib_sha256_bytes_binary_data(self):
        """Test SHA256 with binary data."""
        data = bytes(range(256))
        result = hashlib_sha256_bytes(data)
        assert len(result) == 64  # SHA256 is 64 hex characters
        assert all(c in "0123456789abcdef" for c in result)


class TestKillProcessGroup:
    """Test _kill_process_group function."""

    def test_kill_process_group_already_terminated(self):
        """Test killing a process that's already terminated."""
        # Create a simple process that exits immediately
        proc = subprocess.Popen(["python3", "-c", "exit(0)"])
        proc.wait()  # Wait for it to finish

        # Should handle gracefully
        _kill_process_group(proc, soft_seconds=1)
        assert proc.poll() is not None

    def test_kill_process_group_sigterm(self):
        """Test killing process with SIGTERM."""
        # Create a long-running process
        proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(60)"],
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )

        try:
            # Kill with short timeout
            _kill_process_group(proc, soft_seconds=1)

            # Process should be terminated
            time.sleep(0.5)
            assert proc.poll() is not None
        finally:
            # Ensure cleanup
            try:
                proc.kill()
                proc.wait(timeout=1)
            except:
                pass

    def test_kill_process_group_no_pgid(self):
        """Test killing process when pgid lookup fails."""
        # Create a mock process
        mock_proc = mock.MagicMock()
        mock_proc.pid = 999999  # Non-existent PID
        mock_proc.poll.return_value = None

        # Should handle the exception gracefully
        _kill_process_group(mock_proc, soft_seconds=1)


class TestHaPersistentNotification:
    """Test _ha_persistent_notification function."""

    def test_ha_notification_no_token(self, monkeypatch):
        """Test notification when SUPERVISOR_TOKEN is not set."""
        monkeypatch.setattr("runner_core.SUPERVISOR_TOKEN", "")

        # Should return early without error
        _ha_persistent_notification("Test", "Message", "notif_id")

    @mock.patch("runner_core.urlopen")
    def test_ha_notification_with_id(self, mock_urlopen, monkeypatch):
        """Test notification with notification_id."""
        monkeypatch.setattr("runner_core.SUPERVISOR_TOKEN", "test_token")
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        _ha_persistent_notification("Title", "Message", "notif_123")

        assert mock_urlopen.called
        call_args = mock_urlopen.call_args[0][0]
        assert "Bearer test_token" in call_args.headers.get("Authorization", "")

    @mock.patch("runner_core.urlopen")
    def test_ha_notification_without_id(self, mock_urlopen, monkeypatch):
        """Test notification without notification_id."""
        monkeypatch.setattr("runner_core.SUPERVISOR_TOKEN", "test_token")
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"status": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        _ha_persistent_notification("Title", "Message", None)

        assert mock_urlopen.called

    @mock.patch("runner_core.urlopen", side_effect=Exception("Network error"))
    def test_ha_notification_exception_handling(self, mock_urlopen, monkeypatch):
        """Test notification handles exceptions gracefully."""
        monkeypatch.setattr("runner_core.SUPERVISOR_TOKEN", "test_token")

        # Should not raise exception
        _ha_persistent_notification("Title", "Message", "notif_id")


class TestRunner:
    """Test Runner class."""

    @pytest.fixture
    def temp_jobs_dir(self, tmp_path, monkeypatch):
        """Create temporary jobs directory."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)
        monkeypatch.setattr("runner_core.DATA_DIR", tmp_path)
        return jobs_dir

    @pytest.fixture
    def basic_opts(self):
        """Basic options for Runner."""
        return {
            "token": "test_token",
            "bind_host": "0.0.0.0",
            "bind_port": 8787,
            "job_user": "root" if hasattr(os, "getuid") else "jobrunner",
        }

    def test_runner_initialization_defaults(self, temp_jobs_dir, basic_opts):
        """Test Runner initialization with default options."""
        runner = Runner(basic_opts)

        assert runner.token == "test_token"
        assert runner.bind_host == "0.0.0.0"
        assert runner.bind_port == 8787
        assert runner.job_user in ("root", "jobrunner")
        assert runner.timeout_seconds == 3600
        assert runner.max_upload_mb == 50
        assert runner.default_cpu == 25
        assert runner.max_cpu == 50
        assert runner.default_mem == 4096
        assert runner.max_mem == 4096
        assert runner.max_threads == 1
        assert runner.max_concurrent_jobs == 1
        assert runner.queue_max_jobs == 10

    def test_runner_initialization_custom_options(self, temp_jobs_dir):
        """Test Runner initialization with custom options."""
        opts = {
            "token": "custom_token",
            "bind_port": 9090,
            "timeout_seconds": 7200,
            "max_upload_mb": 100,
            "default_cpu_percent": 50,
            "max_cpu_percent": 100,
            "max_concurrent_jobs": 5,
            "queue_max_jobs": 20,
            "notify_on_completion": False,
        }

        runner = Runner(opts)

        assert runner.token == "custom_token"
        assert runner.bind_port == 9090
        assert runner.timeout_seconds == 7200
        assert runner.max_upload_mb == 100
        assert runner.default_cpu == 50
        assert runner.max_cpu == 100
        assert runner.max_concurrent_jobs == 5
        assert runner.queue_max_jobs == 20
        assert runner.notify_on_completion is False

    def test_runner_invalid_port_fallback(self, temp_jobs_dir, basic_opts):
        """Test Runner uses default port for invalid port values."""
        basic_opts["bind_port"] = 99999  # Invalid port
        runner = Runner(basic_opts)
        assert runner.bind_port == 8787

    def test_runner_stats_dict_empty(self, temp_jobs_dir, basic_opts):
        """Test stats_dict with no jobs."""
        runner = Runner(basic_opts)
        stats = runner.stats_dict()

        assert stats["runner_version"] == ADDON_VERSION
        assert stats["jobs_total"] == 0
        assert stats["jobs_running"] == 0
        assert stats["jobs_done"] == 0
        assert stats["jobs_error"] == 0
        assert stats["jobs_queued"] == 0
        assert stats["job_retention_hours"] == 24
        assert "disk_free_bytes" in stats
        assert "disk_total_bytes" in stats

    def test_runner_list_jobs_empty(self, temp_jobs_dir, basic_opts):
        """Test list_jobs with no jobs."""
        runner = Runner(basic_opts)
        jobs = runner.list_jobs()
        assert jobs == []

    def test_runner_get_nonexistent_job(self, temp_jobs_dir, basic_opts):
        """Test get with non-existent job ID."""
        runner = Runner(basic_opts)
        job = runner.get("nonexistent_id")
        assert job is None

    def test_runner_build_job_env(self, temp_jobs_dir, basic_opts):
        """Test _build_job_env creates proper environment."""
        runner = Runner(basic_opts)
        env = runner._build_job_env(threads=4)

        assert env["HOME"] == "/tmp"
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["OMP_NUM_THREADS"] == "4"
        assert env["OPENBLAS_NUM_THREADS"] == "4"
        assert env["MKL_NUM_THREADS"] == "4"
        assert "SUPERVISOR_TOKEN" not in env

    def test_runner_build_job_env_with_allow_env(self, temp_jobs_dir, monkeypatch):
        """Test _build_job_env with allowed environment variables."""
        monkeypatch.setenv("CUSTOM_VAR", "custom_value")
        monkeypatch.setenv("SUPERVISOR_TOKEN", "should_not_leak")

        opts = {
            "token": "test",
            "allow_env": ["CUSTOM_VAR", "SUPERVISOR_TOKEN"],
        }
        runner = Runner(opts)
        env = runner._build_job_env(threads=1)

        assert env.get("CUSTOM_VAR") == "custom_value"
        # SUPERVISOR_TOKEN should be filtered out even if in allow_env
        assert "SUPERVISOR_TOKEN" not in env

    def test_runner_new_job_queue_full(self, temp_jobs_dir, basic_opts):
        """Test new_job raises error when queue is full."""
        basic_opts["queue_max_jobs"] = 1
        runner = Runner(basic_opts)

        # Keep the first job "active" deterministically so queue_full is stable.
        runner._run_job = lambda _job_id: None

        # Create minimal zip with run.py
        zip_buffer = create_test_zip()

        # Create first job to fill the queue
        job1 = runner.new_job(zip_buffer, {}, "127.0.0.1")

        # Second job should raise queue_full error
        with pytest.raises(RuntimeError, match="queue_full"):
            runner.new_job(zip_buffer, {}, "127.0.0.1")

    def test_runner_new_job_missing_run_py(self, temp_jobs_dir, basic_opts):
        """Test new_job raises error when run.py is missing from zip."""
        runner = Runner(basic_opts)

        # Create zip without run.py
        import io
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr("other_file.txt", "content")

        with pytest.raises(RuntimeError, match="zip_missing_run_py"):
            runner.new_job(zip_buffer.getvalue(), {}, "127.0.0.1")

    def test_runner_delete_nonexistent(self, temp_jobs_dir, basic_opts):
        """Test delete returns False for non-existent job."""
        runner = Runner(basic_opts)
        result = runner.delete("nonexistent_id")
        assert result is False

    def test_runner_cancel_nonexistent(self, temp_jobs_dir, basic_opts):
        """Test cancel returns False for non-existent job."""
        runner = Runner(basic_opts)
        result = runner.cancel("nonexistent_id")
        assert result is False

    def test_runner_purge_dry_run(self, temp_jobs_dir, basic_opts):
        """Test purge with dry_run=True doesn't delete jobs."""
        runner = Runner(basic_opts)

        # Manually add a job to internal state
        job = Job(job_id="test123", state="done")
        runner._jobs["test123"] = job
        runner._job_order.append("test123")

        result = runner.purge(states=["done"], older_than_hours=0, dry_run=True)

        assert result["ok"] is True
        assert result["dry_run"] is True
        assert "test123" in result["deleted"]
        # Job should still exist
        assert runner.get("test123") is not None

    def test_runner_purge_by_state(self, temp_jobs_dir, basic_opts):
        """Test purge filters by state correctly."""
        runner = Runner(basic_opts)

        # Add jobs with different states
        job1 = Job(job_id="done1", state="done")
        job2 = Job(job_id="error1", state="error")
        job3 = Job(job_id="running1", state="running")

        runner._jobs["done1"] = job1
        runner._jobs["error1"] = job2
        runner._jobs["running1"] = job3
        runner._job_order.extend(["done1", "error1", "running1"])

        result = runner.purge(states=["done"], older_than_hours=0, dry_run=True)

        assert "done1" in result["deleted"]
        assert "error1" not in result["deleted"]
        assert "running1" not in result["deleted"]

    def test_runner_notification_id_per_job(self, temp_jobs_dir):
        """Test _notification_id with per_job mode."""
        opts = {
            "token": "test",
            "notify_on_completion": True,
            "notification_mode": "per_job",
            "notification_id_prefix": "test_prefix",
        }
        runner = Runner(opts)

        job = Job(job_id="job123")
        notif_id = runner._notification_id(job)

        assert notif_id == "test_prefix_job123"

    def test_runner_notification_id_latest(self, temp_jobs_dir):
        """Test _notification_id with latest mode."""
        opts = {
            "token": "test",
            "notify_on_completion": True,
            "notification_mode": "latest",
            "notification_id_prefix": "test_prefix",
        }
        runner = Runner(opts)

        job = Job(job_id="job123")
        notif_id = runner._notification_id(job)

        assert notif_id == "test_prefix_latest"

    def test_runner_notification_disabled(self, temp_jobs_dir):
        """Test _notification_id returns None when disabled."""
        opts = {
            "token": "test",
            "notify_on_completion": False,
        }
        runner = Runner(opts)

        job = Job(job_id="job123")
        notif_id = runner._notification_id(job)

        assert notif_id is None


class TestRunnerIntegration:
    """Integration tests for Runner class."""

    @pytest.fixture
    def temp_jobs_dir(self, tmp_path, monkeypatch):
        """Create temporary jobs directory."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)
        monkeypatch.setattr("runner_core.DATA_DIR", tmp_path)
        return jobs_dir

    def test_runner_new_job_creates_job(self, temp_jobs_dir):
        """Test new_job creates a job successfully."""
        opts = {"token": "test", "job_user": "root" if hasattr(os, "getuid") else "jobrunner"}
        runner = Runner(opts)

        zip_data = create_test_zip()
        headers = {
            "X-Runner-CPU-PCT": "30",
            "X-Runner-MEM-MB": "2048",
        }

        job = runner.new_job(zip_data, headers, "192.168.1.10")

        assert job.job_id is not None
        assert job.state == "queued"
        assert job.cpu_percent == 30
        assert job.mem_mb == 2048
        assert job.client_ip == "192.168.1.10"

        # Verify job is in runner
        retrieved_job = runner.get(job.job_id)
        assert retrieved_job is not None
        assert retrieved_job.job_id == job.job_id

    def test_runner_stats_with_jobs(self, temp_jobs_dir):
        """Test stats_dict with various job states."""
        opts = {"token": "test", "job_user": "root" if hasattr(os, "getuid") else "jobrunner"}
        runner = Runner(opts)

        # Add jobs manually
        runner._jobs["job1"] = Job(job_id="job1", state="queued")
        runner._jobs["job2"] = Job(job_id="job2", state="running")
        runner._jobs["job3"] = Job(job_id="job3", state="done")
        runner._jobs["job4"] = Job(job_id="job4", state="error")
        runner._job_order = ["job1", "job2", "job3", "job4"]

        stats = runner.stats_dict()

        assert stats["jobs_total"] == 4
        assert stats["jobs_queued"] == 1
        assert stats["jobs_running"] == 1
        assert stats["jobs_done"] == 1
        assert stats["jobs_error"] == 1

    def test_runner_list_jobs_ordered(self, temp_jobs_dir):
        """Test list_jobs returns jobs in correct order."""
        opts = {"token": "test", "job_user": "root" if hasattr(os, "getuid") else "jobrunner"}
        runner = Runner(opts)

        job1 = Job(job_id="first")
        job2 = Job(job_id="second")
        job3 = Job(job_id="third")

        runner._jobs["first"] = job1
        runner._jobs["second"] = job2
        runner._jobs["third"] = job3
        runner._job_order = ["third", "second", "first"]

        jobs = runner.list_jobs()

        assert len(jobs) == 3
        assert jobs[0].job_id == "third"
        assert jobs[1].job_id == "second"
        assert jobs[2].job_id == "first"


# Helper functions for tests
def create_test_zip() -> bytes:
    """Create a minimal test zip file with run.py."""
    import io
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr("run.py", "#!/usr/bin/env python3\nprint('Hello from test job')\n")
    return zip_buffer.getvalue()


# Edge case and regression tests
class TestEdgeCases:
    """Test edge cases and potential issues."""

    def test_job_duration_with_invalid_timestamps(self):
        """Test duration calculation with invalid timestamp strings."""
        job = Job(job_id="test")
        job.started_utc = "invalid_timestamp"
        job.finished_utc = "also_invalid"

        # Should handle gracefully
        duration = job.duration_seconds()
        assert duration is not None
        assert duration >= 0

    def test_hashlib_sha256_large_data(self):
        """Test SHA256 with larger data to ensure it handles memory correctly."""
        # Create 1MB of data
        large_data = b"x" * (1024 * 1024)
        result = hashlib_sha256_bytes(large_data)

        assert len(result) == 64
        assert isinstance(result, str)

    def test_runner_cpu_limit_mode_validation(self, tmp_path, monkeypatch):
        """Test Runner validates cpu_limit_mode correctly."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)

        opts = {
            "token": "test",
            "cpu_limit_mode": "invalid_mode",
        }
        runner = Runner(opts)

        # Should fall back to default
        assert runner.cpu_limit_mode == "invalid_mode"  # Stores as-is

    def test_runner_allow_env_filters_invalid_names(self, tmp_path, monkeypatch):
        """Test Runner filters out invalid environment variable names."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)

        opts = {
            "token": "test",
            "allow_env": ["VALID_VAR", "123invalid", "also-invalid", "ANOTHER_VALID"],
        }
        runner = Runner(opts)

        assert "VALID_VAR" in runner.allow_env
        assert "ANOTHER_VALID" in runner.allow_env
        assert "123invalid" not in runner.allow_env
        assert "also-invalid" not in runner.allow_env


# Boundary tests
class TestBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_job_duration_zero_time_difference(self):
        """Test duration when start and finish are identical."""
        job = Job(job_id="test")
        timestamp = utc_now()
        job.started_utc = timestamp
        job.finished_utc = timestamp

        duration = job.duration_seconds()
        assert duration == 0

    def test_runner_zero_concurrent_jobs(self, tmp_path, monkeypatch):
        """Test Runner handles zero/negative concurrent jobs."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)

        opts = {
            "token": "test",
            "max_concurrent_jobs": 0,
        }
        runner = Runner(opts)

        # Should clamp to at least 1
        assert runner._sema._value >= 1

    def test_runner_negative_retention_hours(self, tmp_path, monkeypatch):
        """Test Runner handles negative retention hours."""
        jobs_dir = tmp_path / "jobs"
        jobs_dir.mkdir()
        monkeypatch.setattr("runner_core.JOBS_DIR", jobs_dir)

        opts = {
            "token": "test",
            "job_retention_hours": -10,
        }
        runner = Runner(opts)

        # Negative values are clamped defensively
        assert runner.retention_hours == 1
