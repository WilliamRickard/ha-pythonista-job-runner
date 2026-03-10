# Version: 0.6.13-tests-runner-core-options.1
"""Tests for runner_core helpers that do not require job execution."""

from __future__ import annotations

import json
import os

import pytest

import runner_core


def test_read_options_file_missing(temp_data_dir):
    assert runner_core.read_options() == {}


def test_read_options_valid_json(temp_data_dir):
    runner_core.OPTIONS_PATH.write_text(json.dumps({"token": "secret", "bind_port": 9090}), encoding="utf-8")
    assert runner_core.read_options() == {"token": "secret", "bind_port": 9090}


def test_read_options_grouped_json(temp_data_dir):
    runner_core.OPTIONS_PATH.write_text(
        json.dumps({"security": {"token": "secret"}, "runner": {"bind_port": 9090}}),
        encoding="utf-8",
    )
    assert runner_core.read_options() == {"token": "secret", "bind_port": 9090}


def test_read_options_invalid_json(temp_data_dir):
    runner_core.OPTIONS_PATH.write_text("not json", encoding="utf-8")
    assert runner_core.read_options() == {}


def test_read_options_non_dict_json(temp_data_dir):
    runner_core.OPTIONS_PATH.write_text(json.dumps(["x"]), encoding="utf-8")
    assert runner_core.read_options() == {}


def test_resolve_user_ids_empty_username():
    uid, gid = runner_core._resolve_user_ids("")
    assert uid is None
    assert gid is None


def test_resolve_user_ids_no_pwd_module(monkeypatch):
    monkeypatch.setattr(runner_core, "pwd", None)
    uid, gid = runner_core._resolve_user_ids("testuser")
    assert uid is None
    assert gid is None


@pytest.mark.skipif(not hasattr(os, "getuid"), reason="Unix-only test")
def test_resolve_user_ids_nonexistent_user():
    uid, gid = runner_core._resolve_user_ids("nonexistent_user_xyz_12345")
    assert uid is None
    assert gid is None


def test_hashlib_sha256_bytes_known_values():
    assert runner_core.hashlib_sha256_bytes(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert runner_core.hashlib_sha256_bytes(b"hello world") == (
        "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    )


def test_read_options_grouped_json_with_python_package_fields(temp_data_dir):
    runner_core.OPTIONS_PATH.write_text(
        json.dumps(
            {
                "python": {
                    "dependency_mode": "profile",
                    "package_cache_enabled": True,
                    "package_public_wheelhouse_subdir": "wheel_uploads",
                }
            }
        ),
        encoding="utf-8",
    )
    assert runner_core.read_options() == {
        "dependency_mode": "profile",
        "package_cache_enabled": True,
        "package_public_wheelhouse_subdir": "wheel_uploads",
    }


def test_runner_bootstraps_package_store_on_start(temp_data_dir, monkeypatch):
    public_root = temp_data_dir / "addon_config"
    public_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(runner_core._package_store, "PUBLIC_CONFIG_ROOT", public_root)

    runner = runner_core.Runner({}, start_reaper=False)

    assert runner.package_store_paths.private_root == temp_data_dir / "pythonista_job_runner"
    assert runner.package_store_paths.package_index_path.is_file()
    assert runner.package_store_bootstrap["public_available"] is True
    assert runner.package_store_paths.public_profiles_dir.is_dir()
