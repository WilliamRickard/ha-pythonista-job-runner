# Version: 0.6.13-tests-examples-packages.1
"""Tests for package example documentation and manifest wiring."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "pythonista_job_runner" / "examples"
VALIDATOR_PATH = EXAMPLES_ROOT / "tools" / "validate_examples.py"


def _load_validator_module():
    """Load the lightweight examples validator module from disk."""
    shutil.rmtree(EXAMPLES_ROOT / "tools" / "__pycache__", ignore_errors=True)
    spec = importlib.util.spec_from_file_location("examples_validate_examples", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    old_flag = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old_flag
    shutil.rmtree(EXAMPLES_ROOT / "tools" / "__pycache__", ignore_errors=True)
    return module


def test_examples_validator_accepts_package_track() -> None:
    """The examples suite should validate cleanly with the package track present."""
    module = _load_validator_module()
    errors = module.validate_examples_root(EXAMPLES_ROOT)
    assert errors == []


def test_package_examples_public_config_assets_exist() -> None:
    """Package examples should ship the public-config assets their READMEs reference."""
    wheel_path = EXAMPLES_ROOT / "packages" / "12_offline_wheelhouse_install" / "public_config" / "wheel_uploads" / "pjr_demo_formatsize-0.1.0-py3-none-any.whl"
    profile_dir = EXAMPLES_ROOT / "packages" / "13_named_package_profile_run" / "public_config" / "package_profiles" / "demo_formatsize_profile"
    assert wheel_path.is_file()
    assert (profile_dir / "manifest.json").is_file()
    assert (profile_dir / "requirements.txt").is_file()
