from __future__ import annotations

"""
Entry point for the Pythonista Job Runner add-on.

0.6.1 hotfix
- Fix add-on startup crash seen as NameError: field is not defined (dataclasses.field import/usage).

v0.6.1 implements plan steps 7 to 10 (plus a hotfix):
- Step 7: Job detail + diagnostics in Web UI (stats, disk/retention, curl snippet)
- Step 8: Smoother live output (delta tail remains; configurable poll interval in UI)
- Step 9: Actionable, non-spammy notifications (notification_id overwrite mode)
- Step 10: Split into modules (utils, runner_core, webui, http_api)
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

