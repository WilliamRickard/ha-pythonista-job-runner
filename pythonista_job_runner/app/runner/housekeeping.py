# Version: 0.6.12-refactor.1
"""Housekeeping helpers: free-space enforcement and retention reaper."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import List, Tuple

from utils import parse_utc


def disk_free_bytes(runner: object) -> int:
    """Return free bytes for the filesystem containing jobs_dir."""
    jobs_dir = getattr(runner, "jobs_dir")
    try:
        return int(shutil.disk_usage(str(jobs_dir)).free)
    except Exception:
        return 0


def ensure_min_free_space(runner: object) -> None:
    """Best-effort cleanup of finished jobs if disk is below configured threshold.

    This is intentionally conservative: only deletes jobs that are finalised (done/error)
    and have a result zip present, to avoid racing jobs that are still packaging artefacts.
    """
    try:
        min_mb = int(getattr(runner, "cleanup_min_free_mb", 0))
    except Exception:
        min_mb = 0
    if min_mb <= 0:
        return

    target_free = int(min_mb) * 1024 * 1024
    free_now = disk_free_bytes(runner)
    if free_now >= target_free:
        return

    # Throttle scans when disk is low to avoid repeated O(n) directory walks.
    now = time.time()
    try:
        last = float(getattr(runner, "_last_cleanup_check_ts", 0.0))
    except Exception:
        last = 0.0
    if now - last < 30:
        return
    setattr(runner, "_last_cleanup_check_ts", now)

    jobs_dir = getattr(runner, "jobs_dir")

    # Only delete jobs that have finished (done/error), oldest first.
    candidates: List[Tuple[float, str, Path]] = []
    for p in jobs_dir.iterdir() if jobs_dir.exists() else []:
        if not p.is_dir():
            continue
        status_path = p / "status.json"
        if not status_path.exists():
            continue
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        job_id = str(data.get("job_id") or p.name)
        state = str(data.get("state") or "")
        if state not in ("done", "error"):
            continue

        # Avoid racing jobs marked done/error before result packaging completes.
        if not any(p.glob("result_*.zip")) and not (p / "result.zip").exists():
            continue

        finished = parse_utc(str(data.get("finished_utc") or ""))
        if finished is None:
            try:
                finished = float(p.stat().st_mtime)
            except Exception:
                finished = 0.0
        candidates.append((float(finished), job_id, p))

    candidates.sort(key=lambda t: t[0])

    for _, job_id, p in candidates:
        if disk_free_bytes(runner) >= target_free:
            return

        # Prefer the standard delete path to keep in-memory state consistent.
        deleted = False
        try:
            deleted = bool(getattr(runner, "delete")(job_id))
        except Exception:
            deleted = False

        if deleted:
            continue

        # Fallback: best-effort remove directory and clean in-memory indices.
        try:
            shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass

        lock = getattr(runner, "_lock")
        jobs = getattr(runner, "_jobs")
        job_order = getattr(runner, "_job_order")
        procs = getattr(runner, "_procs")
        with lock:
            jobs.pop(job_id, None)
            setattr(runner, "_job_order", [x for x in job_order if x != job_id])
            procs.pop(job_id, None)


def reaper_loop(runner: object) -> None:
    """Background retention loop that deletes stale finished jobs."""
    while True:
        try:
            cutoff = int(time.time()) - (int(getattr(runner, "retention_hours", 0)) * 3600)
            stale: List[str] = []

            lock = getattr(runner, "_lock")
            jobs = getattr(runner, "_jobs")

            with lock:
                for jid, j in jobs.items():
                    if j.finished_utc:
                        finished = parse_utc(j.finished_utc) or time.time()
                        if int(finished) < cutoff:
                            stale.append(jid)

            for jid in stale:
                j = getattr(runner, "get")(jid)
                if j:
                    shutil.rmtree(j.job_dir, ignore_errors=True)

                lock = getattr(runner, "_lock")
                jobs = getattr(runner, "_jobs")
                job_order = getattr(runner, "_job_order")
                procs = getattr(runner, "_procs")

                with lock:
                    jobs.pop(jid, None)
                    setattr(runner, "_job_order", [x for x in job_order if x != jid])
                    procs.pop(jid, None)
        except Exception:
            pass
        time.sleep(600)
