from __future__ import annotations

"""
Entry point for the Pythonista Job Runner Home Assistant add-on.

0.6.3
- Fix runner_core missing imports that could crash on job completion (result zip, notifications).
- Wire up install_requirements and pip_* options (per-job pip install into work/_deps, adds to PYTHONPATH).
- Wire up cleanup_min_free_mb (best-effort deletion of oldest finished jobs when disk is low).
- Fix duplicate ip_in_cidrs definition in utils.
- Preserve job ordering across restarts.
- Add CI job to run pytest.
"""

from http_api import serve


def main() -> None:
    """
    Start the HTTP API server for the Pythonista Job Runner add-on.
    
    This function serves as the module entry point when executed as a script.
    """
    serve()


if __name__ == "__main__":
    main()

