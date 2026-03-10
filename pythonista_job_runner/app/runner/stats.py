# Version: 0.6.13-webui.1
"""Stats helpers for the Runner.

These functions are intentionally side-effect free except for updating Runner cache
fields.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from runner.store import JobStore


def get_disk_usage_cached(runner: object, ttl_seconds: int = 5) -> Tuple[int, int]:
    """Return (free_bytes, total_bytes) for jobs_dir with a small cache."""
    now = time.time()
    try:
        if now - float(getattr(runner, "_disk_cache_ts")) < ttl_seconds:
            return int(getattr(runner, "_disk_cache_free")), int(getattr(runner, "_disk_cache_total"))
    except Exception:
        pass

    free_b = 0
    total_b = 0
    jobs_dir = getattr(runner, "jobs_dir")
    try:
        du = shutil.disk_usage(str(jobs_dir))
        free_b = int(du.free)
        total_b = int(du.total)
    except Exception:
        free_b = 0
        total_b = 0

    setattr(runner, "_disk_cache_ts", now)
    setattr(runner, "_disk_cache_free", free_b)
    setattr(runner, "_disk_cache_total", total_b)
    return free_b, total_b


def dir_size_bytes(root: Path, max_files: int = 200_000) -> int:
    """Best-effort directory size computation.

    Avoids Path.rglob overhead and caps traversal to prevent worst-case blow-ups.
    """
    try:
        root_str = str(root)
    except Exception:
        return 0
    total = 0
    files_seen = 0
    stack = [root_str]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for ent in it:
                    try:
                        if ent.is_symlink():
                            continue
                        if ent.is_file(follow_symlinks=False):
                            try:
                                total += int(ent.stat(follow_symlinks=False).st_size)
                            except Exception:
                                pass
                            files_seen += 1
                            if files_seen >= max_files:
                                return total
                        elif ent.is_dir(follow_symlinks=False):
                            stack.append(ent.path)
                    except Exception:
                        continue
        except Exception:
            continue
    return total


def get_jobs_dir_bytes_cached(runner: object, ttl_seconds: int = 30) -> int:
    """Return approximate bytes used by jobs_dir with caching."""
    now = time.time()
    try:
        if now - float(getattr(runner, "_jobs_bytes_cache_ts")) < ttl_seconds:
            return int(getattr(runner, "_jobs_bytes_cache"))
    except Exception:
        pass

    size_b = 0
    jobs_dir = getattr(runner, "jobs_dir")
    try:
        if jobs_dir.exists():
            size_b = dir_size_bytes(jobs_dir)
    except Exception:
        size_b = 0

    setattr(runner, "_jobs_bytes_cache_ts", now)
    setattr(runner, "_jobs_bytes_cache", size_b)
    return size_b


def stats_dict(runner: object) -> Dict[str, Any]:
    """Return the /stats.json payload."""
    store = JobStore.for_runner(runner)
    states = [str(getattr(j, "state", "")) for j in store.jobs_values_snapshot()]

    jobs_total = len(states)
    jobs_running = sum(1 for s in states if s == "running")
    jobs_error = sum(1 for s in states if s == "error")
    jobs_done = sum(1 for s in states if s == "done")
    jobs_queued = sum(1 for s in states if s == "queued")

    disk_free, disk_total = get_disk_usage_cached(runner)
    jobs_bytes = get_jobs_dir_bytes_cached(runner)

    addon_version = str(getattr(runner, "addon_version", ""))

    return {
        "runner_version": addon_version,
        "jobs_total": jobs_total,
        "jobs_running": jobs_running,
        "jobs_done": jobs_done,
        "jobs_error": jobs_error,
        "jobs_queued": jobs_queued,
        "job_retention_hours": int(getattr(runner, "retention_hours", 0)),
        "jobs_dir_bytes": jobs_bytes,
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
        "ingress_strict": bool(getattr(runner, "ingress_strict", False)),
        "api_allow_cidrs": list(getattr(runner, "api_allow_cidrs", [])),
        "bind_host": str(getattr(runner, "bind_host", "")),
        "bind_port": int(getattr(runner, "bind_port", 0)),
    }
