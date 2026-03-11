# Version: 0.6.13-tests-package-store.6
"""Tests for package storage path resolution and bootstrap."""

from __future__ import annotations

import zipfile
from pathlib import Path

from runner import package_store


def _write_demo_wheel(path: Path, *, suspicious: bool = False) -> None:
    """Write a minimal structurally valid wheel archive for tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("demo_pkg/__init__.py", "__version__ = '0.1.0'\n")
        wheel_prefix = "../evil/demo_pkg-0.1.0.dist-info" if suspicious else "demo_pkg-0.1.0.dist-info"
        zf.writestr(f"{wheel_prefix}/WHEEL", "Wheel-Version: 1.0\nGenerator: tests\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        zf.writestr(f"{wheel_prefix}/METADATA", "Metadata-Version: 2.1\nName: demo-pkg\nVersion: 0.1.0\n")
        zf.writestr(f"{wheel_prefix}/RECORD", "demo_pkg/__init__.py,,\n")


def test_build_package_store_paths_uses_private_and_public_roots(tmp_path):
    """Package store path resolution should honour the supplied roots."""
    public_root = tmp_path / "public_config"
    paths = package_store.build_package_store_paths(
        tmp_path,
        public_root=public_root,
        public_wheelhouse_subdir="wheel_uploads_custom",
    )

    assert paths.private_root == tmp_path / "pythonista_job_runner"
    assert paths.pip_cache_dir == tmp_path / "pythonista_job_runner" / "cache" / "pip"
    assert paths.public_root == public_root
    assert paths.public_wheel_uploads_dir == public_root / "wheel_uploads_custom"


def test_sanitise_public_subdir_rejects_unsafe_names():
    """Unsafe public subdirectory names should fall back to the default."""
    assert package_store.sanitise_public_subdir("../escape") == "wheel_uploads"
    assert package_store.sanitise_public_subdir("nested/path") == "wheel_uploads"
    assert package_store.sanitise_public_subdir("wheel_uploads-ok") == "wheel_uploads-ok"


def test_bootstrap_package_store_creates_private_tree_and_state_files(tmp_path):
    """Bootstrap should create the private store even when public config is absent."""
    public_root = tmp_path / "missing_public"
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)

    result = package_store.bootstrap_package_store(paths)

    assert paths.private_root.is_dir()
    assert paths.pip_cache_dir.is_dir()
    assert paths.wheelhouse_imported_dir.is_dir()
    assert paths.package_index_path.is_file()
    assert paths.venv_index_path.is_file()
    assert result["public_available"] is False


def test_bootstrap_package_store_creates_public_dirs_when_available(tmp_path):
    """Bootstrap should create user-visible subdirectories when /config is present."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)

    result = package_store.bootstrap_package_store(paths)

    assert result["public_available"] is True
    assert paths.public_profiles_dir.is_dir()
    assert paths.public_wheel_uploads_dir.is_dir()
    assert paths.public_diagnostics_dir.is_dir()
    assert paths.public_exports_dir.is_dir()


def test_sync_public_wheel_uploads_copies_valid_files_and_skips_invalid(tmp_path):
    """Public wheel uploads should be validated before import into the private wheelhouse."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    good = paths.public_wheel_uploads_dir / "demo_pkg-0.1.0-py3-none-any.whl"
    _write_demo_wheel(good)
    bad = paths.public_wheel_uploads_dir / "not_a_wheel.txt"
    bad.write_bytes(b"bad")

    result = package_store.sync_public_wheel_uploads(paths)

    assert result["status"] == "ok"
    assert result["copied"] == 1
    assert result["skipped_invalid"] >= 1
    assert (paths.wheelhouse_imported_dir / good.name).is_file()
    summary = package_store.refresh_package_index(paths)
    assert summary["imported_files"] == 1
    assert summary["total_files"] == 1


def test_sync_public_wheel_uploads_rejects_oversized_and_suspicious_archives(tmp_path):
    """Oversized and suspicious wheel uploads should be rejected."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    suspicious = paths.public_wheel_uploads_dir / "demo_pkg-0.2.0-py3-none-any.whl"
    _write_demo_wheel(suspicious, suspicious=True)
    oversized = paths.public_wheel_uploads_dir / "demo_pkg-0.3.0-py3-none-any.whl"
    _write_demo_wheel(oversized)
    with oversized.open("ab") as f:
        f.write(b"x" * 4096)

    result = package_store.sync_public_wheel_uploads(paths, max_import_bytes=1024)

    assert result["skipped_invalid"] >= 2
    assert result["skipped_invalid_path"] >= 1
    assert result["skipped_oversized"] >= 1
    assert not (paths.wheelhouse_imported_dir / suspicious.name).exists()
    assert not (paths.wheelhouse_imported_dir / oversized.name).exists()


def test_find_links_dirs_includes_internal_and_job_vendor_dirs(tmp_path):
    """Wheelhouse link directories should include internal and job-local wheel folders."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)
    _write_demo_wheel(paths.wheelhouse_imported_dir / "demo_pkg-0.1.0-py3-none-any.whl")
    work_dir = tmp_path / "job"
    vendor = work_dir / "vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    _write_demo_wheel(vendor / "vendor_pkg-0.2.0-py3-none-any.whl")

    out = package_store.find_links_dirs(paths, work_dir=work_dir)

    assert str(paths.wheelhouse_imported_dir) in out
    assert str(vendor) in out



def test_ensure_job_user_private_write_access_repairs_private_dirs(tmp_path, monkeypatch):
    """Private package-store paths should be repaired for the job user on startup."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    chown_calls: list[str] = []
    chmod_calls: list[str] = []

    monkeypatch.setattr(package_store.os, "chown", lambda path, uid, gid: chown_calls.append(str(path)))
    monkeypatch.setattr(package_store.os, "chmod", lambda path, mode: chmod_calls.append(str(path)))

    result = package_store.ensure_job_user_private_write_access(paths, uid=123, gid=456)

    assert result["status"] == "ok"
    assert any(path.endswith('/venvs') for path in chown_calls)
    assert any(path.endswith('/jobs/package_reports') for path in chown_calls)
    assert any(path.endswith('/cache/pip') for path in chmod_calls)


def test_upload_public_wheel_stores_file_and_syncs_to_imported_wheelhouse(tmp_path):
    """Wheel uploads should land in the public folder and sync into the imported wheelhouse."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    upload_path = tmp_path / "incoming.whl"
    _write_demo_wheel(upload_path)

    result = package_store.upload_public_wheel(
        paths,
        upload_path,
        filename="demo_pkg-0.1.0-py3-none-any.whl",
        overwrite=False,
        max_upload_bytes=1024 * 1024,
        sync_after_upload=True,
    )

    assert result["status"] == "ok"
    assert result["action"] == "uploaded"
    assert (paths.public_wheel_uploads_dir / "demo_pkg-0.1.0-py3-none-any.whl").is_file()
    assert (paths.wheelhouse_imported_dir / "demo_pkg-0.1.0-py3-none-any.whl").is_file()
    assert result["sync"]["status"] == "ok"


def test_upload_public_wheel_rejects_existing_file_without_overwrite(tmp_path):
    """Wheel uploads should not overwrite an existing public file unless requested."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    existing = paths.public_wheel_uploads_dir / "demo_pkg-0.1.0-py3-none-any.whl"
    _write_demo_wheel(existing)
    upload_path = tmp_path / "incoming.whl"
    _write_demo_wheel(upload_path)

    result = package_store.upload_public_wheel(
        paths,
        upload_path,
        filename=existing.name,
        overwrite=False,
        max_upload_bytes=1024 * 1024,
        sync_after_upload=False,
    )

    assert result["status"] == "error"
    assert result["error"] == "already_exists"


def test_delete_public_wheel_removes_public_and_imported_copy(tmp_path):
    """Deleting one uploaded wheel should also remove its imported copy."""
    public_root = tmp_path / "public_config"
    public_root.mkdir(parents=True, exist_ok=True)
    paths = package_store.build_package_store_paths(tmp_path, public_root=public_root)
    package_store.bootstrap_package_store(paths)

    upload_path = tmp_path / "incoming.whl"
    _write_demo_wheel(upload_path)
    package_store.upload_public_wheel(
        paths,
        upload_path,
        filename="demo_pkg-0.1.0-py3-none-any.whl",
        overwrite=False,
        max_upload_bytes=1024 * 1024,
        sync_after_upload=True,
    )

    result = package_store.delete_public_wheel(paths, "demo_pkg-0.1.0-py3-none-any.whl")

    assert result["status"] == "ok"
    assert result["deleted_public"] is True
    assert result["deleted_imported"] is True
    assert not (paths.public_wheel_uploads_dir / "demo_pkg-0.1.0-py3-none-any.whl").exists()
    assert not (paths.wheelhouse_imported_dir / "demo_pkg-0.1.0-py3-none-any.whl").exists()
