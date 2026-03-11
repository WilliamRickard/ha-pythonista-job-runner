# Version: 0.6.13-core.12
from __future__ import annotations

import ipaddress
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
import dataclasses
from dataclasses import dataclass
try:
    import pwd
except ImportError:
    pwd = None  # type: ignore[assignment]
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from runner import deps as _deps
from runner import executor as _executor
from runner import fs_safe as _fs_safe
from runner import hashes as _hashes
from runner import housekeeping as _housekeeping
from runner import notify as _notify
from runner import package_profiles as _package_profiles
from runner import package_prune as _package_prune
from runner import package_store as _package_store
from runner import process as _process
from runner import redact as _redact
from runner import results as _results
from runner import state as _state
from runner import stats as _stats
from runner import store as _store

from audit import actor_from_headers, append_audit_event
from support_bundle import build_support_bundle
from utils import (
    SafeZipLimits,
    TailBuffer,
    clamp_int,
    ip_in_cidrs,
    parse_utc,
    safe_extract_zip_bytes,
    utc_now,
)

ADDON_VERSION = "0.6.13"
print(f"[pythonista_job_runner] runner_core {ADDON_VERSION} loaded")

DATA_DIR = Path("/data")
OPTIONS_PATH = DATA_DIR / "options.json"
JOBS_DIR = DATA_DIR / "jobs"

INGRESS_PROXY_IP = "172.30.32.2"
SUPERVISOR_API = "http://supervisor"
SUPERVISOR_CORE_API = f"{SUPERVISOR_API}/core/api"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


def read_options() -> Dict[str, Any]:
    """Read and normalise options from the Home Assistant add-on options file."""
    if not OPTIONS_PATH.exists():
        return {}
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return _normalise_options(data) if isinstance(data, dict) else {}


def read_raw_options() -> Dict[str, Any]:
    """Read raw add-on options without flattening nested groups."""
    if not OPTIONS_PATH.exists():
        return {}
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _uses_grouped_options(data: Dict[str, Any]) -> bool:
    """Return whether raw options use grouped add-on sections."""
    if not isinstance(data, dict):
        return False
    for key in ("security", "runner", "jobs", "resources", "python", "notifications", "artefacts", "housekeeping", "telemetry"):
        if isinstance(data.get(key), dict):
            return True
    return False


def _merge_python_options(raw_options: Dict[str, Any], python_updates: Dict[str, Any]) -> Dict[str, Any]:
    """Return raw add-on options with python settings updated safely."""
    base = json.loads(json.dumps(raw_options if isinstance(raw_options, dict) else {}))
    if _uses_grouped_options(base) or not base:
        group = dict(base.get("python") or {})
        group.update(dict(python_updates))
        base["python"] = group
        return base
    for key, value in python_updates.items():
        base[key] = value
    return base



def _normalise_options(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise options.json into the flat structure used by the Runner.

    Home Assistant add-ons can present nested configuration groups in the UI. This
    helper accepts both the legacy flat options and the newer grouped options.

    The returned mapping is intentionally flat; grouped keys like `security:` are
    not preserved in the output.
    """
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

    flat: Dict[str, Any] = {}

    # Preserve any legacy flat keys (top-level), excluding group containers.
    for k, v in data.items():
        if k in groups and isinstance(v, dict):
            continue
        flat[k] = v

    # Merge known groups into the top level. Top-level keys take precedence.
    for group in groups:
        v = data.get(group)
        if not isinstance(v, dict):
            continue
        for k, vv in v.items():
            if k not in flat:
                flat[k] = vv

    return flat



def _resolve_user_ids(username: str) -> tuple[Optional[int], Optional[int]]:
    """Return (uid, gid) for username, or (None, None) if unavailable."""
    if not username:
        return (None, None)
    if pwd is None:
        return (None, None)
    try:
        pw = pwd.getpwnam(username)  # type: ignore[attr-defined]
        return (int(pw.pw_uid), int(pw.pw_gid))
    except Exception:
        return (None, None)


@dataclass
class Job:
    job_id: str
    created_utc: str = dataclasses.field(default_factory=utc_now)
    started_utc: Optional[str] = None
    finished_utc: Optional[str] = None
    state: str = "queued"  # queued|running|done|error
    phase: str = "queued"  # queued|running|done|error
    exit_code: Optional[int] = None
    error: Optional[str] = None

    cpu_percent: int = 25
    cpu_limit_mode: str = "single_core"
    cpu_count: int = 1
    cpu_cpulimit_pct: int = 25
    mem_mb: int = 4096
    timeout_seconds: int = 3600
    threads: int = 1

    submitted_by_name: Optional[str] = None
    submitted_by_display_name: Optional[str] = None
    submitted_by_id: Optional[str] = None
    ingress_path: Optional[str] = None
    client_ip: Optional[str] = None
    audit_events: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    input_sha256: Optional[str] = None

    cancel_requested: bool = False

    delete_requested: bool = False

    job_dir: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset")
    work_dir: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset" / "work")

    stdout_path: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset" / "stdout.txt")
    stderr_path: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset" / "stderr.txt")
    status_path: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset" / "status.json")
    result_zip: Path = dataclasses.field(default_factory=lambda: JOBS_DIR / "unset" / "result.zip")

    tail_stdout: TailBuffer = dataclasses.field(default_factory=lambda: TailBuffer(8000))
    tail_stderr: TailBuffer = dataclasses.field(default_factory=lambda: TailBuffer(8000))

    package: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def duration_seconds(self) -> Optional[int]:
        if not self.started_utc:
            return None
        t0 = parse_utc(self.started_utc) or 0.0
        t1 = parse_utc(self.finished_utc) if self.finished_utc else time.time()
        if not t1:
            t1 = time.time()
        d = int(max(0.0, float(t1) - float(t0)))
        return d

    def status_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_utc": self.created_utc,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "duration_seconds": self.duration_seconds(),
            "state": self.state,
            "phase": self.phase,
            "exit_code": self.exit_code,
            "error": self.error,
            "runner_version": ADDON_VERSION,
            "client_ip": self.client_ip,
            "audit_events": self.audit_events,
            "submitted_by": {
                "id": self.submitted_by_id,
                "name": self.submitted_by_name,
                "display_name": self.submitted_by_display_name,
            },
            "limits": {
                "cpu_percent": self.cpu_percent,
                "cpu_limit_mode": self.cpu_limit_mode,
                "cpu_count": self.cpu_count,
                "cpu_cpulimit_pct": self.cpu_cpulimit_pct,
                "mem_mb": self.mem_mb,
                "threads": self.threads,
                "timeout_seconds": self.timeout_seconds,
            },
            "result_filename": self.result_zip.name,
            "input_sha256": self.input_sha256,
            "delete_requested": self.delete_requested,
            "package": self.package,
        }



def _ha_persistent_notification(title: str, message: str, notification_id: Optional[str]) -> None:
    """Send a Home Assistant persistent notification (best-effort)."""
    if not SUPERVISOR_TOKEN:
        return
    url = f"{SUPERVISOR_CORE_API}/services/persistent_notification/create"
    payload: Dict[str, Any] = {"title": title, "message": message}
    if notification_id:
        payload["notification_id"] = notification_id
    data = json.dumps(payload).encode("utf-8")

    req = Request(
        url=url,
        data=data,
        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=10) as resp:  # noqa: S310
            _ = resp.read()
    except Exception:
        return


class Runner:
    """Main coordinator object used by the HTTP API server."""

    def __init__(self, opts: Dict[str, Any], *, start_reaper: bool = True) -> None:
        self._opts = opts

        # These instance attributes capture module-level constants at construction time so
        # tests can monkeypatch runner_core.JOBS_DIR/DATA_DIR/OPTIONS_PATH before creating
        # the Runner and still affect behaviour.
        self.addon_version = ADDON_VERSION
        self.data_dir = DATA_DIR
        self.jobs_dir = JOBS_DIR
        self.options_path = OPTIONS_PATH
        self.ingress_proxy_ip = INGRESS_PROXY_IP

        # Allow runner.store to create Job instances without importing runner_core.
        self.Job = Job

        self.token = str(opts.get("token") or "")
        self.ingress_strict = bool(opts.get("ingress_strict", False))

        self.api_allow_cidrs = [
            str(c).strip()
            for c in (opts.get("api_allow_cidrs") or [])
            if isinstance(c, str) and str(c).strip()
        ]
        self.allow_env = [
            k
            for k in [str(x).strip() for x in (opts.get("allow_env") or []) if isinstance(x, str)]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
        ]
        self.bind_host = str(opts.get("bind_host") or "0.0.0.0").strip() or "0.0.0.0"
        try:
            self.bind_port = int(opts.get("bind_port") or 8787)
        except Exception:
            self.bind_port = 8787
        if not (1 <= self.bind_port <= 65535):
            self.bind_port = 8787

        # Running as root (typical in add-on containers) materially changes the threat model.
        try:
            self._is_root = bool(hasattr(os, "geteuid") and int(os.geteuid()) == 0)
        except Exception:
            self._is_root = False

        self.audit_log_path = self.data_dir / "audit_events.jsonl"
        self._audit_lock = threading.Lock()
        telemetry_opts = opts.get("telemetry") or {}
        # Prefer flattened options for backward compatibility, but fall back to nested telemetry config.
        self.telemetry_mqtt_enabled = bool(
            opts.get(
                "telemetry_mqtt_enabled",
                telemetry_opts.get(
                    "mqtt_enabled",
                    telemetry_opts.get("telemetry_mqtt_enabled", False),
                ),
            )
        )
        self.telemetry_topic_prefix = (
            str(
                opts.get(
                    "telemetry_topic_prefix",
                    telemetry_opts.get(
                        "topic_prefix",
                        telemetry_opts.get("telemetry_topic_prefix", "pythonista_job_runner"),
                    ),
                )
                or "pythonista_job_runner"
            )
            .strip()
            or "pythonista_job_runner"
        )

        self.job_user = str(opts.get("job_user") or "jobrunner").strip() or "jobrunner"
        self._job_uid, self._job_gid = _resolve_user_ids(self.job_user)
        if self._job_uid is None or self._job_gid is None:
            if self._is_root:
                print("WARNING: job_user not found; jobs would run as root", flush=True)
            else:
                print("WARNING: job_user not found; jobs will run as current user", flush=True)

        def _opt_int(name: str, default: int, lo: int, hi: int) -> int:
            """Parse an integer option and clamp to [lo, hi]."""
            v = opts.get(name)
            if v is None:
                return default
            try:
                iv = int(v)
            except (ValueError, TypeError):
                return default
            if iv < lo:
                return lo
            if iv > hi:
                return hi
            return iv

        self.timeout_seconds = _opt_int("timeout_seconds", 3600, 1, 86400)
        self.max_upload_mb = _opt_int("max_upload_mb", 50, 1, 1024)
        self.install_requirements = bool(opts.get("install_requirements", False))
        self.cleanup_min_free_mb = _opt_int("cleanup_min_free_mb", 0, 0, 262144)
        self.pip_timeout_seconds = _opt_int("pip_timeout_seconds", 120, 10, 3600)
        self.pip_index_url = str(opts.get("pip_index_url") or "").strip()
        self.pip_extra_index_url = str(opts.get("pip_extra_index_url") or "").strip()
        self.dependency_mode = str(opts.get("dependency_mode") or "per_job").strip() or "per_job"
        if self.dependency_mode not in {"disabled", "per_job", "profile"}:
            self.dependency_mode = "per_job"
        self.package_cache_enabled = bool(opts.get("package_cache_enabled", True))
        self.package_cache_max_mb = _opt_int("package_cache_max_mb", 2048, 256, 65536)
        self.package_cache_prune_on_start = bool(opts.get("package_cache_prune_on_start", True))
        self.package_profiles_enabled = bool(opts.get("package_profiles_enabled", True))
        self.package_profile_default = str(opts.get("package_profile_default") or "").strip()
        self.package_allow_public_wheelhouse = bool(opts.get("package_allow_public_wheelhouse", True))
        self.package_public_wheelhouse_subdir = _package_store.sanitise_public_subdir(
            str(opts.get("package_public_wheelhouse_subdir") or "wheel_uploads").strip() or "wheel_uploads"
        )
        self.package_require_hashes = bool(opts.get("package_require_hashes", False))
        self.package_offline_prefer_local = bool(opts.get("package_offline_prefer_local", True))
        self.venv_reuse_enabled = bool(opts.get("venv_reuse_enabled", True))
        self.venv_max_count = _opt_int("venv_max_count", 20, 0, 500)

        trusted_hosts: List[str] = []
        for x in (opts.get("pip_trusted_hosts") or []):
            if not isinstance(x, str):
                continue
            host = x.strip()
            if not host:
                continue
            # Basic allowlist: hostnames / IPv4 literals without spaces.
            if re.fullmatch(r"[A-Za-z0-9.\-]+", host):
                trusted_hosts.append(host)
            else:
                print(f"WARNING: Invalid pip_trusted_hosts entry skipped: {x!r}", flush=True)
        self.pip_trusted_hosts = trusted_hosts

        self.default_cpu = _opt_int("default_cpu_percent", 25, 1, 100)
        self.max_cpu = _opt_int("max_cpu_percent", 50, 1, 100)
        if self.max_cpu < self.default_cpu:
            self.max_cpu = self.default_cpu

        self.default_mem = _opt_int("default_mem_mb", 4096, 256, 262144)
        self.max_mem = _opt_int("max_mem_mb", 4096, 256, 262144)
        if self.max_mem < self.default_mem:
            self.max_mem = self.default_mem

        self.max_threads = _opt_int("max_threads", 1, 1, 256)

        self.cpu_limit_mode = str(opts.get("cpu_limit_mode") or "single_core").strip() or "single_core"

        self.max_concurrent_jobs = _opt_int("max_concurrent_jobs", 1, 1, 32)
        self.queue_max_jobs = _opt_int("queue_max_jobs", 10, 1, 1000)

        self.tail_chars = _opt_int("tail_chars", 8000, 0, 1000000)
        self.retention_hours = _opt_int("job_retention_hours", 24, 1, 720)

        self.summary_head_chars = _opt_int("summary_head_chars", 4000, 0, 1000000)
        self.summary_tail_chars = _opt_int("summary_tail_chars", 4000, 0, 1000000)
        self.manifest_sha256 = bool(opts.get("manifest_sha256", False))

        self.outputs_max_files = _opt_int("outputs_max_files", 2000, 0, 1000000)
        self.outputs_max_bytes = _opt_int("outputs_max_bytes", 209715200, 0, 2147483647)

        self.notify_on_completion = bool(opts.get("notify_on_completion", True))
        self.notification_mode = str(opts.get("notification_mode") or "latest").strip() or "latest"
        self.notification_id_prefix = str(opts.get("notification_id_prefix") or "pythonista_job_runner").strip() or "pythonista_job_runner"
        self.notification_excerpt_chars = _opt_int("notification_excerpt_chars", 1200, 0, 10000)

        self.safe_zip_limits = SafeZipLimits(
            max_members=_opt_int("zip_max_members", 2000, 1, 100000),
            max_total_uncompressed=_opt_int("zip_max_total_uncompressed", (200 * 1024 * 1024), 1, 2147483647),
            max_single_uncompressed=_opt_int("zip_max_single_uncompressed", (50 * 1024 * 1024), 1, 2147483647),
        )

        self._pending_slots = 0  # reserved queue slots during new_job initialisation
        self._paused = False
        self._pause_reason = ""
        self._status_write_warned: set[str] = set()

        # Centralised mutable job registry. Tests historically access Runner._jobs and
        # Runner._job_order directly (including reassigning _job_order), so we expose
        # these as properties backed by this registry.
        self._state = _state.create_job_registry()

        # Internal facade for job lifecycle operations.
        self._job_store = _store.JobStore(self, self._state)

        self._sema = threading.Semaphore(max(1, self.max_concurrent_jobs))
        self._last_cleanup_check_ts = 0.0

        # Stats caching
        self._disk_cache_ts = 0.0
        self._disk_cache_free = 0
        self._disk_cache_total = 0
        self._jobs_bytes_cache_ts = 0.0
        self._jobs_bytes_cache = 0

        self._stop_event = threading.Event()
        self._reaper_thread: threading.Thread | None = None
        self._telemetry_queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=256)
        self._telemetry_thread: threading.Thread | None = None

        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.package_store_paths = _package_store.build_package_store_paths(
            self.data_dir,
            public_root=_package_store.PUBLIC_CONFIG_ROOT,
            public_wheelhouse_subdir=self.package_public_wheelhouse_subdir,
        )
        self.package_store_bootstrap = _package_store.bootstrap_package_store(self.package_store_paths)
        self.package_store_permissions = _package_store.ensure_job_user_private_write_access(
            self.package_store_paths,
            uid=self._job_uid,
            gid=self._job_gid,
        )
        self._active_package_env_lock = threading.Lock()
        self._active_package_env_keys: set[str] = set()
        if self.package_cache_prune_on_start:
            try:
                self.package_cache_startup_prune = _package_prune.prune_package_store(self, reason="startup")
            except Exception as e:
                self.package_cache_startup_prune = {"status": "error", "reason": "startup", "error": f"{type(e).__name__}: {e}"}
        else:
            self.package_cache_startup_prune = {"status": "skipped", "reason": "startup_disabled"}
        self._load_jobs_from_disk()
        if start_reaper:
            self._reaper_thread = threading.Thread(target=self._reaper, name="runner-reaper", daemon=True)
            self._reaper_thread.start()

    @property
    def _lock(self) -> threading.Lock:
        return self._state.lock

    @_lock.setter
    def _lock(self, v: threading.Lock) -> None:
        self._state.lock = v

    @property
    def _jobs(self) -> Dict[str, Job]:
        return self._state.jobs  # type: ignore[return-value]

    @_jobs.setter
    def _jobs(self, v: Dict[str, Job]) -> None:
        self._state.jobs = v  # type: ignore[assignment]

    @property
    def _job_order(self) -> List[str]:
        return self._state.job_order

    @_job_order.setter
    def _job_order(self, v: List[str]) -> None:
        self._state.job_order = v

    @property
    def _procs(self) -> Dict[str, Any]:
        return self._state.procs

    @_procs.setter
    def _procs(self, v: Dict[str, Any]) -> None:
        self._state.procs = v

    def _build_job_env(self, threads: int) -> Dict[str, str]:
        return _executor.build_job_env(self, threads)

    def _prepare_work_dir(self, work_dir: Path) -> None:
        return _executor.prepare_work_dir(self, work_dir)

    def _disk_free_bytes(self) -> int:
        return _housekeeping.disk_free_bytes(self)

    def _ensure_min_free_space(self) -> None:
        return _housekeeping.ensure_min_free_space(self)

    def _maybe_install_requirements(self, j: Job, env: Dict[str, str]) -> Optional[str]:
        return _deps.maybe_install_requirements(self, j, env)

    def _get_disk_usage_cached(self, ttl_seconds: int = 5) -> Tuple[int, int]:
        return _stats.get_disk_usage_cached(self, ttl_seconds)

    @staticmethod
    def _dir_size_bytes(root: Path, max_files: int = 200_000) -> int:
        return _stats.dir_size_bytes(root, max_files=max_files)

    def _get_jobs_dir_bytes_cached(self, ttl_seconds: int = 30) -> int:
        return _stats.get_jobs_dir_bytes_cached(self, ttl_seconds)

    def stats_dict(self) -> Dict[str, Any]:
        return _stats.stats_dict(self)

    def list_jobs(self) -> List[Job]:
        return list(self._job_store.list_jobs())  # type: ignore[return-value]

    def get(self, job_id: str) -> Optional[Job]:
        return self._job_store.get_job(job_id)  # type: ignore[return-value]

    def new_job(self, zip_bytes: bytes, headers: Any, client_ip: str) -> Job:
        return self._job_store.new_job(zip_bytes, headers, client_ip)  # type: ignore[return-value]

    def _finalize_delete(self, job_id: str) -> None:
        return self._job_store.finalize_delete(job_id)

    def delete(self, job_id: str, actor: Dict[str, Any] | None = None) -> bool:
        return self._job_store.delete_job(job_id, actor=actor)

    def cancel(self, job_id: str, actor: Dict[str, Any] | None = None) -> bool:
        return self._job_store.cancel_job(job_id, actor=actor)

    def purge(self, states: List[str], older_than_hours: int, dry_run: bool, actor: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return self._job_store.purge_jobs(states, older_than_hours, dry_run, actor=actor)

    def actor_from_request(self, headers: Any, client_ip: str) -> Dict[str, Any]:
        """Extract audit actor metadata from request context."""
        try:
            return actor_from_headers(headers, client_ip, self.ingress_proxy_ip)
        except Exception:
            return {"client_ip": str(client_ip or ""), "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}

    def record_audit_event(self, action: str, actor: Dict[str, Any], job_id: str | None = None, details: Dict[str, Any] | None = None, *, persist_status: bool = False) -> None:
        """Persist audit event and optionally attach it to a job status record."""
        safe_details = details or {}
        event: Dict[str, Any] = {
            "action": str(action),
            "job_id": str(job_id) if job_id else None,
            "actor": actor,
            "details": safe_details,
        }
        append_audit_event(self.audit_log_path, self._audit_lock, event)
        try:
            self.publish_telemetry("audit", {"action": action, "job_id": job_id, "actor": actor, "details": safe_details})
        except Exception as e:
            print(f"WARNING: failed to publish telemetry for audit event {action}: {e}", flush=True)

        if not persist_status or not job_id:
            return
        j = self.get(job_id)
        if j is None:
            return
        j.audit_events.append({
            "action": str(action),
            "actor": actor,
            "details": safe_details,
        })
        if len(j.audit_events) > 20:
            j.audit_events = j.audit_events[-20:]
        try:
            if bool(getattr(j, "delete_requested", False)):
                return
            if not j.job_dir.exists():
                return
        except Exception:
            return
        self._write_status(j)


    def pause_for_backup(self, reason: str = "backup") -> dict[str, object]:
        """Pause acceptance of new jobs for backup operations."""
        self._paused = True
        self._pause_reason = str(reason or "backup")
        return {"paused": True, "reason": self._pause_reason}

    def resume_after_backup(self) -> dict[str, object]:
        """Resume normal job intake after backup operations."""
        self._paused = False
        reason = self._pause_reason
        self._pause_reason = ""
        return {"paused": False, "previous_reason": reason}

    def pause_status(self) -> dict[str, object]:
        """Return current pause state used by backup flow."""
        return {"paused": bool(self._paused), "reason": self._pause_reason}

    def support_bundle_dict(self) -> Dict[str, Any]:
        """Return redacted support-bundle payload for troubleshooting."""
        return build_support_bundle(self)

    def list_package_profiles(self) -> Dict[str, Any]:
        """Return the current package profile inventory."""
        return _package_profiles.list_profiles(self)

    def package_setup_status(self) -> Dict[str, Any]:
        """Return read-only package setup readiness for the guided example flow."""
        return _package_profiles.setup_status(self)

    def upload_package_setup_wheel(
        self,
        upload_path: Path,
        *,
        filename: str,
        overwrite: bool = False,
        actor: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Validate and store one uploaded setup wheel, then record audit details."""
        result = _package_store.upload_public_wheel(
            self.package_store_paths,
            upload_path,
            filename=filename,
            overwrite=overwrite,
            max_upload_bytes=_package_store.public_wheel_import_max_bytes(getattr(self, "package_cache_max_mb", 0)),
            sync_after_upload=True,
        )
        result["setup_status"] = _package_profiles.setup_status(self)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "setup_wheel_upload",
                safe_actor,
                details={
                    "filename": str(result.get("filename") or filename or ""),
                    "overwrite": bool(overwrite),
                    "status": str(result.get("status") or "error"),
                    "error": result.get("error"),
                    "size_bytes": int(result.get("size_bytes", 0) or 0),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def upload_package_setup_profile_zip(
        self,
        upload_path: Path,
        *,
        filename: str,
        overwrite: bool = False,
        actor: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Validate and store one uploaded setup profile archive, then record audit details."""
        result = _package_profiles.upload_profile_zip(self, upload_path, filename=filename, overwrite=overwrite)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "setup_profile_upload",
                safe_actor,
                details={
                    "filename": str(result.get("filename") or filename or ""),
                    "profile_name": str(result.get("profile_name") or ""),
                    "overwrite": bool(overwrite),
                    "status": str(result.get("status") or "error"),
                    "error": result.get("error"),
                    "size_bytes": int(result.get("size_bytes", 0) or 0),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def delete_package_setup_wheel(
        self,
        filename: str,
        *,
        actor: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Delete one uploaded setup wheel and record audit details."""
        result = _package_store.delete_public_wheel(self.package_store_paths, filename)
        result["setup_status"] = _package_profiles.setup_status(self)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "setup_wheel_delete",
                safe_actor,
                details={
                    "filename": str(result.get("filename") or filename or ""),
                    "status": str(result.get("status") or "error"),
                    "error": result.get("error"),
                    "deleted_imported": bool(result.get("deleted_imported", False)),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def delete_package_setup_profile(
        self,
        profile_name: str,
        *,
        actor: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Delete one uploaded setup profile and record audit details."""
        result = _package_profiles.delete_uploaded_profile(self, profile_name)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "setup_profile_delete",
                safe_actor,
                details={
                    "profile_name": str(result.get("profile_name") or profile_name or ""),
                    "status": str(result.get("status") or "error"),
                    "error": result.get("error"),
                    "removed_cached_venv": bool(result.get("removed_cached_venv", False)),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result


    def build_package_profile(self, profile_name: str | None = None, *, rebuild: bool = False, actor: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Build or rebuild one named package profile and record an audit event."""
        result = _package_profiles.build_profile(self, profile_name, rebuild=rebuild)
        setup_target = str(result.get("profile_name") or profile_name or self.package_profile_default or _package_profiles.DEFAULT_SETUP_TARGET_PROFILE)
        result["setup_status"] = _package_profiles.setup_status(self, target_profile=setup_target)
        result["inventory"] = _package_profiles.list_profiles(self)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "package_profile_build",
                safe_actor,
                details={
                    "profile_name": str(profile_name or self.package_profile_default or ""),
                    "rebuild": bool(rebuild),
                    "status": str(result.get("status") or "unknown"),
                    "error": result.get("error") or result.get("last_error"),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def _supervisor_api_post(self, path: str, payload: Dict[str, Any] | None = None, *, timeout_seconds: int = 15) -> Dict[str, Any]:
        """POST one JSON payload to the Home Assistant Supervisor API."""
        if not SUPERVISOR_TOKEN:
            return {"ok": False, "status_code": 503, "error": "supervisor_token_missing", "payload": {}}
        url = f"{SUPERVISOR_API}{path}"
        data = json.dumps(payload if payload is not None else {}).encode("utf-8")
        req = Request(
            url=url,
            data=data,
            headers={
                "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
                body = resp.read()
                parsed: Dict[str, Any]
                try:
                    parsed = json.loads(body.decode("utf-8", errors="replace")) if body else {}
                except Exception:
                    parsed = {}
                return {"ok": True, "status_code": int(getattr(resp, "status", 200) or 200), "payload": parsed}
        except HTTPError as exc:
            body = exc.read()
            try:
                parsed = json.loads(body.decode("utf-8", errors="replace")) if body else {}
            except Exception:
                parsed = {}
            error = str(parsed.get("message") or parsed.get("error") or exc.reason or exc)
            return {"ok": False, "status_code": int(getattr(exc, "code", 500) or 500), "error": error, "payload": parsed}
        except Exception as exc:
            return {"ok": False, "status_code": 503, "error": str(exc), "payload": {}}

    def apply_persistent_package_mode(self, target_profile: str | None = None, *, actor: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Save the recommended persistent-package settings through Supervisor."""
        safe_target = str(target_profile or self.package_profile_default or _package_profiles.DEFAULT_SETUP_TARGET_PROFILE).strip()
        if not safe_target:
            safe_target = _package_profiles.DEFAULT_SETUP_TARGET_PROFILE
        raw_options = read_raw_options()
        python_updates = {
            "install_requirements": True,
            "dependency_mode": "profile",
            "package_profiles_enabled": True,
            "package_profile_default": safe_target,
            "package_allow_public_wheelhouse": True,
            "package_public_wheelhouse_subdir": str(getattr(self, "package_public_wheelhouse_subdir", "wheel_uploads") or "wheel_uploads"),
            "package_offline_prefer_local": True,
            "venv_reuse_enabled": True,
        }
        candidate_options = _merge_python_options(raw_options, python_updates)
        validate = self._supervisor_api_post("/addons/self/options/validate", candidate_options)
        validate_payload = validate.get("payload") if isinstance(validate.get("payload"), dict) else {}
        if not validate.get("ok"):
            return {
                "status": "error",
                "error": str(validate.get("error") or "supervisor_validate_failed"),
                "target_profile": safe_target,
                "setup_status": self.package_setup_status(),
            }
        if validate_payload and validate_payload.get("valid") is False:
            return {
                "status": "error",
                "error": str(validate_payload.get("message") or "options_invalid"),
                "target_profile": safe_target,
                "setup_status": self.package_setup_status(),
            }
        update = self._supervisor_api_post("/addons/self/options", {"options": candidate_options})
        if not update.get("ok"):
            return {
                "status": "error",
                "error": str(update.get("error") or "supervisor_update_failed"),
                "target_profile": safe_target,
                "setup_status": self.package_setup_status(),
            }
        result = {
            "status": "ok",
            "target_profile": safe_target,
            "changed_keys": sorted(python_updates.keys()),
            "restart_required": True,
            "setup_status": self.package_setup_status(),
        }
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "setup_persistent_mode_apply",
                safe_actor,
                details={
                    "target_profile": safe_target,
                    "changed_keys": list(result["changed_keys"]),
                    "status": "ok",
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def register_active_package_environment(self, environment_key: str | None) -> None:
        """Record that one reusable environment key is attached to a running job."""
        key = str(environment_key or "").strip()
        if not key:
            return
        with self._active_package_env_lock:
            self._active_package_env_keys.add(key)

    def release_active_package_environment(self, environment_key: str | None) -> None:
        """Release one active reusable environment key after job completion."""
        key = str(environment_key or "").strip()
        if not key:
            return
        with self._active_package_env_lock:
            self._active_package_env_keys.discard(key)

    def active_package_environment_keys(self) -> List[str]:
        """Return active reusable environment keys that must not be pruned."""
        with self._active_package_env_lock:
            return sorted(self._active_package_env_keys)

    def package_summary(self) -> Dict[str, Any]:
        """Return one combined package subsystem summary payload."""
        cache = self.package_cache_summary()
        profiles = self.list_package_profiles()
        default_profile = str(getattr(self, "package_profile_default", "") or "")
        summary = {
            "cache_private_bytes": int(cache.get("private_bytes", 0) or 0),
            "cache_public_bytes": int(cache.get("public_bytes", 0) or 0),
            "cache_max_bytes": int(cache.get("package_cache_max_bytes", 0) or 0),
            "cache_over_limit": bool(cache.get("over_limit", False)),
            "venv_count": int(cache.get("venv_count", 0) or 0),
            "wheel_count": int(cache.get("wheel_count", 0) or 0),
            "profile_count": int(profiles.get("profile_count", 0) or 0),
            "ready_profile_count": int(profiles.get("ready_count", 0) or 0),
            "default_profile": default_profile,
            "last_prune_status": cache.get("last_prune_status"),
            "last_prune_reason": cache.get("last_prune_reason"),
            "last_prune_removed": int(cache.get("last_prune_removed", 0) or 0),
            "last_prune_utc": cache.get("last_prune_utc"),
        }
        return {
            "status": str(cache.get("status") or "ok"),
            "dependency_mode": str(getattr(self, "dependency_mode", "per_job") or "per_job"),
            "package_profiles_enabled": bool(getattr(self, "package_profiles_enabled", True)),
            "default_profile": default_profile,
            "summary": summary,
            "cache": cache,
            "profiles": profiles,
        }

    def package_cache_summary(self) -> Dict[str, Any]:
        """Return current package storage usage, limits, and recent actions."""
        return _package_prune.package_cache_summary(self)

    def prune_package_cache(self, *, actor: Dict[str, Any] | None = None, reason: str = "manual") -> Dict[str, Any]:
        """Prune package storage to the configured soft cap and record audit."""
        result = _package_prune.prune_package_store(self, reason=reason, actor=actor)
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "package_cache_prune",
                safe_actor,
                details={
                    "reason": reason,
                    "status": str(result.get("status") or "unknown"),
                    "removed": int(result.get("removed", 0) or 0),
                    "removed_bytes": int(result.get("removed_bytes", 0) or 0),
                    "before_bytes": int(result.get("before_bytes", 0) or 0),
                    "after_bytes": int(result.get("after_bytes", 0) or 0),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def purge_package_cache(
        self,
        *,
        actor: Dict[str, Any] | None = None,
        reason: str = "manual",
        include_venvs: bool = False,
        include_imported_wheels: bool = False,
    ) -> Dict[str, Any]:
        """Purge package caches and optional reusable environments, then record audit."""
        result = _package_prune.purge_package_store(
            self,
            reason=reason,
            actor=actor,
            include_venvs=include_venvs,
            include_imported_wheels=include_imported_wheels,
        )
        safe_actor = actor or {"client_ip": "", "via_ingress": False, "user_id": None, "user_name": None, "display_name": None, "ingress_path": None}
        try:
            self.record_audit_event(
                "package_cache_purge",
                safe_actor,
                details={
                    "reason": reason,
                    "status": str(result.get("status") or "unknown"),
                    "include_venvs": bool(include_venvs),
                    "include_imported_wheels": bool(include_imported_wheels),
                    "removed": int(result.get("removed", 0) or 0),
                    "removed_bytes": int(result.get("removed_bytes", 0) or 0),
                },
                persist_status=False,
            )
        except Exception:
            pass
        return result

    def _start_telemetry_worker_if_needed(self) -> None:
        """Start the telemetry worker lazily when telemetry publication is enabled."""
        th = self._telemetry_thread
        if th is not None and th.is_alive():
            return
        self._telemetry_thread = threading.Thread(target=self._telemetry_worker_loop, name="publish-telemetry", daemon=True)
        self._telemetry_thread.start()

    def _telemetry_worker_loop(self) -> None:
        """Drain queued telemetry events and publish them best-effort."""
        while True:
            if self._stop_event.is_set() and self._telemetry_queue.empty():
                return
            try:
                topic, body = self._telemetry_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                req = Request(
                    url=f"{SUPERVISOR_CORE_API}/services/mqtt/publish",
                    data=json.dumps({"topic": topic, "payload": body, "retain": False}).encode("utf-8"),
                    headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"},
                    method="POST",
                )
                # Use a reduced timeout here so that even the background
                # worker does not block for an extended period on network I/O.
                with urlopen(req, timeout=2) as resp:  # noqa: S310
                    _ = resp.read()
            except Exception:
                # Telemetry failures are intentionally ignored; they should not
                # affect core runner behavior.
                pass
            finally:
                self._telemetry_queue.task_done()

    def stop_background_workers(self, timeout_seconds: float = 1.0) -> None:
        """Request background worker shutdown and join briefly (best-effort)."""
        self._stop_event.set()
        if self._reaper_thread is not None:
            self._reaper_thread.join(timeout=max(0.0, float(timeout_seconds)))
        if self._telemetry_thread is not None:
            self._telemetry_thread.join(timeout=max(0.0, float(timeout_seconds)))

    def publish_telemetry(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publish optional telemetry over Home Assistant MQTT service.

        This method is intentionally non-blocking with respect to network I/O:
        enqueueing is best-effort and returns immediately; a bounded background
        worker performs the Supervisor API call.
        """
        if not self.telemetry_mqtt_enabled:
            return
        if not SUPERVISOR_TOKEN:
            return

        topic = f"{self.telemetry_topic_prefix.rstrip('/')}/{event_type.strip('/') or 'event'}"
        body = json.dumps(payload, separators=(",", ":"))

        self._start_telemetry_worker_if_needed()
        try:
            self._telemetry_queue.put_nowait((topic, body))
        except queue.Full:
            # Drop telemetry when saturated; never block core execution paths.
            return

    def _write_status(self, j: Job) -> None:
        return self._job_store.write_status(j)

    def _run_job(self, job_id: str) -> None:
        return _executor.run_job(self, job_id)

    def _notification_id(self, j: Job) -> Optional[str]:
        return _notify.notification_id(self, j)

    def _notify_done(self, j: Job) -> None:
        return _notify.notify_done(self, j, _ha_persistent_notification)

    def _iter_outputs(self, j: Job) -> Iterable[Path]:
        return _results.iter_outputs(self, j)

    def _make_result_zip(self, j: Job) -> None:
        return _results.make_result_zip(self, j)

    def _reaper(self) -> None:
        return _housekeeping.reaper_loop(self, stop_event=self._stop_event)

    def _load_jobs_from_disk(self) -> None:
        return self._job_store.load_jobs_from_disk()


def hashlib_sha256_bytes(b: bytes) -> str:
    return _hashes.hashlib_sha256_bytes(b)


def _redact_basic_auth_in_urls(text: str) -> str:
    return _redact.redact_basic_auth_in_urls(text)


def _redact_common_query_secrets(text: str) -> str:
    return _redact.redact_common_query_secrets(text)


def _redact_pip_text(text: str, urls: List[str]) -> str:
    return _redact.redact_pip_text(text, urls)


def _safe_write_text_no_symlink(path: Path, text: str) -> None:
    return _fs_safe.safe_write_text_no_symlink(path, text)


def _safe_zip_write(zf: Any, path: Path, arcname: str, base_dir: Path) -> None:
    return _fs_safe.safe_zip_write(zf, path, arcname, base_dir)


def _kill_process_group(p: Any, soft_seconds: int) -> None:
    return _process.kill_process_group(p, soft_seconds)
