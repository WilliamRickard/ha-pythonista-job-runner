from __future__ import annotations

"""Compatibility module for the HTTP API.

The implementation lives in ``http_api_server`` to keep this public import
surface stable while making handler code easier to navigate.
"""

from http_api_server import Handler, RunnerHTTPServer, serve

__all__ = ["Handler", "RunnerHTTPServer", "serve"]
