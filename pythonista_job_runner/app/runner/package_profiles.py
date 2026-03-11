# Version: 0.6.13-package-profiles.7
"""Package profile discovery, build, and export helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from runner import package_envs
from runner import package_hashes
from runner import package_prune
from runner import package_store
from runner.redact import redact_pip_text
from utils import utc_now


_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

DEFAULT_SETUP_TARGET_PROFILE = "demo_formatsize_profile"
DEFAULT_SETUP_TARGET_WHEEL = "pjr_demo_formatsize-0.1.0-py3-none-any.whl"


def _setup_config_snippet(target_profile: str) -> str:
    """Return the suggested add-on configuration snippet for profile-mode setup."""
    safe_target = _safe_profile_name(target_profile) or DEFAULT_SETUP_TARGET_PROFILE
    return "\n".join([
        "python:",
        "  install_requirements: true",
        "  dependency_mode: profile",
        "  package_profiles_enabled: true",
        f"  package_profile_default: {safe_target}",
        "  package_allow_public_wheelhouse: true",
        "  package_offline_prefer_local: true",
        "  venv_reuse_enabled: true",
    ])


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    """Read JSON with a deterministic fallback on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(fallback)



def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write one JSON payload deterministically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def _safe_profile_name(name: str) -> str:
    """Return a safe profile name or an empty string."""
    value = str(name or "").strip()
    if _PROFILE_NAME_RE.fullmatch(value):
        return value
    return ""



def _manifest_candidates(profile_dir: Path) -> list[Path]:
    """Return supported manifest file candidates in priority order."""
    return [profile_dir / "manifest.json", profile_dir / "profile.json"]



def _read_profile_manifest(profile_dir: Path) -> tuple[Path | None, dict[str, Any]]:
    """Return the first valid manifest file and its payload."""
    for candidate in _manifest_candidates(profile_dir):
        if not candidate.exists() or not candidate.is_file() or candidate.is_symlink():
            continue
        payload = _read_json(candidate, {})
        if isinstance(payload, dict):
            return candidate, payload
    return (None, {})



def _requirements_path(profile_dir: Path) -> Path | None:
    """Return the preferred requirements-like file for one profile."""
    for name in ("requirements.lock", "requirements.txt", "requirements.in"):
        candidate = profile_dir / name
        if candidate.exists() and candidate.is_file() and not candidate.is_symlink():
            return candidate
    return None



def _constraints_path(profile_dir: Path) -> Path | None:
    """Return the optional constraints file for one profile."""
    candidate = profile_dir / "constraints.txt"
    if candidate.exists() and candidate.is_file() and not candidate.is_symlink():
        return candidate
    return None



def _profile_state_path(paths: object, profile_name: str) -> Path:
    """Return the private per-profile state file path."""
    return Path(getattr(paths, "profiles_manifests_dir")) / f"{profile_name}.json"



def _profile_exports_dir(paths: object, profile_name: str) -> Path:
    """Return the public exports directory for one profile."""
    return Path(getattr(paths, "public_exports_dir")) / "package_profiles" / profile_name



def _profile_diagnostics_dir(paths: object, profile_name: str) -> Path:
    """Return the public diagnostics directory for one profile."""
    return Path(getattr(paths, "public_diagnostics_dir")) / "package_profiles" / profile_name



def _pip_index_options(runner: object) -> tuple[list[str], list[str]]:
    """Return pip index command options and URLs that should be redacted."""
    opts: list[str] = []
    urls: list[str] = []
    primary = str(getattr(runner, "pip_index_url", "") or "").strip()
    extra = str(getattr(runner, "pip_extra_index_url", "") or "").strip()
    if primary:
        opts += ["--index-url", primary]
        urls.append(primary)
    if extra:
        opts += ["--extra-index-url", extra]
        urls.append(extra)
    for host in list(getattr(runner, "pip_trusted_hosts", []) or []):
        host_value = str(host or "").strip()
        if host_value:
            opts += ["--trusted-host", host_value]
    return (opts, urls)



def _build_env_for_pip(runner: object) -> dict[str, str]:
    """Return the base pip environment for profile builds."""
    env = dict(os.environ)
    if bool(getattr(runner, "package_cache_enabled", True)):
        paths = getattr(runner, "package_store_paths", None)
        cache_dir = getattr(paths, "pip_cache_dir", None)
        if cache_dir is not None:
            env["PIP_CACHE_DIR"] = str(cache_dir)
    return env



def _run_command(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run one subprocess command with captured stdout and stderr files."""
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result: dict[str, Any] = {
        "cmd": list(cmd),
        "rc": None,
        "exec_error": None,
        "duration_seconds": 0.0,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    try:
        with open(stdout_path, "wb") as out_f, open(stderr_path, "wb") as err_f:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=out_f,
                stderr=err_f,
            )
            try:
                result["rc"] = int(proc.wait(timeout=timeout_seconds))
            except subprocess.TimeoutExpired:
                result["exec_error"] = "timeout"
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
    except Exception as exc:
        result["exec_error"] = str(exc)
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    return result



def _status_from_result(result: dict[str, Any]) -> str:
    """Collapse one subprocess result into a compact status string."""
    if result.get("exec_error") == "timeout":
        return "timeout"
    if result.get("exec_error"):
        return "error"
    if int(result.get("rc", 1) or 0) == 0:
        return "ok"
    return f"rc_{int(result.get('rc') or 0)}"



def _read_text(path: Path) -> str:
    """Read text from one path best-effort."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""



def build_profile_environment_key(runner: object, profile_name: str, requirements_path: Path, constraints_path: Path | None) -> str:
    """Return the deterministic reusable-environment key for one profile."""
    payload: dict[str, Any] = {
        "profile_name": str(profile_name),
        "requirements_sha256": package_envs.requirements_sha256(requirements_path),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "machine": os.uname().machine if hasattr(os, "uname") else "",
        "platform": sys.platform,
        "dependency_mode": "profile",
        "require_hashes": bool(getattr(runner, "package_require_hashes", False)),
        "offline_prefer_local": bool(getattr(runner, "package_offline_prefer_local", True)),
        "pip_index_url": str(getattr(runner, "pip_index_url", "") or ""),
        "pip_extra_index_url": str(getattr(runner, "pip_extra_index_url", "") or ""),
        "pip_trusted_hosts": list(getattr(runner, "pip_trusted_hosts", []) or []),
    }
    if constraints_path is not None:
        payload["constraints_sha256"] = package_envs.requirements_sha256(constraints_path)
    return package_envs.build_environment_key_from_payload(payload)





def _normalise_options_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Normalise grouped add-on options into the flat runtime shape."""
    if not isinstance(data, dict):
        return {}
    groups = {
        "security",
        "runner",
        "jobs",
        "resources",
        "python",
        "notifications",
        "artefacts",
        "housekeeping",
        "telemetry",
    }
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if key in groups and isinstance(value, dict):
            continue
        flat[key] = value
    for group in groups:
        value = data.get(group)
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if key not in flat:
                flat[key] = item
    return flat


def _profile_summary_from_dir(runner: object, profile_dir: Path) -> dict[str, Any] | None:
    """Return the discovered metadata for one public package profile directory."""
    if not profile_dir.exists() or not profile_dir.is_dir() or profile_dir.is_symlink():
        return None
    profile_name = _safe_profile_name(profile_dir.name)
    if not profile_name:
        return None

    manifest_path, manifest = _read_profile_manifest(profile_dir)
    requirements_path = _requirements_path(profile_dir)
    constraints_path = _constraints_path(profile_dir)
    paths = getattr(runner, "package_store_paths", None)
    state_path = _profile_state_path(paths, profile_name) if paths is not None else None
    state_payload = _read_json(state_path, {}) if state_path is not None else {}

    requirements_sha256 = package_envs.requirements_sha256(requirements_path) if requirements_path is not None else None
    environment_key = build_profile_environment_key(runner, profile_name, requirements_path, constraints_path) if requirements_path is not None else None
    venv_path = package_envs.venv_dir(paths, environment_key) if (paths is not None and environment_key is not None) else None
    ready = bool(venv_path is not None and package_envs.is_ready_venv(venv_path))

    display_name = str(manifest.get("display_name") or profile_name.replace("_", " ").replace("-", " ").title())
    summary = {
        "name": profile_name,
        "display_name": display_name,
        "dir": str(profile_dir),
        "manifest_path": str(manifest_path) if manifest_path is not None else None,
        "requirements_path": str(requirements_path) if requirements_path is not None else None,
        "requirements_kind": requirements_path.name if requirements_path is not None else None,
        "constraints_path": str(constraints_path) if constraints_path is not None else None,
        "requirements_sha256": requirements_sha256,
        "environment_key": environment_key,
        "venv_path": str(venv_path) if venv_path is not None else None,
        "ready": ready,
        "status": "ready" if ready else ("needs_rebuild" if str(state_payload.get("status") or "") == "ready" else str(state_payload.get("status") or "not_built")),
        "last_build_utc": state_payload.get("last_build_utc"),
        "last_error": state_payload.get("last_error"),
        "exports_dir": str(_profile_exports_dir(paths, profile_name)) if paths is not None else None,
        "diagnostics_dir": str(_profile_diagnostics_dir(paths, profile_name)) if paths is not None else None,
    }
    if manifest:
        summary["manifest"] = manifest
    return summary



def setup_status(
    runner: object,
    *,
    target_profile: str = DEFAULT_SETUP_TARGET_PROFILE,
    target_wheel: str = DEFAULT_SETUP_TARGET_WHEEL,
) -> dict[str, Any]:
    """Return read-only readiness for the guided profile-setup flow."""
    paths = getattr(runner, "package_store_paths", None)
    if paths is None:
        return {
            "status": "error",
            "error": "package_store_unavailable",
            "target_profile": str(target_profile or DEFAULT_SETUP_TARGET_PROFILE),
            "target_wheel": str(target_wheel or DEFAULT_SETUP_TARGET_WHEEL),
            "wheel_present": False,
            "wheel_files": [],
            "profile_present": False,
            "profile_names": [],
            "default_profile": str(getattr(runner, "package_profile_default", "") or ""),
            "default_profile_exists": False,
            "install_requirements_enabled": bool(getattr(runner, "install_requirements", False)),
            "dependency_mode": str(getattr(runner, "dependency_mode", "per_job") or "per_job"),
            "package_profiles_enabled": bool(getattr(runner, "package_profiles_enabled", True)),
            "package_allow_public_wheelhouse": bool(getattr(runner, "package_allow_public_wheelhouse", True)),
            "package_offline_prefer_local": bool(getattr(runner, "package_offline_prefer_local", True)),
            "venv_reuse_enabled": bool(getattr(runner, "venv_reuse_enabled", True)),
            "profile_built": False,
            "profile_build_available": False,
            "ready_for_example_5": False,
            "blockers": ["Package storage is unavailable."],
            "warnings": [],
            "next_steps": ["Restart the add-on and check package storage initialisation."],
        }

    inventory = list_profiles(runner)
    profiles = list(inventory.get("profiles") or [])
    profile_names = [str(item.get("name") or "") for item in profiles if str(item.get("name") or "")]
    safe_target_profile = _safe_profile_name(target_profile) or DEFAULT_SETUP_TARGET_PROFILE
    target_wheel_name = str(target_wheel or DEFAULT_SETUP_TARGET_WHEEL).strip() or DEFAULT_SETUP_TARGET_WHEEL

    runtime_default_profile = str(getattr(runner, "package_profile_default", "") or "").strip()
    runtime_dependency_mode = str(getattr(runner, "dependency_mode", "per_job") or "per_job")
    runtime_install_requirements = bool(getattr(runner, "install_requirements", False))
    runtime_package_profiles_enabled = bool(getattr(runner, "package_profiles_enabled", True))
    runtime_package_allow_public_wheelhouse = bool(getattr(runner, "package_allow_public_wheelhouse", True))
    runtime_package_offline_prefer_local = bool(getattr(runner, "package_offline_prefer_local", True))
    runtime_venv_reuse_enabled = bool(getattr(runner, "venv_reuse_enabled", True))

    raw_options_path = Path(getattr(runner, "options_path", Path("/data/options.json")))
    stored_flat = _normalise_options_payload(_read_json(raw_options_path, {})) if raw_options_path else {}
    stored_default_profile = str(stored_flat.get("package_profile_default") or runtime_default_profile).strip()
    stored_dependency_mode = str(stored_flat.get("dependency_mode") or runtime_dependency_mode or "per_job")
    stored_install_requirements = bool(stored_flat.get("install_requirements", runtime_install_requirements))
    stored_package_profiles_enabled = bool(stored_flat.get("package_profiles_enabled", runtime_package_profiles_enabled))
    stored_package_allow_public_wheelhouse = bool(stored_flat.get("package_allow_public_wheelhouse", runtime_package_allow_public_wheelhouse))
    stored_package_offline_prefer_local = bool(stored_flat.get("package_offline_prefer_local", runtime_package_offline_prefer_local))
    stored_venv_reuse_enabled = bool(stored_flat.get("venv_reuse_enabled", runtime_venv_reuse_enabled))

    def _persistent_mode_matches(
        install_requirements: bool,
        dependency_mode: str,
        package_profiles_enabled: bool,
        default_profile: str,
        package_allow_public_wheelhouse: bool,
        package_offline_prefer_local: bool,
        venv_reuse_enabled: bool,
    ) -> bool:
        return bool(
            install_requirements
            and dependency_mode == "profile"
            and package_profiles_enabled
            and default_profile == safe_target_profile
            and package_allow_public_wheelhouse
            and package_offline_prefer_local
            and venv_reuse_enabled
        )

    persistent_packages_running = _persistent_mode_matches(
        runtime_install_requirements,
        runtime_dependency_mode,
        runtime_package_profiles_enabled,
        runtime_default_profile,
        runtime_package_allow_public_wheelhouse,
        runtime_package_offline_prefer_local,
        runtime_venv_reuse_enabled,
    )
    persistent_packages_saved = _persistent_mode_matches(
        stored_install_requirements,
        stored_dependency_mode,
        stored_package_profiles_enabled,
        stored_default_profile,
        stored_package_allow_public_wheelhouse,
        stored_package_offline_prefer_local,
        stored_venv_reuse_enabled,
    )

    wheel_dir = Path(getattr(paths, "public_wheel_uploads_dir"))
    wheel_files: list[str] = []
    if wheel_dir.exists() and wheel_dir.is_dir() and not wheel_dir.is_symlink():
        for child in sorted(wheel_dir.iterdir(), key=lambda item: item.name.lower()):
            try:
                if child.is_file() and not child.is_symlink() and child.name.endswith('.whl'):
                    wheel_files.append(child.name)
            except OSError:
                continue

    selected_profile = next((item for item in profiles if str(item.get("name") or "") == safe_target_profile), None)
    default_profile_exists = bool(runtime_default_profile and runtime_default_profile in profile_names)
    wheel_present = target_wheel_name in wheel_files
    profile_present = selected_profile is not None
    profile_built = bool(selected_profile and selected_profile.get("ready") is True)
    profile_build_available = bool(profile_present and runtime_package_profiles_enabled)

    blockers: list[str] = []
    warnings: list[str] = []
    next_steps: list[str] = []

    if persistent_packages_saved and not persistent_packages_running:
        blockers.append("Persistent package defaults are saved but the running add-on has not loaded them yet.")
        next_steps.append("Restart the add-on, then refresh Setup.")
    else:
        if not runtime_install_requirements:
            blockers.append("Enable Install requirements.txt automatically in the add-on config.")
            next_steps.append("Use Enable persistent packages to save the recommended settings, or turn on Install requirements.txt automatically manually.")
        if not runtime_package_profiles_enabled:
            blockers.append("Enable package profiles in the add-on config.")
            next_steps.append("Use Enable persistent packages to save the recommended settings, or turn on package profile support manually.")
        if runtime_dependency_mode != 'profile':
            blockers.append("Switch Dependency handling mode to profile for persistent packages.")
            next_steps.append("Use Enable persistent packages to save the recommended settings, or set Dependency handling mode to profile manually.")
        if runtime_default_profile != safe_target_profile:
            blockers.append(f"Set the default package profile to {safe_target_profile}.")
            next_steps.append(f"Use Enable persistent packages to save the recommended settings, or set package_profile_default to {safe_target_profile} manually.")
        elif not default_profile_exists:
            blockers.append(f"The configured default package profile {safe_target_profile} was not found under /config/package_profiles.")
    if not wheel_present:
        blockers.append(f"Upload {target_wheel_name} into {wheel_dir}.")
        next_steps.append(f"Add {target_wheel_name} to {wheel_dir} so the demo profile can build locally.")
    if not profile_present:
        blockers.append(f"Create the profile folder {safe_target_profile} under {Path(getattr(paths, 'public_profiles_dir'))}.")
        next_steps.append(f"Add /config/package_profiles/{safe_target_profile}/requirements.txt and manifest.json.")

    target_profile_status = str(selected_profile.get("status") or "not_built") if selected_profile is not None else "missing"
    target_profile_last_error = str(selected_profile.get("last_error") or "").strip() if selected_profile is not None else ""
    build_available = bool(profile_present and runtime_package_profiles_enabled)
    rebuild_available = build_available
    build_recommended = bool(profile_present and runtime_package_profiles_enabled and not profile_built)

    if profile_present and not profile_built:
        warnings.append(f"Profile {safe_target_profile} exists but has not been built yet.")
        next_steps.append(f"Build {safe_target_profile} from this Setup page, or let example 5 build it on first use.")
    if wheel_present and not runtime_package_allow_public_wheelhouse:
        blockers.append("Enable public wheelhouse support so uploaded wheels are available during profile builds.")
        next_steps.append("Use Enable persistent packages to save the recommended settings, or turn on public wheelhouse support manually.")
    if wheel_present and not runtime_package_offline_prefer_local:
        warnings.append("Offline prefer local is disabled, so pip may use the remote index before local wheels.")
    if profile_present and selected_profile is not None and str(selected_profile.get('status') or '') in {'error', 'needs_rebuild'}:
        if target_profile_last_error:
            warnings.append(f"The last profile build failed: {target_profile_last_error}")
        next_steps.append(f"Rebuild {safe_target_profile} from this Setup page and inspect the diagnostics bundle if it fails again.")

    restart_required = bool(persistent_packages_saved and not persistent_packages_running)

    ready_for_example_5 = bool(
        wheel_present
        and profile_present
        and profile_built
        and persistent_packages_running
        and target_profile_status == "ready"
    )

    if profile_present and target_profile_status in {"error", "needs_rebuild"}:
        ready_state = "build_failed"
    elif restart_required:
        ready_state = "restart_required"
    elif not wheel_present or not profile_present:
        ready_state = "content_missing"
    elif build_recommended:
        ready_state = "build_recommended"
    elif ready_for_example_5:
        ready_state = "ready"
    else:
        ready_state = "not_ready"

    if not next_steps:
        if ready_state == "ready":
            next_steps.append("Persistent packages are ready to use.")
        elif ready_state == "build_recommended":
            next_steps.append(f"Build {safe_target_profile} now for a cleaner first persistent-package run.")
        else:
            next_steps.append("Refresh Setup after the next change to confirm the current state.")

    restart_guidance = (
        "Persistent package defaults are saved. Restart the add-on, then refresh Setup."
        if restart_required
        else (
            f"Build {safe_target_profile} now, or let the first persistent-package run build it on demand."
            if build_recommended
            else (
                "Persistent packages are ready to use from Pythonista."
                if ready_for_example_5
                else "Refresh Setup after the next change to confirm the current state."
            )
        )
    )

    persistent_mode_summary = (
        "Persistent packages are enabled in the running add-on."
        if persistent_packages_running
        else (
            "Persistent package defaults are saved and will apply after the next add-on restart."
            if persistent_packages_saved
            else "Use Enable persistent packages to save the recommended settings in one step."
        )
    )

    next_steps = list(dict.fromkeys(step for step in next_steps if step))
    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))

    payload: dict[str, Any] = {
        "status": "ok",
        "target_profile": safe_target_profile,
        "target_wheel": target_wheel_name,
        "wheel_present": wheel_present,
        "wheel_files": wheel_files,
        "profile_present": profile_present,
        "profile_names": profile_names,
        "default_profile": runtime_default_profile,
        "default_profile_exists": default_profile_exists,
        "install_requirements_enabled": runtime_install_requirements,
        "dependency_mode": runtime_dependency_mode,
        "package_profiles_enabled": runtime_package_profiles_enabled,
        "package_allow_public_wheelhouse": runtime_package_allow_public_wheelhouse,
        "package_offline_prefer_local": runtime_package_offline_prefer_local,
        "venv_reuse_enabled": runtime_venv_reuse_enabled,
        "stored_default_profile": stored_default_profile,
        "stored_install_requirements_enabled": stored_install_requirements,
        "stored_dependency_mode": stored_dependency_mode,
        "stored_package_profiles_enabled": stored_package_profiles_enabled,
        "stored_package_allow_public_wheelhouse": stored_package_allow_public_wheelhouse,
        "stored_package_offline_prefer_local": stored_package_offline_prefer_local,
        "stored_venv_reuse_enabled": stored_venv_reuse_enabled,
        "persistent_packages_running": persistent_packages_running,
        "persistent_packages_saved": persistent_packages_saved,
        "persistent_packages_apply_available": not persistent_packages_saved,
        "persistent_mode_summary": persistent_mode_summary,
        "profile_built": profile_built,
        "profile_build_available": profile_build_available,
        "build_available": build_available,
        "rebuild_available": rebuild_available,
        "build_recommended": build_recommended,
        "target_profile_status": target_profile_status,
        "target_profile_last_error": target_profile_last_error,
        "restart_required": restart_required,
        "restart_guidance": restart_guidance,
        "ready_state": ready_state,
        "config_snippet": _setup_config_snippet(safe_target_profile),
        "ready_for_example_5": ready_for_example_5,
        "blockers": blockers,
        "warnings": warnings,
        "next_steps": next_steps,
        "paths": {
            "wheel_uploads_dir": str(wheel_dir),
            "profiles_dir": str(getattr(paths, "public_profiles_dir")),
        },
        "inventory": {
            "profile_count": int(inventory.get("profile_count", 0) or 0),
            "ready_count": int(inventory.get("ready_count", 0) or 0),
        },
    }
    if selected_profile is not None:
        payload["target_profile_summary"] = selected_profile
    return payload


def _profile_upload_max_bytes(runner: object) -> int:
    """Return the maximum accepted profile archive size for one upload."""
    max_upload_mb = max(1, int(getattr(runner, "max_upload_mb", 50) or 50))
    return max_upload_mb * 1024 * 1024


def _safe_upload_filename(name: str, *, expected_suffix: str) -> str:
    """Return a safe single upload filename or an empty string."""
    value = str(name or "").strip()
    if not value:
        return ""
    basename = Path(value).name
    if value != basename:
        return ""
    suffix = str(expected_suffix or "").lower()
    if suffix and not basename.lower().endswith(suffix):
        return ""
    if any(part in {"", ".", ".."} for part in PurePosixPath(basename).parts):
        return ""
    return basename


def _zip_info_is_symlink(info: zipfile.ZipInfo) -> bool:
    """Return whether one zip entry encodes a symbolic link."""
    mode = (int(info.external_attr) >> 16) & 0xFFFF
    return stat.S_ISLNK(mode)


def _safe_archive_parts(name: str) -> list[str]:
    """Return validated archive path parts or an empty list when invalid."""
    value = str(name or "").replace('\\', '/')
    parts = [part for part in PurePosixPath(value).parts if part not in {"", "."}]
    if not parts:
        return []
    if parts[0].startswith('/'):
        return []
    if any(part == '..' for part in parts):
        return []
    return list(parts)


def _profile_name_from_manifest(manifest_path: Path, fallback_filename: str) -> str:
    """Return one safe profile name derived from manifest content or filename."""
    manifest_payload = _read_json(manifest_path, {})
    candidates = [
        manifest_payload.get('profile_name') if isinstance(manifest_payload, dict) else None,
        manifest_payload.get('name') if isinstance(manifest_payload, dict) else None,
        Path(str(fallback_filename or '')).stem,
    ]
    for candidate in candidates:
        safe_name = _safe_profile_name(str(candidate or ''))
        if safe_name:
            return safe_name
    return ''


def _extract_profile_zip_to_temp(upload_path: Path, temp_root: Path, upload_filename: str) -> tuple[str | None, Path | None, dict[str, Any]]:
    """Inspect and extract one profile archive into a temporary directory tree."""
    summary: dict[str, Any] = {
        'entry_count': 0,
        'file_count': 0,
        'dir_count': 0,
        'total_uncompressed_bytes': 0,
        'archive_layout': None,
    }
    max_entries = 512
    max_uncompressed_bytes = 128 * 1024 * 1024
    try:
        with zipfile.ZipFile(upload_path, 'r') as zf:
            infos = zf.infolist()
            if not infos:
                return ('empty_archive', None, summary)
            summary['entry_count'] = len(infos)
            if len(infos) > max_entries:
                return ('too_many_entries', None, summary)

            root_names: set[str] = set()
            has_top_level_files = False
            for info in infos:
                if _zip_info_is_symlink(info):
                    return ('symlink_member_rejected', None, summary)
                parts = _safe_archive_parts(info.filename)
                if not parts:
                    return ('suspicious_archive_path', None, summary)
                if info.is_dir():
                    summary['dir_count'] += 1
                    continue
                summary['file_count'] += 1
                summary['total_uncompressed_bytes'] = int(summary['total_uncompressed_bytes']) + int(info.file_size)
                if int(summary['total_uncompressed_bytes']) > max_uncompressed_bytes:
                    return ('archive_unpacked_too_large', None, summary)
                if len(parts) == 1:
                    has_top_level_files = True
                else:
                    root_names.add(parts[0])

            if int(summary['file_count']) <= 0:
                return ('empty_archive', None, summary)
            if not has_top_level_files and len(root_names) > 1:
                return ('ambiguous_profile_root', None, summary)

            if has_top_level_files:
                summary['archive_layout'] = 'flat'
                scratch_dir = temp_root / '__profile_flat__'
                scratch_dir.mkdir(parents=True, exist_ok=True)
                for info in infos:
                    parts = _safe_archive_parts(info.filename)
                    target_path = scratch_dir.joinpath(*parts)
                    if info.is_dir():
                        target_path.mkdir(parents=True, exist_ok=True)
                        continue
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, 'r') as src, target_path.open('wb') as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                manifest_path = scratch_dir / 'manifest.json'
                if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
                    return ('profile_manifest_missing', None, summary)
                profile_name = _profile_name_from_manifest(manifest_path, upload_filename)
                if not profile_name:
                    return ('invalid_profile_name', None, summary)
                final_dir = temp_root / profile_name
                scratch_dir.rename(final_dir)
                return (None, final_dir, summary)

            summary['archive_layout'] = 'rooted'
            root_name = next(iter(root_names)) if root_names else ''
            profile_name = _safe_profile_name(root_name)
            if not profile_name:
                return ('invalid_profile_name', None, summary)
            for info in infos:
                parts = _safe_archive_parts(info.filename)
                target_path = temp_root.joinpath(*parts)
                if info.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                    continue
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, 'r') as src, target_path.open('wb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
            return (None, temp_root / profile_name, summary)
    except zipfile.BadZipFile:
        return ('invalid_zip', None, summary)


def upload_profile_zip(
    runner: object,
    upload_path: Path,
    *,
    filename: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate and store one uploaded package profile archive."""
    paths = getattr(runner, 'package_store_paths', None)
    requested_filename = str(filename or '').strip()
    safe_filename = _safe_upload_filename(requested_filename, expected_suffix='.zip')
    result: dict[str, Any] = {
        'status': 'error',
        'requested_filename': requested_filename,
        'filename': safe_filename,
        'overwrite': bool(overwrite),
        'profiles_dir': str(getattr(paths, 'public_profiles_dir', '')) if paths is not None else '',
    }
    if paths is None:
        result['error'] = 'package_store_unavailable'
        return result
    if not safe_filename:
        result['error'] = 'invalid_profile_zip_filename'
        return result
    try:
        if not upload_path.exists() or not upload_path.is_file() or upload_path.is_symlink():
            result['error'] = 'upload_missing'
            return result
    except OSError:
        result['error'] = 'upload_missing'
        return result

    max_upload_bytes = _profile_upload_max_bytes(runner)
    try:
        size_bytes = int(upload_path.stat().st_size)
    except OSError:
        result['error'] = 'upload_missing'
        return result
    result['size_bytes'] = size_bytes
    result['max_upload_bytes'] = max_upload_bytes
    if size_bytes <= 0:
        result['error'] = 'empty_upload'
        return result
    if size_bytes > max_upload_bytes:
        result['error'] = 'upload_too_large'
        return result

    public_profiles_dir = Path(getattr(paths, 'public_profiles_dir'))
    try:
        public_profiles_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        result['error'] = 'profiles_dir_unavailable'
        return result
    if not public_profiles_dir.exists() or not public_profiles_dir.is_dir() or public_profiles_dir.is_symlink():
        result['error'] = 'profiles_dir_unavailable'
        return result

    temp_root = Path(tempfile.mkdtemp(prefix='.profile_upload_', dir=str(public_profiles_dir)))
    backup_dir: Path | None = None
    try:
        extract_error, extracted_dir, extract_summary = _extract_profile_zip_to_temp(upload_path, temp_root, safe_filename)
        result['archive'] = extract_summary
        if extract_error:
            result['error'] = extract_error
            return result
        if extracted_dir is None:
            result['error'] = 'profile_extract_failed'
            return result
        manifest_path = extracted_dir / 'manifest.json'
        requirements_path = _requirements_path(extracted_dir)
        if not manifest_path.exists() or not manifest_path.is_file() or manifest_path.is_symlink():
            result['error'] = 'profile_manifest_missing'
            return result
        if requirements_path is None:
            result['error'] = 'profile_requirements_missing'
            return result
        profile_name = _safe_profile_name(extracted_dir.name)
        if not profile_name:
            result['error'] = 'invalid_profile_name'
            return result

        dest_dir = public_profiles_dir / profile_name
        result['profile_name'] = profile_name
        result['dest_path'] = str(dest_dir)
        existed_before = dest_dir.exists()
        if existed_before:
            try:
                if dest_dir.is_symlink() or not dest_dir.is_dir():
                    result['error'] = 'existing_profile_path_invalid'
                    return result
            except OSError:
                result['error'] = 'existing_profile_path_invalid'
                return result
            if not overwrite:
                result['error'] = 'already_exists'
                return result
            backup_dir = public_profiles_dir / f'.{profile_name}.backup'
            counter = 0
            while backup_dir.exists():
                counter += 1
                backup_dir = public_profiles_dir / f'.{profile_name}.backup.{counter}'
            dest_dir.rename(backup_dir)

        extracted_dir.rename(dest_dir)
        if backup_dir is not None:
            shutil.rmtree(backup_dir, ignore_errors=True)
        shutil.rmtree(temp_root, ignore_errors=True)
        manifest_payload = _read_json(dest_dir / 'manifest.json', {})
        result.update({
            'status': 'ok',
            'action': 'overwritten' if existed_before else 'uploaded',
            'manifest': manifest_payload if isinstance(manifest_payload, dict) else {},
            'requirements_kind': str(Path(requirements_path).name),
            'inventory': list_profiles(runner),
            'setup_status': setup_status(runner, target_profile=profile_name),
        })
        return result
    except Exception:
        if backup_dir is not None and not (public_profiles_dir / str(result.get('profile_name') or '')).exists():
            try:
                backup_dir.rename(public_profiles_dir / str(result.get('profile_name') or ''))
            except Exception:
                pass
        raise
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def delete_uploaded_profile(runner: object, profile_name: str) -> dict[str, Any]:
    """Delete one uploaded public package profile and its cached build artefacts."""
    paths = getattr(runner, 'package_store_paths', None)
    requested_name = str(profile_name or '').strip()
    safe_name = _safe_profile_name(requested_name)
    result: dict[str, Any] = {
        'status': 'error',
        'requested_profile_name': requested_name,
        'profile_name': safe_name,
        'profiles_dir': str(getattr(paths, 'public_profiles_dir', '')) if paths is not None else '',
    }
    if paths is None:
        result['error'] = 'package_store_unavailable'
        return result
    if not safe_name:
        result['error'] = 'invalid_profile_name'
        return result

    public_profiles_dir = Path(getattr(paths, 'public_profiles_dir'))
    dest_dir = public_profiles_dir / safe_name
    result['dest_path'] = str(dest_dir)
    try:
        if not dest_dir.exists():
            result['error'] = 'not_found'
            return result
        if dest_dir.is_symlink() or not dest_dir.is_dir():
            result['error'] = 'existing_profile_path_invalid'
            return result
    except OSError:
        result['error'] = 'existing_profile_path_invalid'
        return result

    summary = _profile_summary_from_dir(runner, dest_dir) or {}
    environment_key = str(summary.get('environment_key') or '')
    active_keys_fn = getattr(runner, 'active_package_environment_keys', None)
    active_keys = []
    if callable(active_keys_fn):
        try:
            active_keys = list(active_keys_fn() or [])
        except Exception:
            active_keys = []
    if environment_key and environment_key in active_keys:
        result['error'] = 'profile_in_use'
        result['environment_key'] = environment_key
        return result

    removed_paths: list[str] = []
    package_envs.remove_tree(dest_dir)
    removed_paths.append(str(dest_dir))

    state_path = _profile_state_path(paths, safe_name)
    try:
        if state_path.exists() and state_path.is_file() and not state_path.is_symlink():
            state_path.unlink()
            removed_paths.append(str(state_path))
    except Exception:
        pass

    exports_dir = _profile_exports_dir(paths, safe_name)
    if exports_dir.exists() and exports_dir.is_dir() and not exports_dir.is_symlink():
        package_envs.remove_tree(exports_dir)
        removed_paths.append(str(exports_dir))

    diagnostics_dir = _profile_diagnostics_dir(paths, safe_name)
    if diagnostics_dir.exists() and diagnostics_dir.is_dir() and not diagnostics_dir.is_symlink():
        package_envs.remove_tree(diagnostics_dir)
        removed_paths.append(str(diagnostics_dir))

    removed_venv = False
    if environment_key:
        venv_path = package_envs.venv_dir(paths, environment_key)
        if venv_path.exists() and venv_path.is_dir() and not venv_path.is_symlink():
            package_envs.remove_tree(venv_path)
            removed_paths.append(str(venv_path))
            removed_venv = True
        staging_path = package_envs.staging_venv_dir(paths, environment_key)
        if staging_path.exists() and staging_path.is_dir() and not staging_path.is_symlink():
            package_envs.remove_tree(staging_path)
            removed_paths.append(str(staging_path))
        try:
            payload = package_envs.read_venv_index(paths)
            items = payload.get('items') if isinstance(payload, dict) else []
            if isinstance(items, list):
                payload['items'] = [item for item in items if str((item or {}).get('environment_key') or '') != environment_key]
                package_envs.write_venv_index(paths, payload)
        except Exception:
            pass

    result.update({
        'status': 'ok',
        'action': 'deleted',
        'removed_paths': removed_paths,
        'removed_cached_venv': bool(removed_venv),
        'inventory': list_profiles(runner),
        'setup_status': setup_status(runner, target_profile=safe_name),
    })
    if environment_key:
        result['environment_key'] = environment_key
    return result


def list_profiles(runner: object) -> dict[str, Any]:
    """Return the current public package profile inventory."""
    paths = getattr(runner, "package_store_paths", None)
    profiles: list[dict[str, Any]] = []
    if paths is not None:
        public_dir = Path(getattr(paths, "public_profiles_dir"))
        if public_dir.exists() and public_dir.is_dir() and not public_dir.is_symlink():
            for child in sorted(public_dir.iterdir(), key=lambda p: p.name):
                profile = _profile_summary_from_dir(runner, child)
                if profile is not None:
                    profiles.append(profile)
    default_profile = str(getattr(runner, "package_profile_default", "") or "").strip()
    return {
        "enabled": bool(getattr(runner, "package_profiles_enabled", True)),
        "dependency_mode": str(getattr(runner, "dependency_mode", "per_job") or "per_job"),
        "default_profile": default_profile,
        "profiles": profiles,
        "profile_count": len(profiles),
        "ready_count": sum(1 for item in profiles if item.get("ready") is True),
    }



def _write_bundle(zip_path: Path, items: list[tuple[Path, str]]) -> None:
    """Write one zip bundle containing the supplied files."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arcname in items:
            try:
                if not src.exists() or not src.is_file() or src.is_symlink():
                    continue
            except OSError:
                continue
            zf.write(src, arcname)



def _export_profile_artifacts(
    paths: object,
    *,
    profile_name: str,
    requirements_path: Path,
    constraints_path: Path | None,
    state_payload: dict[str, Any],
    diagnostics_files: list[Path],
) -> dict[str, Any]:
    """Export effective lock and diagnostics for one profile build."""
    exports_dir = _profile_exports_dir(paths, profile_name)
    diagnostics_dir = _profile_diagnostics_dir(paths, profile_name)
    exports_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    effective_name = "effective_requirements.lock" if requirements_path.name == "requirements.lock" else "effective_requirements.txt"
    effective_path = exports_dir / effective_name
    shutil.copy2(requirements_path, effective_path)

    copied_files: list[Path] = [effective_path]
    if constraints_path is not None:
        constraints_out = exports_dir / "constraints.txt"
        shutil.copy2(constraints_path, constraints_out)
        copied_files.append(constraints_out)

    status_path = diagnostics_dir / "profile_status.json"
    _write_json(status_path, state_payload)
    copied_files.append(status_path)

    for src in diagnostics_files:
        if not src.exists() or not src.is_file() or src.is_symlink():
            continue
        dest = diagnostics_dir / src.name
        same_file = False
        if dest.exists():
            try:
                same_file = src.resolve() == dest.resolve()
            except Exception:
                same_file = False
        if not same_file:
            shutil.copy2(src, dest)
        copied_files.append(dest)

    bundle_path = exports_dir / "diagnostics_bundle.zip"
    _write_bundle(bundle_path, [(item, item.name) for item in copied_files])
    return {
        "effective_requirements_path": str(effective_path),
        "diagnostics_dir": str(diagnostics_dir),
        "exports_dir": str(exports_dir),
        "diagnostics_bundle_path": str(bundle_path),
    }



def build_profile(runner: object, profile_name: str | None = None, *, rebuild: bool = False) -> dict[str, Any]:
    """Build or reuse one named package profile and export diagnostics."""
    paths = getattr(runner, "package_store_paths", None)
    if paths is None:
        return {"status": "error", "error": "package_store_unavailable"}
    if not bool(getattr(runner, "package_profiles_enabled", True)):
        return {"status": "error", "error": "package_profiles_disabled"}

    target_name = _safe_profile_name(profile_name or str(getattr(runner, "package_profile_default", "") or ""))
    if not target_name:
        return {"status": "error", "error": "profile_name_required"}

    inventory = list_profiles(runner)
    selected = None
    for item in inventory["profiles"]:
        if str(item.get("name") or "") == target_name:
            selected = item
            break
    if selected is None:
        return {"status": "error", "error": "profile_not_found", "profile_name": target_name, "inventory": inventory}

    requirements_path = Path(str(selected.get("requirements_path") or ""))
    if not requirements_path.exists() or not requirements_path.is_file():
        return {"status": "error", "error": "profile_requirements_missing", "profile_name": target_name}
    constraints_value = str(selected.get("constraints_path") or "").strip()
    constraints_path = Path(constraints_value) if constraints_value else None

    require_hashes = bool(getattr(runner, "package_require_hashes", False) or bool((selected.get("manifest") or {}).get("require_hashes", False)))
    hash_validation = None
    if require_hashes and requirements_path.name == "requirements.lock":
        hash_validation = package_hashes.validate_requirements_lock_hashes(requirements_path)
        if hash_validation.get("status") != "ok":
            return {
                "status": "error",
                "error": "hash_validation_failed",
                "profile_name": target_name,
                "hash_validation": hash_validation,
            }

    if bool(getattr(runner, "package_allow_public_wheelhouse", True)):
        package_store.sync_public_wheel_uploads(
            paths,
            max_import_bytes=package_store.public_wheel_import_max_bytes(getattr(runner, "package_cache_max_mb", 0)),
        )
    find_links_dirs = package_store.find_links_dirs(paths, work_dir=None)
    env_for_pip = _build_env_for_pip(runner)
    index_opts, redaction_urls = _pip_index_options(runner)
    timeout_seconds = max(10, int(getattr(runner, "pip_timeout_seconds", 120) or 120))
    environment_key = str(selected.get("environment_key") or build_profile_environment_key(runner, target_name, requirements_path, constraints_path))
    venv_path = package_envs.venv_dir(paths, environment_key)
    staging_path = package_envs.staging_venv_dir(paths, environment_key)
    diagnostics_dir = _profile_diagnostics_dir(paths, target_name)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    state_path = _profile_state_path(paths, target_name)

    state_payload = {
        "version": 1,
        "profile_name": target_name,
        "display_name": selected.get("display_name"),
        "requirements_path": str(requirements_path),
        "constraints_path": str(constraints_path) if constraints_path is not None else None,
        "requirements_sha256": package_envs.requirements_sha256(requirements_path),
        "environment_key": environment_key,
        "venv_path": str(venv_path),
        "last_build_utc": utc_now(),
        "status": "building",
        "last_error": None,
        "rebuild": bool(rebuild),
        "hash_enforcement": "required" if require_hashes else "disabled",
        "hash_validation": hash_validation,
    }

    if package_envs.is_ready_venv(venv_path) and not rebuild:
        record = package_envs.touch_last_used(paths, environment_key)
        state_payload.update({"status": "ready", "action": "reused", "venv_record": record})
        exports = _export_profile_artifacts(paths, profile_name=target_name, requirements_path=requirements_path, constraints_path=constraints_path, state_payload=state_payload, diagnostics_files=[])
        state_payload.update(exports)
        _write_json(state_path, state_payload)
        return state_payload

    if rebuild:
        package_envs.remove_tree(venv_path)
    package_envs.prepare_staging_dir(staging_path)

    create_cmd = ["python3", "-m", "venv", str(staging_path)]
    create_result = _run_command(
        create_cmd,
        cwd=Path(str(getattr(paths, "private_root"))),
        env=env_for_pip,
        stdout_path=diagnostics_dir / "profile_venv_create_stdout.txt",
        stderr_path=diagnostics_dir / "profile_venv_create_stderr.txt",
        timeout_seconds=timeout_seconds,
    )
    state_payload["venv_create_status"] = _status_from_result(create_result)
    state_payload["venv_create_command"] = " ".join(create_cmd)
    diagnostics_files = [Path(create_result["stdout_path"]), Path(create_result["stderr_path"])]
    if create_result.get("rc") != 0 or create_result.get("exec_error") is not None:
        state_payload["status"] = "error"
        state_payload["last_error"] = redact_pip_text(_read_text(Path(create_result["stderr_path"])) or str(create_result.get("exec_error") or "venv_create_failed"), redaction_urls)
        exports = _export_profile_artifacts(paths, profile_name=target_name, requirements_path=requirements_path, constraints_path=constraints_path, state_payload=state_payload, diagnostics_files=diagnostics_files)
        state_payload.update(exports)
        _write_json(state_path, state_payload)
        package_envs.remove_tree(staging_path)
        return state_payload

    staging_python = package_envs.venv_python_path(staging_path)
    install_cmd = [
        str(staging_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--report",
        str(diagnostics_dir / "profile_pip_install_report.json"),
        "-r",
        str(requirements_path),
    ]
    if constraints_path is not None:
        install_cmd += ["-c", str(constraints_path)]
    for directory in find_links_dirs:
        install_cmd += ["--find-links", str(directory)]
    if require_hashes:
        install_cmd.append("--require-hashes")

    remote_cmd = list(install_cmd) + list(index_opts)
    if bool(getattr(runner, "package_offline_prefer_local", True)) and find_links_dirs:
        local_cmd = list(install_cmd) + ["--no-index"]
        local_result = _run_command(
            local_cmd,
            cwd=requirements_path.parent,
            env=env_for_pip,
            stdout_path=diagnostics_dir / "profile_pip_install_local_stdout.txt",
            stderr_path=diagnostics_dir / "profile_pip_install_local_stderr.txt",
            timeout_seconds=timeout_seconds,
        )
        diagnostics_files.extend([Path(local_result["stdout_path"]), Path(local_result["stderr_path"])])
        state_payload["local_only_status"] = _status_from_result(local_result)
        if local_result.get("rc") == 0 and local_result.get("exec_error") is None:
            install_result = local_result
            state_payload["install_source"] = "local_wheelhouse"
            state_payload["install_command"] = redact_pip_text(" ".join(local_cmd), redaction_urls)
        else:
            install_result = _run_command(
                remote_cmd,
                cwd=requirements_path.parent,
                env=env_for_pip,
                stdout_path=diagnostics_dir / "profile_pip_install_stdout.txt",
                stderr_path=diagnostics_dir / "profile_pip_install_stderr.txt",
                timeout_seconds=timeout_seconds,
            )
            diagnostics_files.extend([Path(install_result["stdout_path"]), Path(install_result["stderr_path"])])
            state_payload["install_source"] = "local_then_remote"
            state_payload["install_command"] = redact_pip_text(" ".join(remote_cmd), redaction_urls)
    else:
        install_result = _run_command(
            remote_cmd,
            cwd=requirements_path.parent,
            env=env_for_pip,
            stdout_path=diagnostics_dir / "profile_pip_install_stdout.txt",
            stderr_path=diagnostics_dir / "profile_pip_install_stderr.txt",
            timeout_seconds=timeout_seconds,
        )
        diagnostics_files.extend([Path(install_result["stdout_path"]), Path(install_result["stderr_path"])] )
        state_payload["install_source"] = "remote_with_find_links" if find_links_dirs else "remote_index"
        state_payload["install_command"] = redact_pip_text(" ".join(remote_cmd), redaction_urls)

    state_payload["install_status"] = _status_from_result(install_result)
    state_payload["install_duration_seconds"] = install_result.get("duration_seconds")
    if install_result.get("rc") != 0 or install_result.get("exec_error") is not None:
        state_payload["status"] = "error"
        state_payload["last_error"] = redact_pip_text(
            _read_text(Path(install_result["stderr_path"])) or str(install_result.get("exec_error") or "pip_install_failed"),
            redaction_urls,
        )
        exports = _export_profile_artifacts(paths, profile_name=target_name, requirements_path=requirements_path, constraints_path=constraints_path, state_payload=state_payload, diagnostics_files=diagnostics_files)
        state_payload.update(exports)
        _write_json(state_path, state_payload)
        package_envs.remove_tree(staging_path)
        return state_payload

    inspect_cmd = [str(staging_python), "-m", "pip", "inspect"]
    inspect_result = _run_command(
        inspect_cmd,
        cwd=requirements_path.parent,
        env=env_for_pip,
        stdout_path=diagnostics_dir / "profile_pip_inspect_report.json",
        stderr_path=diagnostics_dir / "profile_pip_inspect_stderr.txt",
        timeout_seconds=timeout_seconds,
    )
    diagnostics_files.extend([Path(inspect_result["stdout_path"]), Path(inspect_result["stderr_path"])])
    state_payload["inspect_status"] = _status_from_result(inspect_result)
    state_payload["inspect_command"] = " ".join(inspect_cmd)

    if venv_path.exists():
        package_envs.remove_tree(venv_path)
    staging_path.replace(venv_path)
    record = package_envs.upsert_venv_record(
        paths,
        environment_key=environment_key,
        venv_path=venv_path,
        requirements_path=requirements_path,
        install_source=str(state_payload.get("install_source") or "profile_build"),
        status="ready",
    )
    package_envs.touch_last_used(paths, environment_key)
    prune_keep_keys = [environment_key]
    active_keys_getter = getattr(runner, "active_package_environment_keys", None)
    if callable(active_keys_getter):
        try:
            prune_keep_keys.extend(active_keys_getter())
        except Exception:
            pass
    prune_result = package_envs.prune_venvs(paths, max_count=int(getattr(runner, "venv_max_count", 0) or 0), keep_keys=prune_keep_keys)

    state_payload.update(
        {
            "status": "ready",
            "action": "rebuilt" if rebuild else "built",
            "venv_record": record,
            "venv_prune_status": str(prune_result.get("status") or "unknown"),
            "venv_pruned_count": int(prune_result.get("removed", 0) or 0),
            "wheelhouse_total_files": int(package_store.refresh_package_index(paths).get("total_files", 0) or 0),
        }
    )
    cache_prune = package_prune.prune_package_store(runner, reason="profile_build", keep_keys=[environment_key])
    state_payload["package_cache_prune_status"] = str(cache_prune.get("status") or "unknown")
    state_payload["package_cache_pruned_count"] = int(cache_prune.get("removed", 0) or 0)
    state_payload["package_cache_pruned_bytes"] = int(cache_prune.get("removed_bytes", 0) or 0)
    exports = _export_profile_artifacts(paths, profile_name=target_name, requirements_path=requirements_path, constraints_path=constraints_path, state_payload=state_payload, diagnostics_files=diagnostics_files)
    state_payload.update(exports)
    _write_json(state_path, state_payload)
    return state_payload



def attach_profile_for_job(runner: object, env: dict[str, str], package_meta: dict[str, Any]) -> str | None:
    """Build or reuse the configured default package profile for one job."""
    if not bool(getattr(runner, "package_profiles_enabled", True)):
        package_meta["status"] = "error"
        package_meta["reason"] = "package_profiles_disabled"
        return "package_profiles_disabled"

    profile_name = _safe_profile_name(str(getattr(runner, "package_profile_default", "") or ""))
    if not profile_name:
        package_meta["status"] = "error"
        package_meta["reason"] = "package_profile_default_missing"
        return "package_profile_default_missing"

    result = build_profile(runner, profile_name, rebuild=False)
    package_meta["profile_name"] = profile_name
    package_meta["profile_display_name"] = result.get("display_name")
    package_meta["profile_status"] = result.get("status")
    package_meta["profile_requirements_path"] = result.get("requirements_path")
    package_meta["profile_effective_requirements_path"] = result.get("effective_requirements_path")
    package_meta["profile_diagnostics_bundle_path"] = result.get("diagnostics_bundle_path")
    package_meta["environment_key"] = result.get("environment_key")
    package_meta["venv_path"] = result.get("venv_path")
    package_meta["venv_enabled"] = True
    package_meta["venv_status"] = result.get("status")
    package_meta["venv_action"] = result.get("action") or ("reused" if result.get("status") == "ready" else "error")

    if str(result.get("status") or "") != "ready":
        package_meta["status"] = "error"
        package_meta["reason"] = str(result.get("error") or result.get("last_error") or "profile_build_failed")
        return str(package_meta["reason"])

    venv_path_value = str(result.get("venv_path") or "").strip()
    if not venv_path_value:
        package_meta["status"] = "error"
        package_meta["reason"] = "profile_venv_missing"
        return "profile_venv_missing"

    venv_path = Path(venv_path_value)
    if not package_envs.is_ready_venv(venv_path):
        package_meta["status"] = "error"
        package_meta["reason"] = "profile_venv_not_ready"
        return "profile_venv_not_ready"

    package_envs.attach_venv_to_env(env, venv_path)
    package_meta["status"] = "ok"
    package_meta["reason"] = None
    package_meta["install_source"] = "profile_venv"
    package_meta["install_duration_seconds"] = result.get("install_duration_seconds", 0)
    package_meta["inspect_duration_seconds"] = None
    package_meta["venv_reused"] = bool(str(result.get("action") or "") == "reused")
    package_meta["profile_attached"] = True
    return None
