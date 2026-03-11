from __future__ import annotations

"""
Entry point for the Pythonista Job Runner Home Assistant add-on.

Version: 0.6.12

See pythonista_job_runner/CHANGELOG.md for release notes.
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

