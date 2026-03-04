# Version: 0.6.12-refactor.1
"""Process management helpers."""

from __future__ import annotations

import os
import signal
import subprocess
import time


def kill_process_group(p: subprocess.Popen, soft_seconds: int) -> None:
    """Terminate a subprocess process group, then SIGKILL after a short grace period."""
    try:
        pgid = os.getpgid(p.pid)
    except Exception:
        try:
            p.terminate()
        except Exception:
            pass
        return

    try:
        os.killpg(pgid, signal.SIGTERM)
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < float(soft_seconds):
        if p.poll() is not None:
            return
        time.sleep(0.1)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except Exception:
        pass
