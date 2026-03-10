# Version: 0.6.13-package-profiles.2
"""Package profile discovery, build, and export helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

from runner import package_envs
from runner import package_hashes
from runner import package_prune
from runner import package_store
from runner.redact import redact_pip_text
from utils import utc_now


_PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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
        "status": "ready" if ready else str(state_payload.get("status") or "not_built"),
        "last_build_utc": state_payload.get("last_build_utc"),
        "last_error": state_payload.get("last_error"),
        "exports_dir": str(_profile_exports_dir(paths, profile_name)) if paths is not None else None,
        "diagnostics_dir": str(_profile_diagnostics_dir(paths, profile_name)) if paths is not None else None,
    }
    if manifest:
        summary["manifest"] = manifest
    return summary



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
